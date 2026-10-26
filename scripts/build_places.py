"""Build an offline, partial Place catalog. Run with the QGIS Python runtime."""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from build_recommendation_places import category_for

ROOT = Path(__file__).resolve().parents[1]
DONGS = {"남포동", "광복동", "부평동", "대청동"}
COLUMNS = ["id", "name", "category", "visit_type", "address", "lon", "lat",
           "admin_dong", "duration_min", "estimated_spend", "opening_hours", "data_date", "place_type", "payment_status", "source"]
OPENING_HOURS_COLUMNS = ['place_id', 'weekday', 'status', 'opens_at', 'closes_at', 'closes_next_day', 'source', 'checked_date']
PROVENANCE = ["id", "source_file", "source_id", "raw_category", "category_evidence",
              "supplemental_evidence", "visit_type_rule", "duration_basis", "in_market", "market_ids"]


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, columns):
    temporary = Path(str(path) + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def rules_from(path):
    rules = {}
    for row in read_csv(path):
        key = row["visit_type"].strip()
        if not key or key in rules:
            raise ValueError("Missing or duplicate visit_type")
        minutes = float(row["duration_min"])
        if not math.isfinite(minutes) or minutes <= 0 or not minutes.is_integer():
            raise ValueError("duration_min must be a positive whole number")
        row["duration_min"] = int(minutes)
        row["visit_type"] = key
        rules[key] = row
    return rules


def merchant_type(row, supplemental=""):
    tag = row.get("travel_category") or row.get("purpose_tags", "")
    evidence = row.get("classification_evidence", "") + " " + supplemental
    if tag in {"소품·기념품 쇼핑", "쇼핑"}:
        return None, "shopping_selection_pending"
    if tag in {"커피·디저트", "카페·디저트"}:
        return "seated_cafe", "category_default; seating_not_verified"
    if tag in {"식사|간식·먹거리", "간식·먹거리|식사"}:
        return "quick_meal", "mixed_meal_snack"
    if tag in {"식사", "식당"}:
        quick = any(word in evidence for word in ["> 분식", "김밥/만두/분식", "토스트/샌드위치", "패스트푸드", "햄버거"])
        return ("quick_meal", "explicit_quick_meal") if quick else ("general_restaurant", "category_default")
    if tag == "간식·먹거리":
        dessert = any(word in evidence for word in ["제과", "베이커리", "빵/도넛", "도넛", "떡/한과", "떡,한과", "아이스크림", "빙수", "디저트"])
        savory = any(word in evidence for word in ["닭강정", "핫도그", "분식", "토스트", "샌드위치"])
        if dessert and savory:
            return None, "snack_subtype_conflict"
        if not dessert and not savory:
            return None, "snack_subtype_missing"
        # Reuse the existing service category mapping after checking subtype conflicts.
        category = category_for(SimpleNamespace(purpose_tags=tag, evidence=json.dumps([["merged", "", evidence]])))
        return ("takeaway_dessert", "dessert_default; takeaway_not_verified") if category == "카페·디저트" else ("quick_meal", "savory_snack")
    return None, "category_unconfirmed"


def get_boundaries(path):
    from qgis.core import QgsVectorLayer
    layer = QgsVectorLayer(str(path), "mvp", "ogr")
    if not layer.isValid() or layer.crs().authid() != "EPSG:4326":
        raise ValueError("MVP boundary must be a valid EPSG:4326 vector layer")
    result = []
    for feature in layer.getFeatures():
        name = feature["adm_nm"].split()[-1]
        geometry = feature.geometry()
        if not geometry.isGeosValid():
            geometry = geometry.makeValid()
        if name not in DONGS or geometry.isEmpty() or not geometry.isGeosValid():
            raise ValueError("Invalid MVP boundary")
        result.append((name, geometry))
    if len(result) != 4 or {name for name, _ in result} != DONGS:
        raise ValueError("Exactly four approved administrative dong boundaries are required")
    return result


def admin_dong(row, boundaries):
    from qgis.core import QgsGeometry, QgsPointXY
    try:
        lon, lat = float(row["lon"]), float(row["lat"])
    except (KeyError, ValueError, TypeError):
        return "", "coordinates_missing"
    if not math.isfinite(lon) or not math.isfinite(lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return "", "coordinates_invalid"
    point = QgsGeometry.fromPointXY(QgsPointXY(lon, lat))
    hits = [name for name, geometry in boundaries if geometry.intersects(point)]
    if not hits:
        return "", "outside_mvp"
    if len(hits) != 1:
        return "", "multiple_admin_boundaries"
    return hits[0], ""


def make_place(row, visit_type, dong, rules, category=None, curated=False):
    rule = rules[visit_type]
    category = category or rule["category"]
    if category != rule["category"]:
        raise ValueError("visit_type/category conflict")
    place = {column: "" for column in COLUMNS}
    for column in ["id", "name", "address", "lon", "lat", "data_date"]:
        place[column] = row.get(column, "")
    if any(not str(place[key]).strip() for key in ["id", "name", "address"]):
        raise ValueError("required_identity_missing")
    spend = row.get("estimated_spend", "") if category in {"식당", "카페·디저트"} else ""
    if spend not in (None, ""):
        spend = float(spend)
        if not math.isfinite(spend) or spend < 0:
            raise ValueError("estimated_spend_invalid")
    else:
        spend = ""
    place.update(category=category, visit_type=visit_type, admin_dong=dong,
                 duration_min=rule["duration_min"], estimated_spend=spend,
                 place_type="market" if visit_type == "traditional_market" else "attraction" if category == "관광명소" else "merchant",
                 payment_status="not_verified" if category == "관광명소" else "merchant_listed",
                 source=row.get("source") or ("curated_tourism" if curated else "dongbaekjeon"))
    # Only supplied optional information is copied. No estimates or scraped substitutes.
    place["opening_hours"] = row.get("opening_hours", "") or ""
    return place


def shopping_merchant(selected, merchants):
    """Resolve curator IDs using both the merchant name and supplied source coordinates."""
    direct = [r for r in merchants if r["id"] == selected["id"]]
    if direct:
        return direct[0]
    import re
    normalize = lambda name: re.sub(r"\s+", "", name)
    candidates = []
    for row in merchants:
        try:
            same_point = abs(float(row["lon"]) - float(selected["lon"])) < 0.000001 and abs(float(row["lat"]) - float(selected["lat"])) < 0.000001
        except (KeyError, ValueError, TypeError):
            continue
        name, chosen = normalize(row["name"]), normalize(selected.get("name", ""))
        if same_point and name and (chosen == name or chosen.startswith(name + "부산")):
            candidates.append(row)
    if len(candidates) != 1:
        raise ValueError("Shopping identity is missing or ambiguous: " + selected["id"])
    return candidates[0]


def build(args):
    from qgis.core import QgsApplication
    app = QgsApplication([], False)
    app.initQgis()
    data = args.data_dir
    source = data / "GIS/mvp/mvp_merchants.csv"
    merchants = read_csv(source)
    if len({row["id"] for row in merchants}) != len(merchants):
        raise ValueError("Duplicate merchant IDs")
    rules = rules_from(args.rules_file)
    boundaries = get_boundaries(data / "GIS/boundaries/mvp_admin_boundaries.geojson")
    baseline = {row["id"]: row for row in read_csv(data / "travel_purposes/merchants_travel_purposes.csv")}
    delta_file = data / "travel_purposes/kakao_update_20261021/merchants_travel_purposes_delta.csv"
    baseline.update({row["id"]: row for row in read_csv(delta_file)})
    ready, reviews, provenance = {}, {}, {}
    excluded = Counter()

    def queue(row, reason, source_file):
        review_key = row.get("id") or "missing_id:{}:{}".format(source_file, len(reviews))
        reviews[review_key] = dict(id=row.get("id", ""), name=row.get("name", ""),
                                          source_file=str(source_file), reason=reason,
                                          current_status=row.get("purpose_status", ""),
                                          raw_category=row.get("travel_category", row.get("category", "")))

    def add(row, visit_type, reason, source_file, supplemental="", category=None, curated=False):
        dong, problem = admin_dong(row, boundaries)
        if problem:
            queue(row, problem, source_file)
            return
        try:
            place = make_place(row, visit_type, dong, rules, category, curated)
        except (ValueError, KeyError) as error:
            queue(row, str(error), source_file)
            return
        if place["id"] in ready:
            raise ValueError("Duplicate final place ID: " + place["id"])
        ready[place["id"]] = place
        reviews.pop(place["id"], None)
        provenance[place["id"]] = dict(id=place["id"], source_file=str(source_file), source_id=row["id"],
                                     raw_category=row.get("travel_category", row.get("category", "")),
                                     category_evidence=row.get("classification_evidence", ""),
                                     supplemental_evidence=supplemental, visit_type_rule=reason,
                                     duration_basis=rules[visit_type].get("basis", ""),
                                     in_market=row.get("in_market", ""), market_ids=row.get("market_ids", ""))

    for row in merchants:
        status = row.get("purpose_status")
        if status == "outside_scope":
            excluded[status] += 1
            continue
        if status != "classified":
            queue(row, "classification_" + str(status), source)
            continue
        extra = baseline.get(row["id"], {}).get("evidence", "")
        visit_type, reason = merchant_type(row, extra)
        if not visit_type:
            queue(row, reason, source)
            continue
        add(row, visit_type, reason, source, extra)

    if args.shopping_file:
        selected = read_csv(args.shopping_file)
        if len(selected) != 10 or len({row["id"] for row in selected}) != 10:
            raise ValueError("Shopping selection must contain exactly 10 unique merchant IDs")
        for selected_row in selected:
            original = shopping_merchant(selected_row, merchants)
            row = dict(original)
            # Preserve the merchant ID while retaining curator-supplied display information.
            row.update({key: value for key, value in selected_row.items() if key != "id" and value != ""})
            visit_type = selected_row.get("visit_type", "")
            if visit_type not in {"general_shopping", "souvenir_shop", "retail_store"}:
                raise ValueError("Invalid shopping visit_type")
            if selected_row.get("duration_min") and float(selected_row["duration_min"]) != rules[visit_type]["duration_min"]:
                raise ValueError("Shopping duration conflicts with duration rules")
            if row["id"] in ready:
                raise ValueError("Selected shop already classified in catalog: " + row["id"])
            add(row, visit_type, "curator_selected_10", args.shopping_file,
                supplemental="curator_id=" + selected_row["id"] + "; source_coordinate_and_name_match; source_coordinates_not_field_verified",
                category="쇼핑")

    if args.tourism_file:
        tourist_rows = read_csv(args.tourism_file)
        tourist_ids = [row.get("id", "") for row in tourist_rows if row.get("id")]
        if len(tourist_ids) != len(set(tourist_ids)):
            raise ValueError("Duplicate tourism IDs")
        for original in tourist_rows:
            row = dict(original)
            if not original.get("id"):
                queue(row, "tourism_id_missing", args.tourism_file)
                continue
            row["id"] = original["id"] if original["id"].startswith("spot:") else "spot:" + original["id"]
            visit_type = row.get("visit_type", "")
            if visit_type not in {"scenic_spot", "exhibition_experience", "traditional_market"}:
                queue(row, "tourism_visit_type_missing", args.tourism_file)
                continue
            add(row, visit_type, "curator_tourism", args.tourism_file, category="관광명소", curated=True)

    assert set(ready).isdisjoint(reviews)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    support = data / "place_support"
    support.mkdir(parents=True, exist_ok=True)
    write_csv(out / "places.csv", list(ready.values()), COLUMNS)
    hours_file = out / "place_opening_hours.csv"
    if not hours_file.exists():
        write_csv(hours_file, [], OPENING_HOURS_COLUMNS)
    write_csv(support / "places_review.csv", list(reviews.values()), ["id", "name", "source_file", "reason", "current_status", "raw_category"])
    write_csv(support / "place_sources.csv", list(provenance.values()), PROVENANCE)
    summary = dict(ready=len(ready), review=len(reviews), excluded=dict(excluded),
                   categories=dict(Counter(row["category"] for row in ready.values())),
                   visit_types=dict(Counter(row["visit_type"] for row in ready.values())),
                   review_reasons=dict(Counter(row["reason"] for row in reviews.values())),
                   shopping_input_received=bool(args.shopping_file), tourism_input_received=bool(args.tourism_file),
                   release_status="partial" if not args.shopping_file or not args.tourism_file else "review_required",
                   duration_basis="User-provided initial MVP assumptions; not measured dwell times",
                   source_mvp=str(source), backend_switched=False)
    (support / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/processed/bin")
    parser.add_argument("--rules-file", type=Path, default=ROOT / "data/processed/bin/place_support/duration_rules.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/fin")
    parser.add_argument("--shopping-file", type=Path)
    parser.add_argument("--tourism-file", type=Path)
    build(parser.parse_args())

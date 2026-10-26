"""Merge researched old-town places without rebuilding or overwriting existing survey data."""
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/oldtown_places/20261026/oldtown_shopping_attractions.csv"
SUPPORT = ROOT / "data/processed/bin/place_support"
FIN = ROOT / "data/processed/fin"
EXTRA = ["district", "admission_fee_krw", "admission_fee_weekend_krw", "admission_fee_status", "admission_fee_note"]
SAFE_HOURS = {"공식API안내", "공식웹안내", "공식검색안내", "부분확인_점포별확인"}
# These need another visit type or a more precise, accessible destination.
HELD_NAMES = {"두도", "용두산 자갈치 관광특구", "태종대온천찜질방"}


def read(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames), list(reader)


def write(path, fields, rows):
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    temp.replace(path)


def district(address):
    match = re.search(r"부산(?:광역시)?\s+(중구|동구|서구|영도구)\b", address)
    return match[1] if match else ""


def fee_values(raw):
    status = {"무료":"free", "유료":"paid", "유료_조건확인필요":"conditional"}.get(raw["entry_fee_status"], "unknown")
    if "2026 현장요금 재확인" in raw["review_notes"]:
        status = "conditional"
    def amount(field):
        value = raw.get(field, "")
        if not value or status not in {"free", "paid"}:
            return ""
        number = float(value)
        if not math.isfinite(number) or number < 0 or not number.is_integer():
            raise ValueError("Invalid admission fee: " + raw["raw_id"])
        return str(int(number))
    return dict(admission_fee_krw=amount("adult_fee_krw"),
                admission_fee_weekend_krw=amount("adult_weekend_fee_krw"),
                admission_fee_status=status,
                admission_fee_note=" / ".join(x for x in [raw["fee_basis"], raw["fee_details"]] if x))


def visit_type(raw):
    if raw["place_type"] == "market" or raw["name"] in {"자갈치시장", "부평깡통시장"}:
        return "traditional_market", "관광명소", "market"
    if raw["category"] == "쇼핑":
        return ("general_shopping" if raw["place_type"] in {"shopping_area", "department_store"} else "retail_store"), "쇼핑", "merchant"
    exhibition = any(x in raw["name"] for x in ["박물관", "기념관", "역사관", "미술관", "예술관", "공작소", "센터"])
    return "exhibition_experience" if exhibition else "scenic_spot", "관광명소", "attraction"


def merge(places, research, locations, rules):
    output = [dict(p) for p in places]
    by_id = {p["id"]:p for p in output}
    if len(by_id) != len(output):
        raise ValueError("Duplicate Place ID")
    fields = list(places[0]) + [x for x in EXTRA if x not in places[0]]
    for place in output:
        for field in EXTRA:place.setdefault(field, "unknown" if field == "admission_fee_status" else "")
        place["district"] = district(place["address"])
        if not place["district"]:raise ValueError("Existing place outside old town: " + place["id"])
    audit = []
    for raw in research:
        loc = locations.get(raw["raw_id"], {})
        identity = raw["existing_place_id"]
        generated = "spot:tourapi:" + raw["tourapi_contentid"] if raw["tourapi_contentid"] else "spot:" + raw["raw_id"]
        key = identity or generated
        place = by_id.get(key)
        reason = ""
        if identity and place is None:raise ValueError("Unknown existing place ID: " + identity)
        if place and identity and (place["name"] != raw["name"] and not (place["name"] == "아이하시" and raw["name"] == "아이하시 (수제젓가락공예)")):
            raise ValueError("Existing identity mismatch: " + identity)
        if not place:
            reason = loc.get("reason", "location_not_checked")
            if raw["name"] in HELD_NAMES:reason = "visit_type_or_access_review"
            if not loc.get("admin_dong") or loc.get("district") != raw["district"]:reason = reason or "admin_boundary_unconfirmed"
        if reason:
            audit.append(dict(raw_id=raw["raw_id"],id="",name=raw["name"],action="held",reason=reason,hours_source=raw["hours_source"],fee_source=raw["fee_source"],payment_source=raw["dongbaek_source"]))
            continue
        new = place is None
        if new:
            vt, category, kind = visit_type(raw)
            if vt not in rules:raise ValueError("Missing duration rule")
            place = {field:"" for field in fields}
            place.update(id=key,name=raw["name"],category=category,visit_type=vt,address=raw["address"],
                         lon=loc["lon"],lat=loc["lat"],admin_dong=loc["admin_dong"],district=loc["district"],
                         duration_min=rules[vt],data_date=raw["checked_at"],place_type=kind,
                         payment_status="not_verified",source="oldtown_research_20261026",admission_fee_status="unknown")
            by_id[key]=place;output.append(place)
        if raw["hours_status"] in SAFE_HOURS and raw["opening_hours"]:
            place["opening_hours"] = " ".join(raw["opening_hours"].split())
        elif new and raw["opening_hours"]:
            place["opening_hours"] = " ".join(raw["opening_hours"].split()) + " (운영시간 확인필요)"
        if raw["dongbaek_status"] == "가능":place["payment_status"]="merchant_listed"
        elif raw["dongbaek_status"] == "불가":place["payment_status"]="not_accepted"
        if place["category"] == "관광명소" and raw["fee_details"]:
            place.update(fee_values(raw))
        if place["source"] == "oldtown_research_20261026":
            place["opening_hours"] = " ".join(place["opening_hours"].split())
        audit.append(dict(raw_id=raw["raw_id"],id=key,name=raw["name"],action="added" if new else "merged",reason="",hours_source=raw["hours_source"],fee_source=raw["fee_source"],payment_source=raw["dongbaek_source"]))
    return fields, output, audit


def weekly_rows(raw, place_id):
    if raw["hours_status"] not in {"공식API안내", "공식웹안내"}:
        return []
    hours, closed = raw["opening_hours"], raw["closed_days"]
    # shortcut: only fixed year-round daily hours; seasonal/holiday exceptions stay as source text.
    if closed != "연중무휴" or any(x in hours for x in ["월", "계절", "상이", "문의"]):return []
    if hours == "24시간 개방":start,end,next_day="00:00","00:00",1
    else:
        match=re.fullmatch(r"(?:매일 )?(\d{2}:\d{2})[~\-](\d{2}:\d{2})(?: / (?:입장|발권).*| \(발권.*\))?",hours)
        if not match:return []
        start,end=match.groups();next_day=int(end<=start)
    return [dict(place_id=place_id,weekday=str(day),status="open",opens_at=start,closes_at=end,closes_next_day=str(next_day),source=raw["hours_source"],checked_date=raw["checked_at"]) for day in range(7)]


def main():
    _,places=read(FIN/"places.csv");_,raw=read(RAW);_,locations=read(SUPPORT/"oldtown_locations.csv")
    _,rules=read(SUPPORT/"duration_rules.csv");rules={x["visit_type"].strip():x["duration_min"] for x in rules}
    fields,merged,audit=merge(places,raw,{x["raw_id"]:x for x in locations},rules)
    # Re-running must preserve IDs, existing prices and all unrelated places.
    _,again,_=merge(merged,raw,{x["raw_id"]:x for x in locations},rules)
    assert again==merged
    ids={x["id"] for x in merged};assert len(ids)==len(merged)
    assert all(x["estimated_spend"]==next(p["estimated_spend"] for p in places if p["id"]==x["id"]) for x in merged if x["id"] in {p["id"] for p in places})
    hours_fields,hours=read(FIN/"place_opening_hours.csv");scheduled={x["place_id"] for x in hours}
    for item in audit:
        if item["action"]=="held" or item["id"] in scheduled:continue
        source=next(x for x in raw if x["raw_id"]==item["raw_id"])
        hours.extend(weekly_rows(source,item["id"]));scheduled.add(item["id"])
    previous_file = SUPPORT/"oldtown_merge_review.csv"
    if previous_file.exists():
        _, previous = read(previous_file)
        added = {(x["raw_id"], x["id"]) for x in previous if x["action"] == "added"}
        for item in audit:
            if item["action"] == "merged" and (item["raw_id"], item["id"]) in added:
                item["action"] = "added"
    write(FIN/"places.csv",fields,merged);write(FIN/"place_opening_hours.csv",hours_fields,hours)
    write(SUPPORT/"oldtown_merge_review.csv",list(audit[0]),audit)
    print(json.dumps(dict(places=len(merged),actions=dict(Counter(x["action"] for x in audit)),categories=dict(Counter(x["category"] for x in merged)),districts=dict(Counter(x["district"] for x in merged)),hours_rows=len(hours)),ensure_ascii=False))


if __name__=="__main__":main()

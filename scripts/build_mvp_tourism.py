"""Prepare curated MVP attractions using reviewed coordinate evidence (QGIS Python)."""
import csv
import hashlib
import json
import os
from pathlib import Path

from build_places import admin_dong, get_boundaries, make_place, read_csv, rules_from, write_csv, COLUMNS

ROOT = Path(__file__).resolve().parents[1]


def build(root=ROOT):
    data = root / "data/processed/bin"
    support = data / "place_support"
    source = root / "data/bin/mvp_tourist_spots/mvp_tourist_spots.csv"
    evidence_file = support / "tourism_coordinate_evidence.csv"
    evidence = {r["original_name"]: r for r in read_csv(evidence_file)}
    boundaries = get_boundaries(data / "GIS/boundaries/mvp_admin_boundaries.geojson")
    rules = rules_from(support / "duration_rules.csv")
    types = {"photo_spot": "scenic_spot", "cultural_facility": "exhibition_experience",
             "traditional_market": "traditional_market"}
    ready, reviews = [], []
    selected = read_csv(source)
    if len({r["title"] for r in selected}) != len(selected):
        raise ValueError("Duplicate selected attraction names")
    for row in selected:
        e = evidence.get(row["title"], {})
        visit_type = types.get(row["spot_type"])
        dong, reason = admin_dong(e, boundaries)
        if not visit_type:
            reason = "visit_type_unconfirmed"
        if reason:
            reviews.append({"name": row["title"], "lon": e.get("lon", ""),
                            "lat": e.get("lat", ""), "reason": reason,
                            "coordinate_source": e.get("coordinate_source", ""),
                            "note": e.get("match_note", "")})
            continue
        identity = hashlib.sha256(e["name"].encode("utf-8")).hexdigest()[:16]
        place = make_place({"id": "spot:curated:" + identity, "name": e["name"],
                            "address": row["addr1"], "lon": e["lon"], "lat": e["lat"],
                            "data_date": row["verified_at"], "opening_hours": row["operating_hours"],
                            "source": row["source"] + ";coordinates:" + e["coordinate_source"]},
                           visit_type, dong, rules, curated=True)
        ready.append({**place, "original_name": row["title"], "source_url": row["source_url"],
                      "coordinate_source": e["coordinate_source"],
                      "coordinate_url": e["coordinate_url"], "coordinate_note": e["match_note"]})
    assert len(ready) + len(reviews) == len(selected)
    assert len({p["id"] for p in ready}) == len(ready)
    write_csv(data / "mvp_tourist_spots.csv", ready,
              COLUMNS + ["original_name", "source_url", "coordinate_source", "coordinate_url", "coordinate_note"])
    write_csv(support / "mvp_tourist_spots_review.csv", reviews,
              ["name", "lon", "lat", "reason", "coordinate_source", "note"])
    print(json.dumps({"selected": len(selected), "inside_mvp": len(ready), "review": len(reviews)}))


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from qgis.core import QgsApplication
    app = QgsApplication([], False)
    app.initQgis()
    build()

"""Merge accepted survey prices into places.csv by exact place ID."""
import csv
from decimal import Decimal
from pathlib import Path

from clean_estimated_spend import price_issue, write_csv

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return reader.fieldnames, list(reader)


def merge_prices(places, sources):
    by_id = {row["id"]: row for row in places}
    if len(by_id) != len(places):
        raise ValueError("Duplicate Place IDs")
    prices = {}
    for row in sources:
        value = row["1인 가격(원)"].strip()
        if price_issue(value):
            raise ValueError("Invalid survey price: " + row["장소 ID"])
        amount = Decimal(value.replace(",", ""))
        if amount < 0:
            raise ValueError("Negative survey price")
        key = row["장소 ID"]
        if key in prices:
            raise ValueError("Duplicate survey ID: " + key)
        place = by_id.get(key)
        if place is None or (place["name"], place["category"]) != (row["상호명"], row["카테고리"]):
            raise ValueError("Place identity mismatch: " + key)
        if place["category"] not in {"식당", "카페·디저트"}:
            raise ValueError("Unexpected price category: " + key)
        existing = place.get("estimated_spend", "").strip()
        if existing and Decimal(existing) != amount:
            raise ValueError("Existing price conflict: " + key)
        prices[key] = format(amount.normalize(), "f")
    return [{**row, "estimated_spend": prices.get(row["id"], row.get("estimated_spend", ""))} for row in places]


def main():
    directory = ROOT / "data/processed/estimated_spend"
    target = ROOT / "data/processed/fin/places.csv"
    fields, places = read_csv(target)
    _, existing = read_csv(directory / "merchant_spend_400_cleaned.csv")
    _, research = read_csv(directory / "merchant_spend_39_new_survey.csv")
    completed = [row for row in research if row["상태"].strip() == "완료" and row["1인 가격(원)"].strip()]
    remaining_file = directory / "merchant_spend_remaining_survey.csv"
    remaining = []
    if remaining_file.exists():
        _, survey = read_csv(remaining_file)
        remaining = [row for row in survey if row["상태"].strip() == "완료" and row["1인 가격(원)"].strip()]
    sources = existing + completed + remaining
    merged = merge_prices(places, sources)
    assert len(merged) == len(places)
    assert [{k: v for k, v in row.items() if k != "estimated_spend"} for row in merged] == [{k: v for k, v in row.items() if k != "estimated_spend"} for row in places]
    assert merge_prices(merged, sources) == merged
    write_csv(target, merged, fields)
    print(f"Places: {len(merged)}, existing survey: {len(existing)}, new research: {len(completed)}, remaining survey: {len(remaining)}, priced: {sum(bool(row['estimated_spend']) for row in merged)}")


if __name__ == "__main__":
    main()

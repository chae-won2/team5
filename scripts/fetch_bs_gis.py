"""bs.webasp.kr (부산광역시 생활데이터 상황판)의 비공개(인증 불필요) API를 호출해서
카드 소비 데이터(동 단위, 업종별)를 data/raw/bin/tour_consumption/ 에 CSV로 저장한다.

API: POST https://bs.webasp.kr/api/gis
layerType: "csm" (카드소비)
"""

import csv
import os
import time
import uuid
from datetime import date

import requests

API_URL = "https://bs.webasp.kr/api/gis"
SESSION_ID = uuid.uuid4().hex[:8]

# 부산광역시 16개 구/군 법정동 시군구코드
REGIONS = {
    26110: "중구", 26140: "서구", 26170: "동구", 26200: "영도구",
    26230: "부산진구", 26260: "동래구", 26290: "남구", 26320: "북구",
    26350: "해운대구", 26380: "사하구", 26410: "금정구", 26440: "강서구",
    26470: "연제구", 26500: "수영구", 26530: "사상구", 26710: "기장군",
}

MONTHS = [202601, 202602, 202603, 202604, 202605, 202606, 202607, 202608]

SPENDING_CATEGORY = [str(i) for i in range(1, 12)]
CATEGORY_LABELS = {
    "1": "여행/숙박", "2": "여가/문화", "3": "유통", "4": "음식/주점",
    "5": "음식료품", "6": "의류/잡화", "7": "미용", "8": "의료",
    "9": "교육", "10": "생활", "11": "자동차",
}

OUT_TOUR_CONSUMPTION = "data/raw/bin/tour_consumption"


def call_api(layer_type, region, ym):
    payload = {
        "layerType": layer_type,
        "region": region,
        "from": ym,
        "to": ym * 100 + 1,
        "isInflow": True,
        "spendingCategory": SPENDING_CATEGORY,
        "sessionId": SESSION_ID,
    }
    for attempt in range(3):
        try:
            r = requests.post(API_URL, json=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
            if data.get("ok"):
                return data["res"]
        except requests.RequestException:
            pass
        time.sleep(1 + attempt)
    return None


def fetch_tour_consumption():
    rows = []
    for ym in MONTHS:
        for region, gu_name in REGIONS.items():
            res = call_api("csm", region, ym)
            if not res:
                print(f"  실패: {ym} {gu_name}")
                continue
            for item in res.get("month_sub_region_spend", []):
                lon, lat = item["center"]
                row = {
                    "year_month": ym,
                    "gu": gu_name,
                    "dong_region_code": item["regionCode"],
                    "dong_name": item["regionName"],
                    "lon": lon,
                    "lat": lat,
                }
                for cat_id, label in CATEGORY_LABELS.items():
                    row[label] = item["count"].get(cat_id, 0)
                rows.append(row)
        print(f"  카드소비 {ym} 완료")

    os.makedirs(OUT_TOUR_CONSUMPTION, exist_ok=True)
    today = date.today().strftime("%Y%m%d")
    out_path = os.path.join(OUT_TOUR_CONSUMPTION, f"{today}_관광데이터랩_소비.csv")
    fieldnames = ["year_month", "gu", "dong_region_code", "dong_name", "lon", "lat"] + list(CATEGORY_LABELS.values())
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"저장: {out_path} ({len(rows)}행)")


if __name__ == "__main__":
    print("=== 카드소비(tour_consumption) 수집 시작 ===")
    fetch_tour_consumption()

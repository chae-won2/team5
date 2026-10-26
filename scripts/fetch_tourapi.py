"""한국관광공사 TourAPI(KorService2)에서 부산 지역 관광지/음식점 데이터를 받아
data/raw/bin/tourapi/ 에 원본 CSV로 저장한다.

contentTypeId: 12=관광지, 39=음식점
areaCode: 6=부산
"""

import csv
import os
import time
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://apis.data.go.kr/B551011/KorService2/areaBasedList2"
SERVICE_KEY = os.environ["TOURAPI_SERVICE_KEY"]
AREA_CODE = 6  # 부산
OUT_DIR = "data/raw/bin/tourapi"

CONTENT_TYPES = {
    "12": "관광지",
    "14": "문화시설",
    "15": "축제공연행사",
    "25": "여행코스",
    "28": "레포츠",
    "32": "숙박",
    "38": "쇼핑",
    "39": "음식점",
}

FIELDS = [
    "contentid", "contenttypeid", "title", "addr1", "addr2",
    "zipcode", "tel", "mapx", "mapy",
    "cat1", "cat2", "cat3", "sigungucode",
    "firstimage", "createdtime", "modifiedtime",
]


def fetch_all(content_type_id):
    items = []
    page = 1
    num_of_rows = 100
    while True:
        params = {
            "serviceKey": SERVICE_KEY,
            "numOfRows": num_of_rows,
            "pageNo": page,
            "MobileOS": "ETC",
            "MobileApp": "BusanFullCourse",
            "_type": "json",
            "areaCode": AREA_CODE,
            "contentTypeId": content_type_id,
        }
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        body = data["response"]["body"]
        total_count = body["totalCount"]
        page_items = body["items"].get("item", []) if body.get("items") else []
        items.extend(page_items)

        if len(items) >= total_count or not page_items:
            break
        page += 1
        time.sleep(0.2)

    return items


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    today = date.today().strftime("%Y%m%d")

    for content_type_id, label in CONTENT_TYPES.items():
        print(f"{label}(contentTypeId={content_type_id}) 수집 중...")
        items = fetch_all(content_type_id)
        print(f"  총 {len(items)}건")

        out_path = os.path.join(OUT_DIR, f"{today}_tourapi_{label}.csv")
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            for it in items:
                writer.writerow(it)
        print(f"  저장: {out_path}")


if __name__ == "__main__":
    main()

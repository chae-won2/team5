"""동백전 가맹점을 Kakao 키워드검색 API로 조회해서, Kakao 자체 업종분류(category_group_name,
category_name)를 받아온다. sangga 매칭보다 커버리지/정확도가 더 좋아서 카탈로그 보강용으로 쓴다.

하루 쿼터 10만 건이라 전체(15.8만)는 하루에 다 못 돈다. 주소 단위로 캐시(_kakao_category_cache.csv)에
이어 쓰기 때문에, 쿼터 초과로 멈춰도 다음날 다시 실행하면 이어서 진행된다.
"""

import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

MERCHANTS_PATH = "data/processed/merchants.csv"
CACHE_PATH = "data/processed/bin/_kakao_category_cache.csv"

API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
API_KEY = os.environ["KAKAO_REST_API_KEY"]
HEADERS = {"Authorization": f"KakaoAK {API_KEY}"}

MATCH_RADIUS_M = 100
MAX_WORKERS = 15
RETRY = 2

QUOTA_EXCEEDED = False


def load_cache():
    """"error"(네트워크 실패 등 일시적 오류)는 완료로 치지 않고 다음 실행에서 재시도한다.
    "ok"/"no_match"만 확정 결과라서 완료로 센다."""
    if not os.path.exists(CACHE_PATH):
        return set()
    df = pd.read_csv(CACHE_PATH, encoding="utf-8-sig")
    return set(df.loc[df["status"].isin(["ok", "no_match"]), "id"])


def append_cache_rows(rows):
    file_exists = os.path.exists(CACHE_PATH)
    with open(CACHE_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["id", "category_group_name", "category_name", "place_name", "status"])
        for r in rows:
            writer.writerow([r["id"], r["category_group_name"], r["category_name"], r["place_name"], r["status"]])


def fetch_one(merchant):
    global QUOTA_EXCEEDED
    if QUOTA_EXCEEDED:
        return None

    for attempt in range(RETRY):
        try:
            resp = requests.get(
                API_URL,
                params={"query": merchant.name, "x": merchant.lon, "y": merchant.lat,
                        "radius": MATCH_RADIUS_M, "size": 1},
                headers=HEADERS, timeout=10,
            )
        except requests.RequestException:
            time.sleep(1 + attempt)
            continue

        if resp.status_code == 429:
            QUOTA_EXCEEDED = True
            return None
        if resp.status_code != 200:
            body = resp.text[:200]
            # 실제 쿼터 초과 응답은 429가 아니라 400 + "API limit has been exceeded"로 온다.
            if "quota" in body.lower() or "limit has been exceeded" in body.lower():
                QUOTA_EXCEEDED = True
                return None
            time.sleep(1 + attempt)
            continue

        docs = resp.json().get("documents") or []
        if docs:
            d = docs[0]
            return {
                "id": merchant.id,
                "category_group_name": d.get("category_group_name") or "",
                "category_name": d.get("category_name") or "",
                "place_name": d.get("place_name") or "",
                "status": "ok",
            }
        return {"id": merchant.id, "category_group_name": "", "category_name": "", "place_name": "", "status": "no_match"}

    return {"id": merchant.id, "category_group_name": "", "category_name": "", "place_name": "", "status": "error"}


def main():
    merchants = pd.read_csv(MERCHANTS_PATH, encoding="utf-8-sig")
    cache = load_cache()
    todo = [m for m in merchants.itertuples() if m.id not in cache]
    print(f"전체: {len(merchants)}, 이미 처리됨: {len(cache)}, 이번에 할 것: {len(todo)}")

    done = 0
    buffer = []
    flush_every = 200

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_one, m): m for m in todo}
        for fut in as_completed(futures):
            r = fut.result()
            done += 1
            if r is None:
                continue
            buffer.append(r)
            if len(buffer) >= flush_every:
                append_cache_rows(buffer)
                buffer = []
                print(f"  진행: {done}/{len(todo)}")
            if QUOTA_EXCEEDED:
                print("쿼터 초과 감지, 중단합니다. 내일 다시 실행하면 이어서 진행됩니다.")
                break

    if buffer:
        append_cache_rows(buffer)
    print(f"완료 (이번 실행 {done}건 시도). 다시 실행하면 안 한 것만 이어서 합니다.")


if __name__ == "__main__":
    main()

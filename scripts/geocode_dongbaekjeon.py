"""동백전 가맹점 주소를 Kakao Local API로 지오코딩해서 GIS(GeoJSON) 파일을 만든다.

입력: data/raw/bin/dongbaekjeon/*.csv (가맹점 명 / 주소 / 데이터기준일자)
출력:
  data/processed/bin/dongbaekjeon_geocoded.csv   - 원본 + lon/lat
  data/processed/bin/dongbaekjeon.geojson        - Point FeatureCollection
  data/processed/bin/dongbaekjeon_geocode_failed.csv - 매칭 실패 주소 목록

주소 단위로 캐시(data/processed/bin/_geocode_cache.csv)를 유지해서, 중간에 끊겨도
이어서 돌릴 수 있다.
"""

import csv
import glob
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = "data/raw/bin/dongbaekjeon"
OUT_DIR = "data/processed/bin"
CACHE_PATH = os.path.join(OUT_DIR, "_geocode_cache.csv")
OUT_CSV = os.path.join(OUT_DIR, "dongbaekjeon_geocoded.csv")
OUT_GEOJSON = os.path.join(OUT_DIR, "dongbaekjeon.geojson")
OUT_FAILED = os.path.join(OUT_DIR, "dongbaekjeon_geocode_failed.csv")

API_URL = "https://dapi.kakao.com/v2/local/search/address.json"
API_KEY = os.environ["KAKAO_REST_API_KEY"]
HEADERS = {"Authorization": f"KakaoAK {API_KEY}"}

MAX_WORKERS = 20
RETRY = 3


def find_input_csv():
    paths = glob.glob(os.path.join(RAW_DIR, "*.csv"))
    if not paths:
        raise FileNotFoundError(f"{RAW_DIR} 에 csv 파일이 없습니다.")
    return paths[0]


def load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    df = pd.read_csv(CACHE_PATH, encoding="utf-8-sig")
    cache = {}
    for row in df.itertuples(index=False):
        cache[row.주소] = {
            "lon": row.lon if pd.notna(row.lon) else None,
            "lat": row.lat if pd.notna(row.lat) else None,
            "matched_address": row.matched_address if pd.notna(row.matched_address) else None,
            "status": row.status,
        }
    return cache


def append_cache_rows(rows):
    file_exists = os.path.exists(CACHE_PATH)
    with open(CACHE_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["주소", "lon", "lat", "matched_address", "status"])
        for addr, r in rows:
            writer.writerow([addr, r["lon"], r["lat"], r["matched_address"], r["status"]])


def geocode_one(addr):
    for attempt in range(RETRY):
        try:
            resp = requests.get(
                API_URL, params={"query": addr}, headers=HEADERS, timeout=10
            )
        except requests.RequestException:
            time.sleep(1 + attempt)
            continue

        if resp.status_code == 429:
            time.sleep(2 + attempt * 2)
            continue
        if resp.status_code != 200:
            time.sleep(1 + attempt)
            continue

        data = resp.json()
        docs = data.get("documents") or []
        if docs:
            d = docs[0]
            return {
                "lon": float(d["x"]),
                "lat": float(d["y"]),
                "matched_address": d["address_name"],
                "status": "ok",
            }
        return {"lon": None, "lat": None, "matched_address": None, "status": "no_match"}

    return {"lon": None, "lat": None, "matched_address": None, "status": "error"}


def strip_parenthetical(addr):
    # "부산광역시 연제구 화지로 84(거제동, 유림아시아드타워)" -> "부산광역시 연제구 화지로 84"
    idx = addr.find("(")
    return addr[:idx].strip() if idx != -1 else addr


def geocode_with_fallback(addr):
    r = geocode_one(addr)
    if r["status"] == "no_match":
        stripped = strip_parenthetical(addr)
        if stripped != addr:
            r2 = geocode_one(stripped)
            if r2["status"] == "ok":
                return r2
    return r


def main():
    input_csv = find_input_csv()
    print(f"입력 파일: {input_csv}")
    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    df = df.rename(columns={"가맹점 명": "store_name", "주소": "address", "데이터기준일자": "data_date"})

    os.makedirs(OUT_DIR, exist_ok=True)

    unique_addrs = sorted(df["address"].dropna().unique())
    print(f"전체 행: {len(df)}, 고유 주소: {len(unique_addrs)}")

    cache = load_cache()
    todo = [a for a in unique_addrs if a not in cache]
    print(f"캐시에 없는 주소(신규 지오코딩 대상): {len(todo)}")

    done = 0
    buffer = []
    flush_every = 200

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(geocode_with_fallback, a): a for a in todo}
        for fut in as_completed(futures):
            addr = futures[fut]
            r = fut.result()
            cache[addr] = r
            buffer.append((addr, r))
            done += 1
            if len(buffer) >= flush_every:
                append_cache_rows(buffer)
                buffer = []
                print(f"  진행: {done}/{len(todo)}")

    if buffer:
        append_cache_rows(buffer)
        print(f"  진행: {done}/{len(todo)} (완료)")

    # merge
    cache_df = pd.DataFrame(
        [
            {"address": a, "lon": v["lon"], "lat": v["lat"], "matched_address": v["matched_address"], "geocode_status": v["status"]}
            for a, v in cache.items()
        ]
    )
    merged = df.merge(cache_df, on="address", how="left")
    merged.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"저장: {OUT_CSV} ({len(merged)}행)")

    ok = merged["geocode_status"].eq("ok")
    print(f"지오코딩 성공: {ok.sum()} / {len(merged)} ({ok.mean()*100:.1f}%)")

    failed = merged[~ok][["store_name", "address", "data_date", "geocode_status"]].drop_duplicates()
    failed.to_csv(OUT_FAILED, index=False, encoding="utf-8-sig")
    print(f"실패 목록 저장: {OUT_FAILED} ({len(failed)}행, 고유주소 기준)")

    # geojson
    features = []
    for row in merged[ok].itertuples(index=False):
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row.lon, row.lat]},
                "properties": {
                    "store_name": row.store_name,
                    "address": row.address,
                    "matched_address": row.matched_address,
                    "data_date": row.data_date,
                },
            }
        )
    geojson = {"type": "FeatureCollection", "features": features}
    with open(OUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"저장: {OUT_GEOJSON} ({len(features)}개 포인트)")


if __name__ == "__main__":
    main()

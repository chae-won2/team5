"""여러 소스의 raw 데이터를 공통 스키마로 정제한다.

출력:
  merchants.csv          - 동백전 가맹점 (source, name, address, lon, lat, data_date). data/processed/ (서빙 입력)
  tourist_spots.csv      - TourAPI + 전통시장(부산) 통합 POI. data/processed/bin/
  consumption.csv        - 카드소비(관광데이터랩), long format. data/processed/bin/
  visitors.csv           - 외국인 지역별 방문자수, 연도 통합. data/processed/bin/
  commercial_density.csv - 상가(상권)정보, 행정동x업종대분류 집계. data/processed/bin/
"""

import glob
import hashlib
import os

import pandas as pd

RAW_DIR = "data/raw"
RAW_BIN_DIR = "data/raw/bin"
OUT_DIR = "data/processed"
OUT_BIN_DIR = "data/processed/bin"

POI_COLUMNS = ["id", "source", "source_id", "name", "category_major", "category_minor",
               "address", "lon", "lat", "data_date"]


def stable_id(*parts):
    """여러 필드를 합쳐 결정적(deterministic) md5 id를 만든다.
    같은 입력이면 재실행해도 항상 같은 id -> upsert 시 멱등성 보장."""
    key = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def latest_file(pattern):
    paths = sorted(glob.glob(pattern))
    if not paths:
        raise FileNotFoundError(pattern)
    return paths[-1]


def clean_merchants():
    path = os.path.join(OUT_BIN_DIR, "dongbaekjeon_geocoded.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df[df["geocode_status"] == "ok"].copy()
    out = pd.DataFrame({
        "id": [stable_id("dongbaekjeon", n, a) for n, a in zip(df["store_name"], df["address"])],
        "source": "dongbaekjeon",
        "source_id": None,
        "name": df["store_name"],
        "category_major": "동백전가맹점",
        "category_minor": None,
        "address": df["address"],
        "lon": df["lon"],
        "lat": df["lat"],
        "data_date": df["data_date"],
    })
    out = out.drop_duplicates(subset="id")
    out_path = os.path.join(OUT_DIR, "merchants.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장: {out_path} ({len(out)}행)")


def clean_tourist_spots():
    frames = []

    for path in glob.glob(os.path.join(RAW_BIN_DIR, "tourapi", "*_tourapi_*.csv")):
        label = os.path.basename(path).split("_tourapi_")[1].replace(".csv", "")
        df = pd.read_csv(path, encoding="utf-8-sig")
        frames.append(pd.DataFrame({
            "id": [stable_id("tourapi", cid) for cid in df["contentid"]],
            "source": "tourapi",
            "source_id": df["contentid"],
            "name": df["title"],
            "category_major": label,
            "category_minor": df["cat3"],
            "address": df["addr1"].fillna("") + " " + df["addr2"].fillna(""),
            "lon": df["mapx"],
            "lat": df["mapy"],
            "data_date": df["modifiedtime"].astype(str).str[:8],
        }))

    tm_path = os.path.join(RAW_BIN_DIR, "traditional_market", "전국전통시장표준데이터.csv")
    tm = pd.read_csv(tm_path, encoding="cp949")
    tm = tm[tm["소재지도로명주소"].str.startswith("부산", na=False)].copy()
    frames.append(pd.DataFrame({
        "id": [stable_id("traditional_market", n, a) for n, a in zip(tm["시장명"], tm["소재지도로명주소"])],
        "source": "traditional_market",
        "source_id": None,
        "name": tm["시장명"],
        "category_major": "전통시장",
        "category_minor": tm["시장유형"],
        "address": tm["소재지도로명주소"],
        "lon": tm["경도"],
        "lat": tm["위도"],
        "data_date": tm["데이터기준일자"],
    }))

    out = pd.concat(frames, ignore_index=True)[POI_COLUMNS]
    out = out.dropna(subset=["lon", "lat"]).drop_duplicates(subset="id")
    out_path = os.path.join(OUT_BIN_DIR, "tourist_spots.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장: {out_path} ({len(out)}행)")


def clean_consumption():
    path = latest_file(os.path.join(RAW_BIN_DIR, "tour_consumption", "*_관광데이터랩_소비.csv"))
    df = pd.read_csv(path, encoding="utf-8-sig")
    category_cols = ["여행/숙박", "여가/문화", "유통", "음식/주점", "음식료품",
                      "의류/잡화", "미용", "의료", "교육", "생활", "자동차"]
    id_cols = ["year_month", "gu", "dong_region_code", "dong_name", "lon", "lat"]
    long_df = df.melt(id_vars=id_cols, value_vars=category_cols,
                       var_name="category", value_name="amount_krw")
    long_df.insert(0, "id", [
        stable_id(r.dong_region_code, r.year_month, r.category)
        for r in long_df.itertuples()
    ])
    out_path = os.path.join(OUT_BIN_DIR, "consumption.csv")
    long_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장: {out_path} ({len(long_df)}행)")


def clean_visitors():
    frames = []
    for path in glob.glob(os.path.join(RAW_BIN_DIR, "visitors", "2*_외국인 지역별 방문자 수.csv")):
        period = os.path.basename(path).split("_")[0]
        df = pd.read_csv(path, encoding="utf-8-sig")
        df = df.rename(columns={"지역": "region", "외국인 방문자수": "foreign_visitors"})
        df["period"] = period
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)[["period", "region", "foreign_visitors"]]
    out.insert(0, "id", [stable_id(p, r) for p, r in zip(out["period"], out["region"])])
    out_path = os.path.join(OUT_BIN_DIR, "visitors.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장: {out_path} ({len(out)}행)")


def _find_sangga_file():
    paths = glob.glob(os.path.join(RAW_BIN_DIR, "sangga", "*.csv")) + glob.glob(os.path.join(RAW_BIN_DIR, "sangga", "*.zip"))
    if not paths:
        raise FileNotFoundError("sangga 원본(csv/zip)을 찾을 수 없습니다.")
    return sorted(paths)[-1]


def _read_sangga():
    path = _find_sangga_file()
    compression = "zip" if path.endswith(".zip") else None
    snapshot_date = os.path.basename(path).rsplit("_", 1)[-1].replace(".zip", "").replace(".csv", "")
    df = pd.read_csv(path, compression=compression, encoding="utf-8-sig")
    return df, snapshot_date


def clean_sangga_points():
    """merchants <-> sangga 근접매칭(카페/식당/기념품 카테고리 부여)용 포인트 데이터.
    원본 전체(86MB)를 매 요청마다 백엔드에서 읽긴 무거워서, 필요한 컬럼만 추려 저장한다."""
    df, _ = _read_sangga()
    out = df[["상호명", "상권업종대분류명", "상권업종중분류명", "경도", "위도"]].rename(columns={
        "상호명": "name", "상권업종대분류명": "category_major", "상권업종중분류명": "category_minor",
        "경도": "lon", "위도": "lat",
    })
    out["category_major"] = out["category_major"].str.strip()
    out["category_minor"] = out["category_minor"].str.strip()
    out = out.dropna(subset=["lon", "lat", "name"])
    out_path = os.path.join(OUT_BIN_DIR, "sangga_points.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장: {out_path} ({len(out)}행)")


def clean_commercial_density():
    df, snapshot_date = _read_sangga()

    grouped = df.groupby(["시군구명", "행정동명", "상권업종대분류명"]).agg(
        store_count=("상가업소번호", "count"),
        lon=("경도", "mean"),
        lat=("위도", "mean"),
    ).reset_index()
    grouped = grouped.rename(columns={
        "시군구명": "gu", "행정동명": "dong", "상권업종대분류명": "category_major",
    })
    grouped.insert(0, "snapshot_date", snapshot_date)
    grouped.insert(0, "id", [
        stable_id(r.gu, r.dong, r.category_major, snapshot_date)
        for r in grouped.itertuples()
    ])
    out_path = os.path.join(OUT_BIN_DIR, "commercial_density.csv")
    grouped.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장: {out_path} ({len(grouped)}행)")


def clean_busan_mat():
    """"부산의 맛" 인증 식당 목록. 전부 식당이라 카테고리 보강용으로 쓴다
    (좌표가 없어서 상호명+구 로만 merchants와 매칭한다)."""
    path = os.path.join(RAW_DIR, "dongbaekjeon", "2026_부산의맛_식당목록.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")
    out = df.rename(columns={"구군": "gu", "식당명": "name"})[["gu", "name"]]
    out_path = os.path.join(OUT_BIN_DIR, "busan_mat.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장: {out_path} ({len(out)}행)")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(OUT_BIN_DIR, exist_ok=True)
    clean_merchants()
    clean_tourist_spots()
    clean_consumption()
    clean_visitors()
    clean_commercial_density()
    clean_sangga_points()
    clean_busan_mat()
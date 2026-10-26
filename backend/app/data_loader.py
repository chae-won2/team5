"""CSV loaders; current recommendations use fin/places.csv through load_places().

Supabase stores anonymous exposure history separately in services/exposure.py.
Legacy source-data loaders remain for compatible endpoints and preprocessing.
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


@lru_cache(maxsize=1)
def load_merchants() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "merchants.csv", encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load_tourist_spots() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bin/tourist_spots.csv", encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load_consumption() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bin/consumption.csv", encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load_visitors() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bin/visitors.csv", encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load_commercial_density() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bin/commercial_density.csv", encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load_sangga_points() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bin/sangga_points.csv", encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load_kakao_categories() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bin/_kakao_category_cache.csv", encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load_busan_mat() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bin/busan_mat.csv", encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load_recommendation_places() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bin/recommendation_places.csv", encoding="utf-8-sig").fillna("")


@lru_cache(maxsize=1)
def load_opening_hours() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "fin/place_opening_hours.csv", encoding="utf-8-sig", dtype={"place_id": str})


@lru_cache(maxsize=1)
def load_places() -> pd.DataFrame:
    """Read the service catalog and attach verified display tags."""
    import math

    frame = pd.read_csv(DATA_DIR / "fin/places.csv", encoding="utf-8-sig", dtype={"id": str})
    required = {"id", "name", "category", "visit_type", "address", "lon", "lat", "admin_dong", "duration_min"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("Missing Place columns: " + ", ".join(sorted(missing)))
    if frame[list(required)].isna().any().any():
        raise ValueError("Required Place values must not be NULL")
    for column in ["id", "name", "category", "visit_type", "address", "admin_dong"]:
        if frame[column].astype(str).str.strip().eq("").any():
            raise ValueError("Required Place strings must not be blank")
    if not frame.id.is_unique:
        raise ValueError("Place IDs must be unique")
    types = {
        "general_restaurant": "식당", "quick_meal": "식당",
        "seated_cafe": "카페·디저트", "takeaway_dessert": "카페·디저트",
        "general_shopping": "쇼핑", "souvenir_shop": "쇼핑", "retail_store": "쇼핑",
        "scenic_spot": "관광명소", "exhibition_experience": "관광명소", "traditional_market": "관광명소",
    }
    if not frame.visit_type.map(types).eq(frame.category).all():
        raise ValueError("Invalid Place category/visit_type pair")
    if not frame.admin_dong.isin(["남포동", "광복동", "부평동", "대청동"]).all():
        raise ValueError("Place is outside the approved MVP dong")
    for column in ["lon", "lat", "duration_min", "estimated_spend"]:
        if column not in frame:
            continue
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        values = frame[column].dropna()
        if not values.map(math.isfinite).all():
            raise ValueError(column + " must be finite")
        if column in ["duration_min", "estimated_spend"] and (values < 0).any():
            raise ValueError(column + " must not be negative")
        if column == "duration_min" and (values % 1 != 0).any():
            raise ValueError(column + " must contain whole numbers")
    if (frame.duration_min <= 0).any():
        raise ValueError("duration_min must be positive")
    if not frame.lon.between(-180, 180).all() or not frame.lat.between(-90, 90).all():
        raise ValueError("Invalid Place coordinates")
    for column in frame.columns:
        if column not in ["lon", "lat", "duration_min"]:
            frame[column] = frame[column].astype(object).where(frame[column].notna(), None)
    from app.services.place_tags import busan_taste_matches
    taste = busan_taste_matches(frame, DATA_DIR.parent / "raw/dongbaekjeon/2026_부산의맛_식당목록.csv")
    frame["is_busan_taste"] = frame.id.isin(taste)
    frame["busan_taste_name"] = frame.id.map(taste).fillna("")
    return frame

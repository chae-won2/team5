"""출발지 키워드 검색과 지도 중심 좌표의 행정구역 조회를 프록시한다.
프론트에 Kakao 키를 노출하지 않으려고 백엔드를 거친다."""

import os
from functools import lru_cache

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query

load_dotenv()

router = APIRouter(prefix="/api/geocode", tags=["geocode"])

KAKAO_KEY = os.environ.get("KAKAO_REST_API_KEY")
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


@router.get("")
def search_location(query: str):
    if not KAKAO_KEY:
        raise HTTPException(500, "KAKAO_REST_API_KEY가 설정되어 있지 않습니다.")

    resp = requests.get(
        KAKAO_KEYWORD_URL,
        params={"query": query, "size": 5},
        headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "results": [
            {
                "name": d["place_name"],
                "address": d.get("road_address_name") or d.get("address_name"),
                "lon": float(d["x"]),
                "lat": float(d["y"]),
            }
            for d in data.get("documents", [])
        ]
    }


@lru_cache(maxsize=512)
def lookup_region(lat: float, lon: float):
    """Cache successful coordinate lookups; use administrative dong (H), not legal dong (B)."""
    if not KAKAO_KEY:
        raise HTTPException(503, "Region lookup is unavailable")
    try:
        response = requests.get(
            "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json",
            params={"x": lon, "y": lat, "input_coord": "WGS84"},
            headers={"Authorization": f"KakaoAK {KAKAO_KEY}"}, timeout=5,
        )
        response.raise_for_status()
        documents = response.json()["documents"]
        if not isinstance(documents, list):
            raise ValueError("Invalid region response")
        region = next((d for d in documents if d.get("region_type") == "H"), {})
        return {"district": region.get("region_2depth_name", ""), "dong": region.get("region_3depth_name", "")}
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, "Region lookup is temporarily unavailable") from None


@router.get("/region")
def map_region(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    return lookup_region(lat, lon)

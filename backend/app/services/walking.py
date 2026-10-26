"""TMAP pedestrian routing. Credentials stay on the backend."""
import math
import os
from pathlib import Path
from time import monotonic
from threading import Lock
from app.services.geo import haversine_m

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")


_retry_after = 0.0
_cooldown_lock = Lock()


def estimated_leg(start_lat, start_lon, end_lat, end_lon):
    # shortcut: distance factor does not model hills, barriers or pedestrian access.
    distance = float(haversine_m(start_lat, start_lon, end_lat, end_lon)) * 1.3
    seconds = distance / (4.5 * 1000 / 3600)
    return {"leg_minutes": round(seconds / 60, 1), "leg_seconds": seconds,
            "leg_distance_m": distance, "leg_path": [], "routing_source": "estimated"}


def pause_requests(seconds):
    global _retry_after
    with _cooldown_lock:
        _retry_after = max(_retry_after, monotonic() + seconds)


class WalkingError(Exception):
    pass


def walking_leg(start_lat, start_lon, end_lat, end_lon):
    key = os.getenv("TMAP_APP_KEY")
    if not key:
        raise WalkingError("TMAP 키가 설정되어 있지 않습니다.")
    if (start_lat, start_lon) == (end_lat, end_lon):
        return {"leg_minutes": 0, "leg_seconds": 0, "leg_distance_m": 0, "leg_path": []}
    with _cooldown_lock:
        cooling_down = monotonic() < _retry_after
    if cooling_down:
        return estimated_leg(start_lat, start_lon, end_lat, end_lon)
    try:
        response = requests.post(
            "https://apis.openapi.sk.com/tmap/routes/pedestrian",
            params={"version": "1"},
            headers={"appKey": key},
            json={"startX": start_lon, "startY": start_lat,
                  "endX": end_lon, "endY": end_lat,
                  "startName": "start", "endName": "end",
                  "reqCoordType": "WGS84GEO", "resCoordType": "WGS84GEO"},
            timeout=10,
        )
        if response.status_code in (401, 403):
            raise WalkingError("TMAP 인증에 실패했습니다. 앱 키와 TMAP 상품 연결 상태를 확인해주세요.")
        if response.status_code == 429:
            try:
                delay = float(response.headers.get("Retry-After", 300))
                if not math.isfinite(delay):
                    delay = 300
            except (TypeError, ValueError):
                delay = 300
            pause_requests(max(30, min(delay, 3600)))
            return estimated_leg(start_lat, start_lon, end_lat, end_lon)
        if response.status_code >= 500:
            pause_requests(30)
            return estimated_leg(start_lat, start_lon, end_lat, end_lon)
        if response.status_code >= 400:
            raise WalkingError("TMAP 도보 경로 요청을 처리하지 못했습니다.")
        response.raise_for_status()
        features = response.json()["features"]
        summary = next(f["properties"] for f in features if "totalTime" in f.get("properties", {}))
        seconds, distance = float(summary["totalTime"]), float(summary["totalDistance"])
        if not all(math.isfinite(v) and v >= 0 for v in (seconds, distance)):
            raise ValueError("Invalid routing summary")
        path = []
        for feature in features:
            geometry = feature.get("geometry", {})
            if geometry.get("type") == "LineString":
                path.extend([[lat, lon] for lon, lat in geometry["coordinates"]])
        return {"leg_minutes": round(seconds / 60, 1), "leg_seconds": seconds, "leg_distance_m": distance, "leg_path": path, "routing_source": "tmap"}
    except WalkingError:
        raise
    except (requests.RequestException, ValueError, KeyError, TypeError, StopIteration):
        # Never forward upstream exceptions/headers containing credentials.
        pause_requests(30)
        return estimated_leg(start_lat, start_lon, end_lat, end_lon)

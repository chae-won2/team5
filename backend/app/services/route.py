"""User-ordered courses, walking constraints, optional time overruns and exposure rotation."""

import pandas as pd

from app.services.geo import haversine_m
from app.services.walking import walking_leg
from app.services.exposure import rotate
from app.services.opening_hours import status_at
from app.services.place_labels import official_labels, romanized_name

CATEGORIES = ["식당", "카페·디저트", "관광명소", "쇼핑"]
WALK_SPEED_MPS = 4.5 * 1000 / 3600
WALK_DISTANCE_FACTOR = 1.3


def estimate_walk_minutes(distance_m):
    return distance_m * WALK_DISTANCE_FACTOR / WALK_SPEED_MPS / 60


MAX_LEG_WALK_MINUTES = 20
MAX_OVERRUN_MINUTES = 10


class RouteConstraintError(ValueError):
    pass


MIN_STOP_SEPARATION_M = 30  # 이보다 가까우면 같은 상가 다른 호실/상호 취급, 하나만 남긴다
PER_CATEGORY_POOL_SIZE = 20  # 카테고리 하나가 전체를 독점하지 못하게, 카테고리별로 이만큼만 후보군에 넣는다


def nearest_candidates(catalog: pd.DataFrame, start_lat, start_lon, categories=None, limit=5):
    """Build a capped, spatially deduplicated distance pool.

    This is candidate retrieval, not the final exposure-rotation ordering.
    """
    pool = catalog
    if categories:
        pool = pool[pool["category"].isin(categories)]
    if pool.empty:
        return []

    pool = pool.copy()
    pool["distance_m"] = haversine_m(start_lat, start_lon, pool["lat"].to_numpy(), pool["lon"].to_numpy())
    pool = pool.sort_values("distance_m")

    capped_parts = [g.head(PER_CATEGORY_POOL_SIZE) for _, g in pool.groupby("category")]
    capped = pd.concat(capped_parts).sort_values("distance_m").to_dict("records")

    deduped = []
    for cand in capped:
        too_close = any(
            haversine_m(cand["lat"], cand["lon"], kept["lat"], kept["lon"]) < MIN_STOP_SEPARATION_M
            for kept in deduped if cand["category"] == kept["category"]
        )
        if not too_close:
            deduped.append(cand)
        if len(deduped) >= limit * 4:
            break

    return deduped


def _is_closed(place_id, opening):
    """True only when the researched schedule confirms the place is shut; unknown places are never excluded."""
    return bool(opening) and status_at(place_id, *opening) == "closed"


def _place_fields(stop, opening=None, language=None):
    spend = stop.get("estimated_spend")
    official = official_labels(stop["id"], stop["name"], stop["address"], language) if language else {}
    return {
        "is_busan_taste": bool(stop.get("is_busan_taste", False)),
        "busan_taste_name": stop.get("busan_taste_name", ""),
        "duration_min": stop["duration_min"],
        "estimated_spend": None if pd.isna(spend) else spend,
        "duration_basis": stop.get("duration_basis", "place_default"),
        "id": stop["id"],
        "name": stop["name"],
        "official_name": official.get("name", ""),
        "official_names": {lang: labels["name"] for lang in ("en", "ja", "zh-TW")
                           if (labels := official_labels(stop["id"], stop["name"], stop["address"], lang)).get("name")},
        "romanized_name": romanized_name(stop["name"]),
        "category": "카페/디저트" if stop["category"] == "카페·디저트" else stop["category"],
        "address": stop["address"],
        "lon": stop["lon"],
        "lat": stop["lat"],
        "data_date": stop["data_date"],
        "place_type": stop["place_type"],
        "payment_status": stop["payment_status"],
        "source": stop["source"],
        "opening_status": status_at(stop["id"], *opening) if opening else "unknown",
    }


def route_legs():
    """Reuse directed legs only within this request; do not persist routing data."""
    cache = {}
    def leg(a_lat, a_lon, b_lat, b_lon):
        key = (a_lat, a_lon, b_lat, b_lon)
        if key not in cache:
            cache[key] = walking_leg(*key)
        return cache[key]
    return leg


def walking_seconds(leg):
    return leg.get("leg_seconds", leg["leg_minutes"] * 60)


def within_walk_limit(leg):
    return walking_seconds(leg) <= MAX_LEG_WALK_MINUTES * 60


def recommend_route(catalog, start_lat, start_lon, categories=None, max_minutes=90,
                    return_to_start=False, selected_only=False, opening=None, language=None):
    selected = {"카페·디저트" if c == "카페/디저트" else c for c in (categories or [])}
    allowed = selected if selected_only and selected else selected | {"관광명소"} if selected else set(CATEGORIES)
    candidates = nearest_candidates(catalog, start_lat, start_lon, limit=20)
    remaining = [p for p in candidates if p["category"] in allowed and not _is_closed(p["id"], opening)]
    stops, counts, origin = [], {}, {}
    current_lat, current_lon = start_lat, start_lon
    used, return_leg = 0.0, None
    leg = route_legs()
    primary_available = not selected or any(p["category"] in selected for p in remaining)
    if not primary_available:
        remaining = []
    # shortcut: greedily build a feasible course; this does not guarantee a globally optimal tour.
    while remaining:
        remaining = [p for p in remaining if used + p["duration_min"] <= max_minutes]
        if not remaining:
            break
        last_category = stops[-1]["category"] if stops else None
        eligible = [p for p in remaining if p["category"] == "관광명소" or p["category"] != last_category]
        if not eligible:
            break
        eligible.sort(key=lambda p: (
            0 if selected and p["category"] in selected and not counts.get(p["category"]) else 1,
            counts.get(p["category"], 0),
            haversine_m(current_lat, current_lon, p["lat"], p["lon"])))
        stop = eligible[0]
        remaining.remove(stop)
        incoming = leg(current_lat, current_lon, stop["lat"], stop["lon"])
        origin_leg = incoming
        if not within_walk_limit(incoming):
            continue
        back = leg(stop["lat"], stop["lon"], start_lat, start_lon) if return_to_start else None
        next_used = round(used + incoming["leg_minutes"] + stop["duration_min"], 1)
        if next_used + (back["leg_minutes"] if back else 0) > max_minutes:
            continue
        stops.append({**_place_fields(stop, opening, language), **incoming, "order": len(stops) + 1,
                      "origin_walk_minutes": origin_leg["leg_minutes"]})
        used, return_leg = next_used, back
        current_lat, current_lon = stop["lat"], stop["lon"]
        counts[stop["category"]] = counts.get(stop["category"], 0) + 1
    result = summarize_route(stops, max_minutes, return_leg)
    result["return_to_start"] = return_to_start
    chosen = {s["id"] for s in stops}
    alternatives = []
    # Verify a few alternatives per category even when that category was not selected.
    for category in CATEGORIES:
        found = 0
        for place in candidates:
            if place["category"] != category or place["id"] in chosen or _is_closed(place["id"], opening):
                continue
            origin_leg = origin.setdefault(place["id"], leg(start_lat, start_lon, place["lat"], place["lon"]))
            if not within_walk_limit(origin_leg):
                continue
            alternatives.append({**_place_fields(place, opening, language), "origin_walk_minutes": origin_leg["leg_minutes"]})
            found += 1
            if found == 3:
                break
    result["alternatives"] = alternatives
    if not primary_available:
        result["message"] = "선택한 관심 업종의 장소는 아직 준비 중이에요. 다른 업종을 선택해주세요."
    elif not stops:
        result["message"] = "출발지 도보 20분 이내에서 여행 시간에 맞는 코스를 찾지 못했어요. 출발지나 시간을 바꿔주세요."
    elif selected and "쇼핑" in selected and not any(p["category"] == "쇼핑" for p in candidates):
        result["message"] = "쇼핑 장소는 준비 중이라 다른 관심 업종을 중심으로 구성했어요."
    return result


def summarize_route(stops, max_minutes, return_leg=None):
    walk_seconds = sum(walking_seconds(s) for s in stops) + (walking_seconds(return_leg) if return_leg else 0)
    stay = sum(s["duration_min"] for s in stops)
    total_seconds = walk_seconds + stay * 60
    return {"stops": stops, "total_walk_minutes": round(walk_seconds / 60, 1), "total_stay_minutes": round(stay, 1),
            "total_minutes": round(total_seconds / 60, 1), "total_seconds": total_seconds,
            "over_budget": total_seconds > max_minutes * 60, "routing_source": "tmap",
            "return_leg": return_leg, "return_to_start": return_leg is not None,
            "max_leg_walk_minutes": MAX_LEG_WALK_MINUTES, "max_overrun_minutes": MAX_OVERRUN_MINUTES}


def recalculate_route(start_lat, start_lon, stops, max_minutes=90, return_to_start=False, leg=None):
    leg = leg or route_legs()
    current_lat, current_lon = start_lat, start_lon
    result = []
    for i, stop in enumerate(stops, start=1):
        incoming = leg(current_lat, current_lon, stop["lat"], stop["lon"])
        if not within_walk_limit(incoming):
            raise RouteConstraintError("직전 장소에서 도보 20분이 넘는 장소예요. 다른 장소를 선택해주세요.")
        result.append({**stop, **incoming, "order": i})
        current_lat, current_lon = stop["lat"], stop["lon"]
    back = leg(current_lat, current_lon, start_lat, start_lon) if return_to_start and result else None
    summary = summarize_route(result, max_minutes, back)
    if summary["total_seconds"] > (max_minutes + MAX_OVERRUN_MINUTES) * 60:
        raise RouteConstraintError("전체 일정은 설정한 여행시간보다 최대 10분까지만 초과할 수 있어요. 장소를 줄이거나 여행시간을 늘려주세요.")
    return summary


def next_places(catalog, start_lat, start_lon, stops, category=None, max_minutes=90, return_to_start=False, *, record_candidates=False, opening=None, language=None):
    """Keep user order, allow 20-minute legs and at most a 10-minute total overrun."""
    leg = route_legs()
    result = recalculate_route(start_lat, start_lon, stops, max_minutes, return_to_start, leg=leg)
    result["alternatives"] = []
    if record_candidates:
        result["_candidate_snapshot"] = []
    result["remaining_minutes"] = round(max_minutes - result["total_minutes"], 1)
    if not category or len(stops) >= 24:
        return result
    category = "카페·디저트" if category == "카페/디저트" else category
    current = stops[-1] if stops else {"lat": start_lat, "lon": start_lon}
    used_ids = {s["id"] for s in stops}
    pool = catalog[(catalog.category == category) & ~catalog.id.isin(used_ids)]
    candidates = nearest_candidates(pool, current["lat"], current["lon"], [category], limit=20)
    used_seconds = result["total_seconds"] - (walking_seconds(result["return_leg"]) if result["return_leg"] else 0)
    for place in candidates:
        if _is_closed(place["id"], opening):
            continue
        incoming = leg(current["lat"], current["lon"], place["lat"], place["lon"])
        if not within_walk_limit(incoming):
            continue
        back = leg(place["lat"], place["lon"], start_lat, start_lon) if return_to_start else None
        seconds = used_seconds + walking_seconds(incoming) + place["duration_min"] * 60 + (walking_seconds(back) if back else 0)
        if seconds > (max_minutes + MAX_OVERRUN_MINUTES) * 60:
            continue
        total = round(seconds / 60, 1)
        if record_candidates:
            result["_candidate_snapshot"].append({"id": place["id"], "leg_seconds": walking_seconds(incoming),
                "duration_min": place["duration_min"], "projected_total_seconds": seconds})
        result["alternatives"].append({**_place_fields(place, opening, language), **incoming,
            "projected_total_minutes": total,
            "over_budget": seconds > max_minutes * 60})
    # shortcut: rotate within the existing nearest-20 pool, not the entire catalog.
    # Exposure rotation is a 동백전 가맹점 fairness mechanism; attractions stay in distance order.
    fitting = [p for p in result["alternatives"] if not p["over_budget"]]
    overruns = [p for p in result["alternatives"] if p["over_budget"]]
    if category == "관광명소":
        result["alternatives"] = (fitting + overruns)[:3]
    else:
        result["alternatives"] = (rotate(fitting) + rotate(overruns))[:3]
    return result

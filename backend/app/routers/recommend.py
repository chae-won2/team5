import logging
import time
from uuid import UUID
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.data_loader import load_places
from app.services.route import recommend_route, recalculate_route, next_places, RouteConstraintError
from app.services.walking import WalkingError
from app.services.exposure import issue, acknowledge, ExposureStorageError
from app.services.opening_hours import resolve_context

router = APIRouter(prefix="/api/recommend", tags=["recommend"])
logger = logging.getLogger("recommend")
TIME_PATTERN = r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class RecommendRequest(BaseModel):
    start_lat: float = Field(ge=-90, le=90)
    start_lon: float = Field(ge=-180, le=180)
    return_to_start: bool = False
    selected_only: bool = False
    categories: Optional[List[Literal["식당", "카페/디저트", "카페·디저트", "관광명소", "쇼핑"]]] = None
    max_minutes: int = Field(default=90, ge=30, le=360)


class RecalculateRequest(BaseModel):
    start_lat: float = Field(ge=-90, le=90)
    start_lon: float = Field(ge=-180, le=180)
    return_to_start: bool = False
    stop_ids: List[str] = Field(min_length=1, max_length=24)
    max_minutes: int = Field(default=90, ge=30, le=360)


class NextPlaceRequest(BaseModel):
    start_lat: float = Field(ge=-90, le=90)
    start_lon: float = Field(ge=-180, le=180)
    return_to_start: bool = False
    max_minutes: int = Field(default=90, ge=30, le=360)
    stop_ids: List[str] = Field(default_factory=list, max_length=24)
    category: Optional[Literal["식당", "카페/디저트", "카페·디저트", "관광명소", "쇼핑"]] = None
    departure_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    departure_time: Optional[str] = Field(default=None, pattern=TIME_PATTERN)


@router.post("/next")
def recommend_next(req: NextPlaceRequest):
    catalog = load_places()
    indexed = catalog.set_index("id")
    if len(set(req.stop_ids)) != len(req.stop_ids) or any(i not in indexed.index for i in req.stop_ids):
        raise HTTPException(422, "유효한 장소 ID를 중복 없이 선택해주세요.")
    try:
        opening = resolve_context(req.departure_date, req.departure_time)
    except ValueError:
        raise HTTPException(422, "유효한 출발 날짜가 아니에요.") from None
    from app.services.route import _place_fields
    stops = [_place_fields({**indexed.loc[i].to_dict(), "id": i}, opening) for i in req.stop_ids]
    try:
        result = next_places(catalog, req.start_lat, req.start_lon, stops, req.category, req.max_minutes, req.return_to_start, record_candidates=True, opening=opening)
        candidates = result.pop('_candidate_snapshot')
        if req.category:
            result['recommendation_id'] = issue(result['alternatives'], candidates=candidates, policy='rotation',
                context={'category': req.category, 'max_minutes': req.max_minutes,
                         'return_to_start': req.return_to_start, 'selected_place_ids': req.stop_ids,
                         'max_leg_walk_minutes': 20, 'max_overrun_minutes': 10,
                         'history_window_days': 7, 'similar_extra_seconds': 120,
                         'candidate_pool_limit': 20})
        return result
    except ExposureStorageError as exc:
        raise HTTPException(503, str(exc)) from None
    except RouteConstraintError as exc:
        raise HTTPException(422, str(exc)) from None
    except WalkingError as exc:
        raise HTTPException(502, str(exc)) from None


class ImpressionRequest(BaseModel):
    recommendation_id: UUID


@router.post('/impressions')
def impression(req: ImpressionRequest):
    try:
        return {'recorded': acknowledge(req.recommendation_id)}
    except ExposureStorageError as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError:
        raise HTTPException(404, '추천 목록이 만료되었거나 존재하지 않습니다.') from None


@router.post("/recalculate")
def recalculate(req: RecalculateRequest):
    catalog = load_places().set_index("id")
    if len(set(req.stop_ids)) != len(req.stop_ids) or any(i not in catalog.index for i in req.stop_ids):
        raise HTTPException(422, "유효한 장소 ID를 중복 없이 선택해주세요.")
    from app.services.route import _place_fields
    stops = [_place_fields({**catalog.loc[i].to_dict(), "id": i}) for i in req.stop_ids]
    try:
        result = recalculate_route(req.start_lat, req.start_lon, stops, req.max_minutes, req.return_to_start)
        return result
    except RouteConstraintError as exc:
        raise HTTPException(422, str(exc)) from None
    except WalkingError as exc:
        raise HTTPException(502, str(exc)) from None


@router.post("")
def recommend(req: RecommendRequest):
    t0 = time.perf_counter()
    try:
        result = recommend_route(
            catalog=load_places(),
            start_lat=req.start_lat,
            start_lon=req.start_lon,
            categories=req.categories,
            max_minutes=req.max_minutes,
            return_to_start=req.return_to_start,
            selected_only=req.selected_only,
        )
    except RouteConstraintError as exc:
        raise HTTPException(422, str(exc)) from None
    except WalkingError as exc:
        raise HTTPException(502, str(exc)) from None
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(
        "recommend start=(%.5f,%.5f) categories=%s max_minutes=%d -> %d stops in %sms",
        req.start_lat, req.start_lon, req.categories, req.max_minutes, len(result["stops"]), elapsed_ms,
    )
    return result

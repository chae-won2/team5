"""Open/closed lookup from the researched weekly schedule (place_opening_hours.csv).

Only places with a recorded weekday entry get a definite answer; everything
else is "unknown" per the data contract (no guessing closed or 24h).
"""
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.data_loader import load_opening_hours

SEOUL = ZoneInfo("Asia/Seoul")


def _minutes(hhmm):
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


@lru_cache(maxsize=1)
def _index():
    idx = {}
    for row in load_opening_hours().itertuples(index=False):
        idx.setdefault((row.place_id, int(row.weekday)), []).append(row)
    return idx


def status_at(place_id, weekday, minutes_of_day):
    """weekday: Monday=0 .. Sunday=6 (date.weekday()). minutes_of_day: 0-1439."""
    idx = _index()
    rows = idx.get((place_id, weekday), [])
    for row in rows:
        if row.status != "open":
            continue
        start = _minutes(row.opens_at)
        if row.closes_next_day == 1:
            if minutes_of_day >= start:
                return "open"
        elif start <= minutes_of_day < _minutes(row.closes_at):
            return "open"
    for row in idx.get((place_id, (weekday - 1) % 7), []):
        if row.status == "open" and row.closes_next_day == 1 and minutes_of_day < _minutes(row.closes_at):
            return "open"
    if any(row.status == "closed" for row in rows):
        return "closed"
    return "unknown"


def resolve_context(departure_date, departure_time):
    """Fill in missing date/time with the current Asia/Seoul clock, mirroring the
    frontend's "automatic" departure (busanClock()). Returns (weekday, minutes_of_day)."""
    now = datetime.now(SEOUL)
    day = datetime.strptime(departure_date, "%Y-%m-%d").date() if departure_date else now.date()
    minutes = _minutes(departure_time) if departure_time else now.hour * 60 + now.minute
    return day.weekday(), minutes

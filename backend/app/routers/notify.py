import json
from pathlib import Path
import logging
import math
import os
import smtplib

import requests
from email.mime.text import MIMEText
from typing import List, Literal, Optional
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.place_labels import official_labels, romanized_name

load_dotenv()

router = APIRouter(prefix="/api/notify", tags=["notify"])
logger = logging.getLogger("notify")

EMAIL_COPY = json.loads((Path(__file__).resolve().parents[1] / "services/email_translations.json").read_text(encoding="utf-8"))

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


class RouteStop(BaseModel):
    id: Optional[str] = None
    order: int
    name: str
    category: str
    address: str
    leg_minutes: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    routing_source: Optional[Literal["tmap", "estimated"]] = None
    leg_seconds: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    duration_min: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    lat: Optional[float] = None
    lon: Optional[float] = None


class EmailRequest(BaseModel):
    language: Literal["ko", "en", "ja", "zh-TW"] = "ko"
    email: str
    email_consent: bool = False
    return_to_start: bool = False
    departure_time: Optional[str] = Field(default=None, min_length=5, max_length=5, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    return_minutes: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    return_estimated: bool = False
    return_seconds: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    total_minutes: Optional[float] = None
    max_minutes: int = Field(default=360, ge=30, le=360)
    start_label: Optional[str] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    stops: List[RouteStop]


def build_course_link(req: EmailRequest) -> Optional[str]:
    if not req.stops or req.start_lat is None or req.start_lon is None or any(not s.id for s in req.stops):
        return None
    params = {"start": f"{req.start_lat},{req.start_lon}", "stop": [s.id for s in req.stops],
              "minutes": req.max_minutes, "return": "1" if req.return_to_start else "0", "lang": req.language}
    if req.departure_time:
        params["depart"] = req.departure_time
    if req.start_label:
        params["label"] = req.start_label
    site = os.environ.get("PUBLIC_SITE_URL", "https://busan-full-course.onrender.com").rstrip("/")
    return site + "/?" + urlencode(params, doseq=True)


def format_duration(minutes, text):
    if minutes is None:
        return "-"
    hours, remaining = divmod(math.ceil(minutes), 60)
    parts = []
    if hours:
        parts.append(text["hours"].format(n=hours))
    if remaining or not hours:
        parts.append(text["minutes"].format(n=remaining))
    return " ".join(parts)


def schedule_range(departure_time, start_seconds, end_seconds, text):
    hour, minute = map(int, departure_time.split(":"))
    def clock(seconds):
        value = hour * 60 + minute + math.ceil(seconds / 60 - 1e-9)
        days, day_minute = divmod(value, 1440)
        h, m = divmod(day_minute, 60)
        value = f"{h:02d}:{m:02d}"
        return text["next_day"].format(time=value) if days else value
    return clock(start_seconds) + " ~ " + clock(end_seconds)


def build_email_body(req: EmailRequest) -> str:
    text = EMAIL_COPY[req.language]
    lines = [text["total"].format(n=format_duration(req.total_minutes, text)), ""]
    if req.return_estimated or any(s.routing_source == "estimated" for s in req.stops):
        lines.extend([text["walking_estimate_notice"], ""])
    timed = bool(req.departure_time) and all(
        (s.leg_seconds is not None or s.leg_minutes is not None) and s.duration_min is not None
        for s in req.stops)
    elapsed = 0.0
    if req.departure_time:
        lines.extend([text["departure"].format(time=req.departure_time), ""])
    missing_official = False
    for stop in req.stops:
        category = text["categories"].get(stop.category, stop.category)
        official = official_labels(stop.id, stop.name, stop.address, req.language)
        display_name = official.get("name") or stop.name
        display_address = official.get("address") or stop.address
        visit_window = ""
        if timed:
            walk_start = elapsed
            elapsed += stop.leg_seconds if stop.leg_seconds is not None else stop.leg_minutes * 60
            walk_window = schedule_range(req.departure_time, walk_start, elapsed, text)
            lines.append(text["walk"].format(n=format_duration((elapsed-walk_start)/60, text)) + f" ({walk_window})")
            visit_start = elapsed
            elapsed += stop.duration_min * 60
            visit_window = " (" + schedule_range(req.departure_time, visit_start, elapsed, text) + ")"
        lines.append(f"{stop.order}. {display_name}{visit_window} ({category})")
        if display_name != stop.name:
            lines.append(f"   {text['native_name']}: {stop.name}")
        if req.language != "ko" and not official.get("name") and (reading := romanized_name(stop.name)):
            lines.append(f"   {text['romanized_name']}: {reading}")
        lines.append(f"   {text['address']}: {display_address}")
        if display_address != stop.address:
            lines.append(f"   {text['native_address']}: {stop.address}")
        if req.language != "ko" and (not official.get("name") or not official.get("address")):
            missing_official = True
        if stop.leg_minutes is not None and not timed:
            lines.append("   " + text["walk"].format(n=format_duration(stop.leg_minutes, text)))
        if stop.duration_min is not None:
            lines.append("   " + text["stay"].format(n=format_duration(stop.duration_min, text)))
        lines.append("")
    if req.return_to_start:
        value = text["return"].format(n=format_duration(req.return_minutes, text))
        seconds = req.return_seconds if req.return_seconds is not None else req.return_minutes * 60 if req.return_minutes is not None else None
        if timed and seconds is not None:
            value += " (" + schedule_range(req.departure_time, elapsed, elapsed+seconds, text) + ")"
        lines.append(value)
    course_link = build_course_link(req)
    if course_link:
        lines.extend([text["course_link"] + ": " + course_link, ""])
    if missing_official:
        lines.append(text["official_fallback"])
    lines.append(text["source"])
    return "\n".join(lines)


@router.post("/email")
def send_route_email(req: EmailRequest):
    if not req.email_consent:
        raise HTTPException(400, EMAIL_COPY[req.language]["consent"])
    if os.environ.get("EMAIL_DELIVERY_ENABLED", "true").lower() == "false":
        raise HTTPException(503, EMAIL_COPY[req.language]["error"])
    brevo_key = os.environ.get("BREVO_API_KEY")
    if brevo_key:
        sender = os.environ.get("EMAIL_FROM") or GMAIL_ADDRESS
        if not sender:
            raise HTTPException(503, EMAIL_COPY[req.language]["error"])
        try:
            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": brevo_key, "accept": "application/json"},
                json={"sender": {"email": sender, "name": "Busan Full Course"},
                      "to": [{"email": req.email}],
                      "subject": EMAIL_COPY[req.language]["subject"],
                      "textContent": build_email_body(req)},
                timeout=15,
            )
            response.raise_for_status()
            if not response.json().get("messageId"):
                raise ValueError("Missing delivery acknowledgement")
        except (requests.RequestException, ValueError) as error:
            # Provider response bodies can contain recipient details; do not log them.
            logger.error("Brevo delivery failed: %s", type(error).__name__)
            raise HTTPException(502, EMAIL_COPY[req.language]["error"]) from None
        return {"ok": True, "sent": True}
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.info("Email sending is not configured; request skipped")
        return {"ok": True, "sent": False, "reason": "gmail credentials not configured yet"}

    msg = MIMEText(build_email_body(req))
    msg["Subject"] = EMAIL_COPY[req.language]["subject"]
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = req.email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, [req.email], msg.as_string())
    except (smtplib.SMTPException, OSError) as e:
        logger.error("failed to send email via gmail smtp: %s", e)
        raise HTTPException(status_code=502, detail=EMAIL_COPY[req.language]["error"])

    return {"ok": True, "sent": True}

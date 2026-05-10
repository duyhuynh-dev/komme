from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from app.core.config import get_settings
from app.models.contracts import CandidateEvent, RetrievalQuery

NYC_TZ = ZoneInfo("America/New_York")


class NYCEventsConnector:
    source_name = "nyc_events"

    def skip_reason(self) -> str | None:
        if not get_settings().nyc_events_api_url:
            return "missing_nyc_events_api_url"
        return None

    async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
        settings = get_settings()
        if self.skip_reason():
            return []

        headers: dict[str, str] = {}
        params: dict[str, object] = {"limit": 50}
        if settings.nyc_events_api_key:
            headers["Ocp-Apim-Subscription-Key"] = settings.nyc_events_api_key
            params["$$app_token"] = settings.nyc_events_api_key

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(settings.nyc_events_api_url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

        return [
            candidate
            for item in _event_items(payload)
            if (candidate := _candidate_from_nyc_event(item, query, source_base_url=settings.nyc_events_api_url)) is not None
        ]


def _event_items(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("events", "items", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _candidate_from_nyc_event(item: dict, query: RetrievalQuery, *, source_base_url: str) -> CandidateEvent | None:
    title = _first_string(item, "title", "name", "event_name", "event")
    venue_name = _first_string(item, "venue_name", "location_name", "park_name", "site_name", "place")
    address = _first_string(item, "address", "location", "location_description", "site_address")
    starts_at = _normalize_event_datetime(item)
    latitude, longitude = _coordinates(item)

    if not title or not venue_name or not address or not starts_at or latitude is None or longitude is None:
        return None

    source_url = _first_string(item, "url", "event_url", "link", "website") or source_base_url
    category = _first_string(item, "category", "event_type", "type", "program_type") or query.category
    city = _first_string(item, "city") or "New York City"
    state = _first_string(item, "state") or "NY"
    event_id = _first_string(item, "id", "event_id", "objectid") or f"{title}:{starts_at}"

    return CandidateEvent(
        source="nyc_events",
        source_kind="open_data",
        source_event_key=f"nyc_events:{event_id}",
        venue_name=venue_name,
        neighborhood=city,
        address=address,
        city=city,
        state=state,
        title=title,
        summary=_first_string(item, "description", "summary", "details"),
        category=category,
        starts_at=starts_at,
        latitude=latitude,
        longitude=longitude,
        ticket_url=source_url,
        source_url=source_url,
        source_base_url=_source_origin(source_base_url),
        source_confidence=0.74,
        topic_keys=["creative_meetups"] if category.lower() in {"community", "parks", "free"} else [],
        tags=[value for value in [query.query, category, "free", "nyc official"] if value],
    )


def _normalize_event_datetime(item: dict) -> str | None:
    raw = _first_string(item, "starts_at", "start_datetime", "start_date_time", "start_time", "date_time")
    if raw:
        parsed = _parse_datetime(raw)
        if parsed:
            return parsed

    date_value = _first_string(item, "start_date", "date", "event_date")
    time_value = _first_string(item, "time_start", "start_time", "time")
    if date_value and time_value:
        return _parse_datetime(f"{date_value} {time_value}")
    if date_value:
        return _parse_datetime(f"{date_value} 12:00 PM")
    return None


def _parse_datetime(value: str) -> str | None:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None

    if parsed is None:
        for date_format in ("%Y-%m-%d %I:%M %p", "%m/%d/%Y %I:%M %p", "%Y-%m-%d %H:%M"):
            try:
                parsed = datetime.strptime(value.strip(), date_format)
                break
            except ValueError:
                continue

    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=NYC_TZ)
    return parsed.astimezone(UTC).isoformat()


def _coordinates(item: dict) -> tuple[float | None, float | None]:
    latitude = _coerce_coordinate(_first_string(item, "latitude", "lat"))
    longitude = _coerce_coordinate(_first_string(item, "longitude", "lon", "lng"))
    if latitude is not None and longitude is not None:
        return latitude, longitude

    location = item.get("location")
    if isinstance(location, dict):
        latitude = _coerce_coordinate(location.get("latitude") or location.get("lat"))
        longitude = _coerce_coordinate(location.get("longitude") or location.get("lon") or location.get("lng"))
        return latitude, longitude
    return None, None


def _first_string(item: dict, *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return None


def _coerce_coordinate(value: object) -> float | None:
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None
    if coordinate == 0.0:
        return None
    return coordinate


def _source_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return value

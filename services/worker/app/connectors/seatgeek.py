from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from app.core.config import get_settings
from app.models.contracts import CandidateEvent, RetrievalQuery

NYC_LATITUDE = 40.73061
NYC_LONGITUDE = -73.935242


class SeatGeekConnector:
    source_name = "seatgeek"

    def skip_reason(self) -> str | None:
        if not get_settings().seatgeek_client_id:
            return "missing_seatgeek_client_id"
        return None

    async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
        settings = get_settings()
        if self.skip_reason():
            return []

        now = datetime.now(tz=UTC)
        params: dict[str, object] = {
            "client_id": settings.seatgeek_client_id,
            "q": query.query,
            "lat": NYC_LATITUDE,
            "lon": NYC_LONGITUDE,
            "range": "15mi",
            "per_page": 50,
            "datetime_utc.gte": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "datetime_utc.lte": (now + timedelta(days=90)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "sort": "datetime_utc.asc",
        }
        if settings.seatgeek_client_secret:
            params["client_secret"] = settings.seatgeek_client_secret

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get("https://api.seatgeek.com/2/events", params=params)
            response.raise_for_status()
            payload = response.json()

        return [
            candidate
            for item in payload.get("events", [])
            if (candidate := _candidate_from_seatgeek(item, query)) is not None
        ]


def _candidate_from_seatgeek(item: dict, query: RetrievalQuery) -> CandidateEvent | None:
    starts_at = _normalize_seatgeek_datetime(item.get("datetime_utc"))
    venue = item.get("venue") if isinstance(item.get("venue"), dict) else {}
    location = venue.get("location") if isinstance(venue.get("location"), dict) else {}
    latitude = _coerce_coordinate(location.get("lat") or venue.get("lat"))
    longitude = _coerce_coordinate(location.get("lon") or venue.get("lon"))
    title = _string_value(item.get("title"))
    venue_name = _string_value(venue.get("name"))
    event_url = _string_value(item.get("url"))

    if not starts_at or latitude is None or longitude is None or not title or not venue_name or not event_url:
        return None

    stats = item.get("stats") if isinstance(item.get("stats"), dict) else {}
    taxonomies = item.get("taxonomies") if isinstance(item.get("taxonomies"), list) else []
    performers = item.get("performers") if isinstance(item.get("performers"), list) else []
    taxonomy_names = [_string_value(taxonomy.get("name")) for taxonomy in taxonomies if isinstance(taxonomy, dict)]
    performer_names = [_string_value(performer.get("name")) for performer in performers if isinstance(performer, dict)]
    category = next((name for name in taxonomy_names if name), query.category)
    address = _string_value(venue.get("address")) or venue_name
    city = _string_value(venue.get("city")) or "New York City"
    state = _string_value(venue.get("state")) or "NY"

    return CandidateEvent(
        source="seatgeek",
        source_kind="api_connector",
        source_event_key=f"seatgeek:{item.get('id', title)}",
        venue_name=venue_name,
        neighborhood=city,
        address=address,
        city=city,
        state=state,
        postal_code=_string_value(venue.get("postal_code")),
        title=title,
        summary=_string_value(item.get("description")),
        category=category,
        starts_at=starts_at,
        latitude=latitude,
        longitude=longitude,
        ticket_url=event_url,
        source_url=event_url,
        source_base_url="https://seatgeek.com",
        min_price=_coerce_price(stats.get("lowest_price")),
        max_price=_coerce_price(stats.get("highest_price")),
        source_confidence=0.88,
        tags=[value for value in [query.query, category, *taxonomy_names, *performer_names] if value],
    )


def _normalize_seatgeek_datetime(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _coerce_coordinate(value: object) -> float | None:
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None
    if coordinate == 0.0:
        return None
    return coordinate


def _coerce_price(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

from __future__ import annotations

import httpx

from app.connectors.curated_venues import CuratedVenueConnector
from app.connectors.ticketmaster import TicketmasterConnector
from app.core.config import get_settings
from app.models.contracts import CandidateEvent, RetrievalQuery

DEFAULT_SUPPLY_QUERIES = [
    RetrievalQuery(query="techno brooklyn", source="ticketmaster", category="live music"),
    RetrievalQuery(query="indie live music nyc", source="ticketmaster", category="live music"),
    RetrievalQuery(query="gallery installation nyc", source="curated_venues", category="culture"),
    RetrievalQuery(query="indie songwriter brooklyn", source="curated_venues", category="live music"),
]


def build_daily_supply_queries() -> list[RetrievalQuery]:
    return DEFAULT_SUPPLY_QUERIES.copy()


async def collect_supply_candidates() -> list[CandidateEvent]:
    connectors = {
        "ticketmaster": TicketmasterConnector(),
        "curated_venues": CuratedVenueConnector(),
    }
    seen_keys: set[str] = set()
    candidates: list[CandidateEvent] = []

    for query in build_daily_supply_queries():
        connector = connectors.get(query.source)
        if connector is None:
            continue

        for candidate in await connector.search(query):
            if candidate.source_event_key in seen_keys:
                continue
            seen_keys.add(candidate.source_event_key)
            candidates.append(candidate)

    return candidates


async def sync_supply_to_api(candidates: list[CandidateEvent]) -> dict:
    settings = get_settings()
    if not settings.api_base_url:
        return {"status": "skipped", "reason": "missing_api_base_url", "accepted": 0}

    headers: dict[str, str] = {}
    if settings.internal_ingest_secret:
        headers["x-pulse-ingest-secret"] = settings.internal_ingest_secret

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{settings.api_base_url}/v1/internal/ingest/candidates",
            json={"items": [candidate.model_dump(mode="json") for candidate in candidates]},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    payload["status"] = "synced"
    return payload


async def run_daily_supply_sync() -> dict:
    candidates = await collect_supply_candidates()
    payload = await sync_supply_to_api(candidates)
    payload["candidate_count"] = len(candidates)
    return payload

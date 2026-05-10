import httpx

from app.core.config import get_settings
from app.schemas.common import SupplySyncResponse


async def trigger_worker_supply_sync() -> SupplySyncResponse:
    settings = get_settings()
    headers: dict[str, str] = {}

    if settings.internal_ingest_secret:
        headers["x-pulse-ingest-secret"] = settings.internal_ingest_secret

    try:
        timeout = httpx.Timeout(180.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{settings.worker_base_url}/v1/supply/sync",
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as error:
        raise RuntimeError("Pulse worker is unavailable for supply sync. Start the worker on port 8001 and try again.") from error

    return SupplySyncResponse(
        candidateCount=payload.get("candidate_count", 0),
        realEventCount=payload.get("real_event_count", payload.get("candidate_count", 0)),
        ticketUrlCount=payload.get("ticket_url_count", 0),
        accepted=payload.get("accepted", 0),
        sourcesCreated=payload.get("sources_created", 0),
        venuesCreated=payload.get("venues_created", 0),
        eventsCreated=payload.get("events_created", 0),
        occurrencesCreated=payload.get("occurrences_created", 0),
        sourceCounts=payload.get("source_counts", {}),
        rejectedCounts=payload.get("rejected_counts", {}),
        skippedSources=payload.get("skipped_sources", {}),
        fallbackUsed=payload.get("fallback_used", False),
        status=payload.get("status", "synced"),
    )

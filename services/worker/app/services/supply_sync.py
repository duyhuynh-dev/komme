from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import httpx

from app.connectors.curated_venues import CuratedVenueConnector
from app.connectors.nyc_events import NYCEventsConnector
from app.connectors.seatgeek import SeatGeekConnector
from app.connectors.ticketmaster import TicketmasterConnector
from app.core.config import get_settings
from app.models.contracts import CandidateEvent, RetrievalQuery

DEFAULT_SUPPLY_QUERIES = [
    RetrievalQuery(query="", source="ticketmaster", category="all"),
    RetrievalQuery(query="concert", source="ticketmaster", category="live music"),
    RetrievalQuery(query="music", source="ticketmaster", category="live music"),
    RetrievalQuery(query="techno brooklyn", source="ticketmaster", category="live music"),
    RetrievalQuery(query="indie live music nyc", source="ticketmaster", category="live music"),
    RetrievalQuery(query="jazz nyc", source="ticketmaster", category="live music"),
    RetrievalQuery(query="dance music nyc", source="ticketmaster", category="nightlife"),
    RetrievalQuery(query="comedy nyc", source="ticketmaster", category="comedy"),
    RetrievalQuery(query="theater nyc", source="ticketmaster", category="theater"),
    RetrievalQuery(query="book talk nyc", source="ticketmaster", category="talks"),
    RetrievalQuery(query="networking panel nyc", source="ticketmaster", category="community"),
    RetrievalQuery(query="design market brooklyn", source="ticketmaster", category="market"),
    RetrievalQuery(query="vintage pop up nyc", source="ticketmaster", category="shopping"),
    RetrievalQuery(query="", source="seatgeek", category="all"),
    RetrievalQuery(query="concert", source="seatgeek", category="live music"),
    RetrievalQuery(query="music", source="seatgeek", category="live music"),
    RetrievalQuery(query="techno brooklyn", source="seatgeek", category="live music"),
    RetrievalQuery(query="indie live music nyc", source="seatgeek", category="live music"),
    RetrievalQuery(query="brooklyn concert", source="seatgeek", category="live music"),
    RetrievalQuery(query="new york concert", source="seatgeek", category="live music"),
    RetrievalQuery(query="jazz nyc", source="seatgeek", category="live music"),
    RetrievalQuery(query="dance music nyc", source="seatgeek", category="nightlife"),
    RetrievalQuery(query="comedy nyc", source="seatgeek", category="comedy"),
    RetrievalQuery(query="theater nyc", source="seatgeek", category="theater"),
    RetrievalQuery(query="arts nyc", source="seatgeek", category="culture"),
    RetrievalQuery(query="free parks culture", source="nyc_events", category="community"),
    RetrievalQuery(query="family parks events", source="nyc_events", category="community"),
    RetrievalQuery(query="outdoor concert", source="nyc_events", category="live music"),
    RetrievalQuery(query="gallery installation nyc", source="curated_venues", category="culture"),
    RetrievalQuery(query="indie songwriter brooklyn", source="curated_venues", category="live music"),
    RetrievalQuery(query="artist talk brooklyn", source="curated_venues", category="talks"),
    RetrievalQuery(query="community workshop brooklyn", source="curated_venues", category="community"),
]
SUPPLY_LOOKAHEAD = timedelta(days=90)
INGEST_BATCH_SIZE = 50
INGEST_TIMEOUT_SECONDS = 60.0
INGEST_COUNT_FIELDS = (
    "accepted",
    "sources_created",
    "venues_created",
    "events_created",
    "occurrences_created",
)


@dataclass
class SupplyCollectionResult:
    candidates: list[CandidateEvent] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)
    rejected_counts: dict[str, int] = field(default_factory=dict)
    skipped_sources: dict[str, str] = field(default_factory=dict)
    ticket_url_count: int = 0


def build_daily_supply_queries() -> list[RetrievalQuery]:
    return DEFAULT_SUPPLY_QUERIES.copy()


async def collect_supply_candidates() -> list[CandidateEvent]:
    return (await collect_supply_candidates_with_diagnostics()).candidates


async def collect_supply_candidates_with_diagnostics() -> SupplyCollectionResult:
    connectors = {
        "ticketmaster": TicketmasterConnector(),
        "seatgeek": SeatGeekConnector(),
        "nyc_events": NYCEventsConnector(),
        "curated_venues": CuratedVenueConnector(),
    }
    seen_keys: set[str] = set()
    seen_fingerprints: set[str] = set()
    result = SupplyCollectionResult()

    for query in build_daily_supply_queries():
        connector = connectors.get(query.source)
        if connector is None:
            continue
        skip_reason = _connector_skip_reason(connector)
        if skip_reason:
            result.skipped_sources[query.source] = skip_reason
            continue

        try:
            connector_candidates = await connector.search(query)
        except httpx.HTTPError:
            result.rejected_counts[f"{query.source}_http_error"] = (
                result.rejected_counts.get(f"{query.source}_http_error", 0) + 1
            )
            continue

        for candidate in connector_candidates:
            rejection_reason = _candidate_rejection_reason(candidate)
            if rejection_reason is not None:
                result.rejected_counts[rejection_reason] = result.rejected_counts.get(rejection_reason, 0) + 1
                continue
            fingerprint = _dedupe_fingerprint(candidate)
            if candidate.source_event_key in seen_keys or fingerprint in seen_fingerprints:
                result.rejected_counts["duplicate"] = result.rejected_counts.get("duplicate", 0) + 1
                continue
            seen_keys.add(candidate.source_event_key)
            seen_fingerprints.add(fingerprint)
            result.candidates.append(candidate)
            result.source_counts[candidate.source] = result.source_counts.get(candidate.source, 0) + 1
            result.ticket_url_count += int(bool(candidate.ticket_url))

    return result


def _connector_skip_reason(connector: object) -> str | None:
    skip_reason = getattr(connector, "skip_reason", None)
    if not callable(skip_reason):
        return None
    reason = skip_reason()
    return reason if isinstance(reason, str) and reason else None


def _dedupe_fingerprint(candidate: CandidateEvent) -> str:
    normalized_title = _normalize_fingerprint_text(candidate.title)
    normalized_venue = _normalize_fingerprint_text(candidate.venue_name)
    starts_on = candidate.starts_at[:10]
    return f"{normalized_venue}|{normalized_title}|{starts_on}"


def _normalize_fingerprint_text(value: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else " " for character in value)
    return " ".join(normalized.split())


def _candidate_is_usable(candidate: CandidateEvent) -> bool:
    return _candidate_rejection_reason(candidate) is None


def _candidate_rejection_reason(candidate: CandidateEvent) -> str | None:
    try:
        starts_at = datetime.fromisoformat(candidate.starts_at.replace("Z", "+00:00"))
    except ValueError:
        return "invalid_start_time"

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)

    now = datetime.now(tz=UTC)
    if starts_at < now - timedelta(hours=4):
        return "stale"
    if starts_at > now + SUPPLY_LOOKAHEAD:
        return "too_far_future"
    if candidate.latitude == 0.0 or candidate.longitude == 0.0:
        return "invalid_coordinates"
    if not candidate.title.strip() or not candidate.venue_name.strip():
        return "missing_title_or_venue"
    if not (candidate.ticket_url or candidate.source_url or candidate.source_base_url):
        return "missing_source_url"
    return None


async def sync_supply_to_api(candidates: list[CandidateEvent]) -> dict:
    settings = get_settings()
    if not settings.api_base_url:
        return {"status": "skipped", "reason": "missing_api_base_url", "accepted": 0}

    headers: dict[str, str] = {}
    if settings.internal_ingest_secret:
        headers["x-pulse-ingest-secret"] = settings.internal_ingest_secret

    payload = {"status": "synced", "ingest_batches": 0}
    for count_field in INGEST_COUNT_FIELDS:
        payload[count_field] = 0

    timeout = httpx.Timeout(INGEST_TIMEOUT_SECONDS, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for batch in _candidate_batches(candidates, INGEST_BATCH_SIZE):
            response = await client.post(
                f"{settings.api_base_url}/v1/internal/ingest/candidates",
                json={"items": [candidate.model_dump(mode="json") for candidate in batch]},
                headers=headers,
            )
            response.raise_for_status()
            batch_payload = response.json()
            payload["ingest_batches"] += 1
            for count_field in INGEST_COUNT_FIELDS:
                payload[count_field] += int(batch_payload.get(count_field, 0) or 0)

    return payload


def _candidate_batches(candidates: list[CandidateEvent], batch_size: int) -> list[list[CandidateEvent]]:
    return [candidates[index : index + batch_size] for index in range(0, len(candidates), batch_size)]


async def run_daily_supply_sync() -> dict:
    result = await collect_supply_candidates_with_diagnostics()
    payload = await sync_supply_to_api(result.candidates)
    payload["candidate_count"] = len(result.candidates)
    payload["real_event_count"] = len(result.candidates)
    payload["ticket_url_count"] = result.ticket_url_count
    payload["source_counts"] = result.source_counts
    payload["rejected_counts"] = result.rejected_counts
    payload["skipped_sources"] = result.skipped_sources
    payload["fallback_used"] = False
    return payload

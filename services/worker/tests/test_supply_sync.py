import pytest

from app.models.contracts import CandidateEvent, RetrievalQuery
from app.services.supply_sync import (
    _candidate_is_usable,
    build_daily_supply_queries,
    collect_supply_candidates,
    collect_supply_candidates_with_diagnostics,
    sync_supply_to_api,
)


def test_daily_supply_queries_cover_api_and_curated_sources() -> None:
    queries = build_daily_supply_queries()
    query_pairs = {(query.source, query.query) for query in queries}

    assert len(queries) >= 25
    assert {query.source for query in queries} == {"ticketmaster", "seatgeek", "nyc_events", "curated_venues"}
    assert ("ticketmaster", "") in query_pairs
    assert ("ticketmaster", "concert") in query_pairs
    assert ("ticketmaster", "comedy nyc") in query_pairs
    assert ("seatgeek", "") in query_pairs
    assert ("seatgeek", "new york concert") in query_pairs
    assert ("seatgeek", "theater nyc") in query_pairs


@pytest.mark.asyncio
async def test_collect_supply_candidates_dedupes_by_source_event_key(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeConnector:
        def __init__(self, source_name: str) -> None:
            self.source_name = source_name

        async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
            return [
                CandidateEvent(
                    source=self.source_name,
                    source_event_key="shared-event",
                    venue_name="Elsewhere",
                    neighborhood="Bushwick",
                    address="599 Johnson Ave, Brooklyn, NY",
                    title=f"{query.query} result",
                    starts_at="2026-06-25T23:30:00+00:00",
                    latitude=40.7063,
                    longitude=-73.9232,
                    source_url="https://example.com/event",
                )
            ]

    monkeypatch.setattr(
        "app.services.supply_sync.TicketmasterConnector",
        lambda: FakeConnector("ticketmaster"),
    )
    monkeypatch.setattr(
        "app.services.supply_sync.SeatGeekConnector",
        lambda: FakeConnector("seatgeek"),
    )
    monkeypatch.setattr(
        "app.services.supply_sync.NYCEventsConnector",
        lambda: FakeConnector("nyc_events"),
    )
    monkeypatch.setattr(
        "app.services.supply_sync.CuratedVenueConnector",
        lambda: FakeConnector("curated_venues"),
    )

    candidates = await collect_supply_candidates()
    assert len(candidates) == 1
    assert candidates[0].source_event_key == "shared-event"

    result = await collect_supply_candidates_with_diagnostics()
    assert result.source_counts == {"ticketmaster": 1}
    assert result.rejected_counts["duplicate"] >= 1


@pytest.mark.asyncio
async def test_collect_supply_candidates_dedupes_by_normalized_event_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnector:
        def __init__(self, source_name: str, title: str, event_key: str) -> None:
            self.source_name = source_name
            self.title = title
            self.event_key = event_key

        async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
            return [
                CandidateEvent(
                    source=self.source_name,
                    source_event_key=self.event_key,
                    venue_name="Public Records",
                    neighborhood="Gowanus",
                    address="233 Butler St, Brooklyn, NY",
                    title=self.title,
                    starts_at="2026-06-25T23:30:00+00:00",
                    latitude=40.6784,
                    longitude=-73.9896,
                    source_url="https://example.com/event",
                )
            ]

    monkeypatch.setattr(
        "app.services.supply_sync.TicketmasterConnector",
        lambda: FakeConnector("ticketmaster", "Late Night Warehouse Textures", "ticketmaster-1"),
    )
    monkeypatch.setattr(
        "app.services.supply_sync.SeatGeekConnector",
        lambda: FakeConnector("seatgeek", "Late Night Warehouse Textures", "seatgeek-1"),
    )
    monkeypatch.setattr(
        "app.services.supply_sync.NYCEventsConnector",
        lambda: FakeConnector("nyc_events", "Late Night Warehouse Textures", "nyc-events-1"),
    )
    monkeypatch.setattr(
        "app.services.supply_sync.CuratedVenueConnector",
        lambda: FakeConnector("curated_venues", "Late Night Warehouse Textures", "curated-1"),
    )

    candidates = await collect_supply_candidates()
    assert len(candidates) == 1
    assert candidates[0].source_event_key in {"ticketmaster-1", "seatgeek-1", "nyc-events-1", "curated-1"}


@pytest.mark.asyncio
async def test_collect_supply_candidates_records_skipped_source_reasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SkippedConnector:
        def skip_reason(self) -> str:
            return "missing_demo_key"

        async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
            raise AssertionError("Skipped connectors should not be searched")

    class EmptyConnector:
        async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
            return []

    monkeypatch.setattr("app.services.supply_sync.TicketmasterConnector", SkippedConnector)
    monkeypatch.setattr("app.services.supply_sync.SeatGeekConnector", EmptyConnector)
    monkeypatch.setattr("app.services.supply_sync.NYCEventsConnector", EmptyConnector)
    monkeypatch.setattr("app.services.supply_sync.CuratedVenueConnector", EmptyConnector)

    result = await collect_supply_candidates_with_diagnostics()

    assert result.skipped_sources == {"ticketmaster": "missing_demo_key"}


def test_candidate_is_usable_rejects_stale_or_invalid_coordinates() -> None:
    usable = CandidateEvent(
        source="ticketmaster",
        source_event_key="usable",
        venue_name="Elsewhere",
        neighborhood="Bushwick",
        address="599 Johnson Ave, Brooklyn, NY",
        title="Warehouse textures",
        starts_at="2026-05-25T23:30:00+00:00",
        latitude=40.7063,
        longitude=-73.9232,
        source_url="https://example.com/event",
    )
    stale = usable.model_copy(
        update={"source_event_key": "stale", "starts_at": "2020-04-25T23:30:00+00:00"}
    )
    too_far_future = usable.model_copy(
        update={"source_event_key": "too-far", "starts_at": "2099-04-25T23:30:00+00:00"}
    )
    invalid_coordinates = usable.model_copy(update={"source_event_key": "bad-coords", "latitude": 0.0})
    missing_source_url = usable.model_copy(
        update={
            "source_event_key": "no-source",
            "ticket_url": None,
            "source_url": None,
            "source_base_url": None,
        }
    )

    assert _candidate_is_usable(usable) is True
    assert _candidate_is_usable(stale) is False
    assert _candidate_is_usable(too_far_future) is False
    assert _candidate_is_usable(invalid_coordinates) is False
    assert _candidate_is_usable(missing_source_url) is False


@pytest.mark.asyncio
async def test_sync_supply_to_api_batches_large_candidate_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_batches: list[list[dict]] = []
    captured_headers: list[dict[str, str]] = []

    class FakeResponse:
        def __init__(self, accepted: int) -> None:
            self.accepted = accepted

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, int]:
            return {
                "accepted": self.accepted,
                "sources_created": 1,
                "venues_created": 2,
                "events_created": self.accepted,
                "occurrences_created": self.accepted,
            }

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, json: dict[str, list[dict]], headers: dict[str, str]) -> FakeResponse:
            assert url == "http://api.test/v1/internal/ingest/candidates"
            captured_batches.append(json["items"])
            captured_headers.append(headers)
            return FakeResponse(accepted=len(json["items"]))

    class FakeSettings:
        api_base_url = "http://api.test"
        internal_ingest_secret = "pulse-secret"

    candidates = [
        CandidateEvent(
            source="ticketmaster",
            source_event_key=f"event-{index}",
            venue_name="Elsewhere",
            neighborhood="Bushwick",
            address="599 Johnson Ave, Brooklyn, NY",
            title=f"Warehouse textures {index}",
            starts_at="2026-06-25T23:30:00+00:00",
            latitude=40.7063,
            longitude=-73.9232,
            source_url="https://example.com/event",
        )
        for index in range(5)
    ]

    monkeypatch.setattr("app.services.supply_sync.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("app.services.supply_sync.INGEST_BATCH_SIZE", 2)
    monkeypatch.setattr("app.services.supply_sync.httpx.AsyncClient", FakeClient)

    payload = await sync_supply_to_api(candidates)

    assert [len(batch) for batch in captured_batches] == [2, 2, 1]
    assert captured_headers == [{"x-pulse-ingest-secret": "pulse-secret"}] * 3
    assert payload["status"] == "synced"
    assert payload["ingest_batches"] == 3
    assert payload["accepted"] == 5
    assert payload["sources_created"] == 3
    assert payload["venues_created"] == 6
    assert payload["events_created"] == 5
    assert payload["occurrences_created"] == 5

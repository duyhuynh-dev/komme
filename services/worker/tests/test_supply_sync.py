import pytest

from app.models.contracts import CandidateEvent, RetrievalQuery
from app.services.supply_sync import (
    _candidate_is_usable,
    build_daily_supply_queries,
    collect_supply_candidates,
    collect_supply_candidates_with_diagnostics,
)


def test_daily_supply_queries_cover_api_and_curated_sources() -> None:
    queries = build_daily_supply_queries()

    assert len(queries) >= 4
    assert {query.source for query in queries} == {"ticketmaster", "seatgeek", "nyc_events", "curated_venues"}


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

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.events import CanonicalEvent, EventOccurrence, EventSource, Venue
from app.models.recommendation import RecommendationRun, VenueRecommendation
from app.models.user import User, UserConstraint
from app.schemas.recommendations import (
    MapVenuePin,
    RecommendationFreshness,
    RecommendationProvenance,
    TonightPlannerResponse,
    TonightPlannerStop,
    TravelEstimate,
    VenueRecommendationCard,
)
from app.services.planner import build_tonight_planner
from app.services.recommendations import get_map_recommendations


def _planner_card(
    *,
    venue_id: str,
    venue_name: str,
    neighborhood: str,
    starts_at: str,
    score: float,
    score_band: str,
    price_label: str,
    source_confidence: float,
    transit_minutes: int,
) -> VenueRecommendationCard:
    return VenueRecommendationCard(
        venueId=venue_id,
        venueName=venue_name,
        neighborhood=neighborhood,
        address="123 Example St, New York, NY",
        eventTitle=f"{venue_name} set",
        eventId=f"{venue_id}-event",
        startsAt=starts_at,
        priceLabel=price_label,
        scoreBand=score_band,
        score=score,
        travel=[
            TravelEstimate(mode="walk", label=f"{max(5, transit_minutes + 8)} min walk", minutes=max(5, transit_minutes + 8)),
            TravelEstimate(mode="transit", label=f"{transit_minutes} min transit", minutes=transit_minutes),
        ],
        reasons=[],
        freshness=RecommendationFreshness(
            discoveredAt="2026-04-25T20:00:00+00:00",
            lastVerifiedAt="2026-04-25T21:30:00+00:00",
            freshnessLabel="Checked today",
        ),
        provenance=RecommendationProvenance(
            sourceName="Curated venue calendars",
            sourceKind="curated_calendar",
            sourceConfidence=source_confidence,
            sourceConfidenceLabel="High trust" if source_confidence >= 0.82 else "Solid signal",
            sourceBaseUrl="https://example.com",
            hasTicketUrl=True,
        ),
        secondaryEvents=[],
    )


def _planner_pin(
    *,
    venue_id: str,
    venue_name: str,
    latitude: float,
    longitude: float,
    score_band: str = "high",
) -> MapVenuePin:
    return MapVenuePin(
        venueId=venue_id,
        venueName=venue_name,
        latitude=latitude,
        longitude=longitude,
        scoreBand=score_band,
        selected=False,
    )


def test_build_tonight_planner_sequences_pregame_main_and_late_option() -> None:
    now_utc = datetime(2026, 4, 25, 22, 0, tzinfo=UTC)
    items = [
        _planner_card(
            venue_id="pregame-venue",
            venue_name="Night Cafe",
            neighborhood="Lower East Side",
            starts_at="2026-04-25T23:15:00+00:00",
            score=0.78,
            score_band="high",
            price_label="$18",
            source_confidence=0.84,
            transit_minutes=12,
        ),
        _planner_card(
            venue_id="main-venue",
            venue_name="Elsewhere",
            neighborhood="Bushwick",
            starts_at="2026-04-26T01:00:00+00:00",
            score=0.92,
            score_band="high",
            price_label="$35",
            source_confidence=0.91,
            transit_minutes=24,
        ),
        _planner_card(
            venue_id="late-venue",
            venue_name="Mood Ring",
            neighborhood="Bushwick",
            starts_at="2026-04-26T03:10:00+00:00",
            score=0.75,
            score_band="high",
            price_label="$22",
            source_confidence=0.83,
            transit_minutes=26,
        ),
        _planner_card(
            venue_id="backup-venue",
            venue_name="Good Room",
            neighborhood="Greenpoint",
            starts_at="2026-04-26T01:20:00+00:00",
            score=0.8,
            score_band="high",
            price_label="$28",
            source_confidence=0.88,
            transit_minutes=22,
        ),
    ]
    pins = [
        _planner_pin(venue_id="pregame-venue", venue_name="Night Cafe", latitude=40.7206, longitude=-73.9874),
        _planner_pin(venue_id="main-venue", venue_name="Elsewhere", latitude=40.7082, longitude=-73.9232),
        _planner_pin(venue_id="late-venue", venue_name="Mood Ring", latitude=40.7136, longitude=-73.9318),
        _planner_pin(venue_id="backup-venue", venue_name="Good Room", latitude=40.7278, longitude=-73.9524),
    ]

    planner = build_tonight_planner(
        items,
        pins,
        budget_level="under_75",
        timezone="America/New_York",
        now_utc=now_utc,
    )

    assert planner.status == "ready"
    assert [stop.role for stop in planner.stops] == ["pregame", "main_event", "late_option"]
    assert planner.stops[0].venueId == "pregame-venue"
    assert planner.stops[1].venueId == "main-venue"
    assert planner.stops[2].venueId == "late-venue"
    assert planner.stops[1].confidence == "high"
    assert planner.stops[1].hopLabel is not None
    assert "Elsewhere" in (planner.summary or "")


def test_build_tonight_planner_adds_fallbacks_for_late_low_confidence_stop() -> None:
    now_utc = datetime(2026, 4, 25, 22, 0, tzinfo=UTC)
    items = [
        _planner_card(
            venue_id="pregame-venue",
            venue_name="Night Cafe",
            neighborhood="Lower East Side",
            starts_at="2026-04-25T23:10:00+00:00",
            score=0.76,
            score_band="high",
            price_label="$16",
            source_confidence=0.83,
            transit_minutes=11,
        ),
        _planner_card(
            venue_id="main-venue",
            venue_name="Elsewhere",
            neighborhood="Bushwick",
            starts_at="2026-04-26T01:00:00+00:00",
            score=0.91,
            score_band="high",
            price_label="$34",
            source_confidence=0.9,
            transit_minutes=25,
        ),
        _planner_card(
            venue_id="late-venue",
            venue_name="Very Late Warehouse",
            neighborhood="Bushwick",
            starts_at="2026-04-26T03:55:00+00:00",
            score=0.74,
            score_band="medium",
            price_label="$42",
            source_confidence=0.67,
            transit_minutes=28,
        ),
        _planner_card(
            venue_id="alt-venue",
            venue_name="Good Room",
            neighborhood="Greenpoint",
            starts_at="2026-04-26T01:20:00+00:00",
            score=0.82,
            score_band="high",
            price_label="$28",
            source_confidence=0.89,
            transit_minutes=21,
        ),
    ]
    pins = [
        _planner_pin(venue_id="pregame-venue", venue_name="Night Cafe", latitude=40.7206, longitude=-73.9874),
        _planner_pin(venue_id="main-venue", venue_name="Elsewhere", latitude=40.7082, longitude=-73.9232),
        _planner_pin(venue_id="late-venue", venue_name="Very Late Warehouse", latitude=40.7076, longitude=-73.9251, score_band="medium"),
        _planner_pin(venue_id="alt-venue", venue_name="Good Room", latitude=40.7278, longitude=-73.9524),
    ]

    planner = build_tonight_planner(
        items,
        pins,
        budget_level="under_30",
        timezone="America/New_York",
        now_utc=now_utc,
    )

    late_stop = next(stop for stop in planner.stops if stop.role == "late_option")

    assert late_stop.confidence == "watch"
    assert late_stop.fallbacks
    assert late_stop.fallbacks[0].venueId == "alt-venue"
    assert "late" in late_stop.fallbacks[0].fallbackReason.lower()


@pytest.mark.asyncio
async def test_get_map_recommendations_includes_tonight_planner_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="planner@example.com", timezone="America/New_York")
        source = EventSource(name="curated_venues", kind="curated_calendar")
        session.add_all([user, source])
        await session.flush()

        constraint = UserConstraint(
            user_id=user.id,
            city="New York City",
            neighborhood="Bushwick",
            zip_code="11237",
            radius_miles=8,
            budget_level="under_30",
            preferred_days_csv="Friday,Saturday",
            social_mode="either",
        )
        venue = Venue(
            name="Elsewhere",
            neighborhood="Bushwick",
            address="599 Johnson Ave, Brooklyn, NY",
            city="Brooklyn",
            state="NY",
            latitude=40.7082,
            longitude=-73.9232,
        )
        event = CanonicalEvent(
            source_id=source.id,
            source_event_key="curated:event-1",
            title="Warehouse Headliner",
            category="live music",
            summary="Peak-time headline set",
        )
        occurrence = EventOccurrence(
            event_id="pending",
            venue_id="pending",
            starts_at=(datetime.now(tz=UTC) + timedelta(hours=4)).isoformat(),
            ticket_url="https://example.com/tickets",
            metadata_json={"sourceConfidence": 0.88, "topicKeys": ["underground_dance"]},
        )
        run = RecommendationRun(
            user_id=user.id,
            provider="catalog",
            model_name="pulse-deterministic-v1",
            viewport_json={
                "latitude": 40.73061,
                "longitude": -73.935242,
                "latitudeDelta": 0.22,
                "longitudeDelta": 0.22,
            },
            created_at=datetime.now(tz=UTC),
        )

        session.add_all([constraint, venue, event])
        await session.flush()
        occurrence.event_id = event.id
        occurrence.venue_id = venue.id
        session.add_all([occurrence, run])
        await session.flush()

        session.add(
            VenueRecommendation(
                run_id=run.id,
                venue_id=venue.id,
                event_occurrence_id=occurrence.id,
                rank=1,
                score=0.91,
                score_band="high",
                reasons_json=[],
                travel_json=[{"mode": "transit", "label": "18 min transit", "minutes": 18}],
                secondary_events_json=[],
                created_at=datetime.now(tz=UTC),
            )
        )
        await session.commit()

        async def fake_refresh(*_args, **_kwargs) -> RecommendationRun:
            return run

        captured: dict[str, object] = {}

        def fake_planner(
            items: list[VenueRecommendationCard],
            pins: list[MapVenuePin],
            *,
            budget_level: str,
            timezone: str,
            now_utc: datetime | None = None,
        ) -> TonightPlannerResponse:
            captured["item_count"] = len(items)
            captured["pin_count"] = len(pins)
            captured["budget_level"] = budget_level
            captured["timezone"] = timezone
            captured["now_utc"] = now_utc
            return TonightPlannerResponse(
                status="ready",
                summary="Test planner",
                stops=[
                    TonightPlannerStop(
                        role="main_event",
                        roleLabel="Main event",
                        venueId=venue.id,
                        venueName=venue.name,
                        eventId=occurrence.id,
                        eventTitle=event.title,
                        neighborhood=venue.neighborhood or "Bushwick",
                        startsAt=occurrence.starts_at,
                        priceLabel="$25",
                        scoreBand="high",
                        hopLabel="18 min transit",
                        roleReason="Test reason",
                        confidence="high",
                        confidenceLabel="Confident anchor",
                        confidenceReason="Test confidence",
                        fallbacks=[],
                    )
                ],
            )

        monkeypatch.setattr("app.services.recommendations.refresh_recommendations_for_user", fake_refresh)
        monkeypatch.setattr("app.services.recommendations.build_tonight_planner", fake_planner)

        response = await get_map_recommendations(session, user)

        assert response.tonightPlanner.summary == "Test planner"
        assert captured["item_count"] == 1
        assert captured["pin_count"] == 1
        assert captured["budget_level"] == "under_30"
        assert captured["timezone"] == "America/New_York"

    await engine.dispose()

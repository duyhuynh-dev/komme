from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import event_plan_sessions, planner_sessions, recommendation_interactions
from app.db.base import Base
from app.models.events import CanonicalEvent, EventOccurrence, EventSource, Venue
from app.models.recommendation import (
    PLANNER_ATTENDED_FEEDBACK_ACTION,
    PLANNER_COMMIT_FEEDBACK_ACTION,
    PLANNER_SKIPPED_FEEDBACK_ACTION,
    PLANNER_SWAP_FEEDBACK_ACTION,
    FeedbackEvent,
    PlannerSession,
    PlannerSessionEvent,
    RecommendationRun,
    VenueRecommendation,
)
from app.models.user import User, UserConstraint
from app.schemas.recommendations import RecommendationInteractionsPayload
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
from app.services.planner_sessions import (
    PLANNER_EVENT_ROUTE_RECOMPUTED,
    PLANNER_EVENT_SESSION_COMPLETED,
    PLANNER_EVENT_SESSION_CREATED,
    PLANNER_EVENT_SESSION_EXPIRED,
    PLANNER_EVENT_STOP_LOCKED,
    PLANNER_EVENT_STOP_SKIPPED,
    PLANNER_SESSION_ACTIVE,
    PLANNER_SESSION_COMPLETED,
    PLANNER_SESSION_EXPIRED,
    append_planner_session_event,
    evaluate_session_lifecycle,
    expire_stale_planner_sessions,
    get_or_create_planner_session,
    get_planner_session_debug,
    list_planner_session_events,
    recompose_remaining_route,
    reduce_planner_session,
)
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


def _planner_stop(
    *,
    event_id: str,
    venue_id: str = "venue-1",
    venue_name: str = "Elsewhere",
    starts_at: str = "2026-04-26T01:00:00+00:00",
    role: str = "main_event",
) -> TonightPlannerStop:
    return TonightPlannerStop(
        role=role,
        roleLabel="Main event" if role == "main_event" else role.replace("_", " ").title(),
        venueId=venue_id,
        venueName=venue_name,
        eventId=event_id,
        eventTitle=f"{venue_name} event",
        neighborhood="Bushwick",
        startsAt=starts_at,
        priceLabel="$35",
        scoreBand="high",
        hopLabel="18 min transit",
        roleReason="Test route stop",
        confidence="high",
        confidenceLabel="Confident anchor",
        confidenceReason="Test confidence",
        selected=False,
        fallbacks=[],
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
            starts_at="2026-04-26T03:55:00+00:00",
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


def test_build_tonight_planner_marks_execution_and_outcome_state() -> None:
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
            starts_at="2026-04-26T03:55:00+00:00",
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
    baseline_planner = build_tonight_planner(
        items,
        pins,
        budget_level="under_75",
        timezone="America/New_York",
        now_utc=now_utc,
    )
    swap_target = next(
        fallback
        for stop in baseline_planner.stops
        for fallback in stop.fallbacks
    )

    locked_planner = build_tonight_planner(
        items,
        pins,
        budget_level="under_75",
        timezone="America/New_York",
        now_utc=now_utc,
        selected_recommendation_id="main-venue-event",
        selected_action=PLANNER_COMMIT_FEEDBACK_ACTION,
        outcome_recommendation_id="main-venue-event",
        outcome_action=PLANNER_ATTENDED_FEEDBACK_ACTION,
    )
    swapped_planner = build_tonight_planner(
        items,
        pins,
        budget_level="under_75",
        timezone="America/New_York",
        now_utc=now_utc,
        selected_recommendation_id=swap_target.eventId,
        selected_action=PLANNER_SWAP_FEEDBACK_ACTION,
        outcome_recommendation_id=swap_target.eventId,
        outcome_action=PLANNER_SKIPPED_FEEDBACK_ACTION,
    )

    locked_main_stop = next(stop for stop in locked_planner.stops if stop.role == "main_event")
    swapped_backup = next(
        fallback
        for stop in swapped_planner.stops
        for fallback in stop.fallbacks
        if fallback.eventId == swap_target.eventId
    )

    assert locked_planner.executionStatus == "locked"
    assert locked_main_stop.selected is True
    assert locked_planner.activeTargetEventId == "main-venue-event"
    assert locked_planner.activeTargetVenueName == "Elsewhere"
    assert locked_planner.outcomeStatus == "attended"
    assert locked_planner.rerouteStatus == "idle"
    assert "Elsewhere" in (locked_planner.executionNote or "")
    assert "Elsewhere" in (locked_planner.outcomeNote or "")
    assert swapped_planner.executionStatus == "swapped"
    assert swapped_backup.selected is True
    assert swapped_planner.activeTargetEventId == swap_target.eventId
    assert swapped_planner.activeTargetVenueName == swap_target.venueName
    assert swapped_planner.outcomeStatus == "skipped"
    assert swapped_planner.rerouteStatus == "unavailable"
    assert swap_target.venueName in (swapped_planner.executionNote or "")
    assert swap_target.venueName in (swapped_planner.outcomeNote or "")


def test_build_tonight_planner_suggests_reroute_after_skipped_stop() -> None:
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
            starts_at="2026-04-26T03:55:00+00:00",
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
        selected_recommendation_id="main-venue-event",
        selected_action=PLANNER_COMMIT_FEEDBACK_ACTION,
        outcome_recommendation_id="main-venue-event",
        outcome_action=PLANNER_SKIPPED_FEEDBACK_ACTION,
    )

    assert planner.outcomeStatus == "skipped"
    assert planner.rerouteStatus == "available"
    assert planner.rerouteOption is not None
    assert planner.rerouteOption.venueName == "Mood Ring"
    assert planner.rerouteOption.sourceKind == "next_stop"
    assert "jump ahead" in (planner.rerouteNote or "").lower()


@pytest.mark.asyncio
async def test_planner_session_reducer_tracks_execution_events() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="planner-session@example.com")
        session.add(user)
        await session.flush()

        now_utc = datetime(2026, 4, 25, 22, 0, tzinfo=UTC)
        planner = build_tonight_planner(
            [
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
                    starts_at="2026-04-26T03:55:00+00:00",
                    score=0.75,
                    score_band="high",
                    price_label="$22",
                    source_confidence=0.83,
                    transit_minutes=26,
                ),
            ],
            [
                _planner_pin(venue_id="pregame-venue", venue_name="Night Cafe", latitude=40.7206, longitude=-73.9874),
                _planner_pin(venue_id="main-venue", venue_name="Elsewhere", latitude=40.7082, longitude=-73.9232),
                _planner_pin(venue_id="late-venue", venue_name="Mood Ring", latitude=40.7136, longitude=-73.9318),
            ],
            budget_level="under_75",
            timezone="America/New_York",
            now_utc=now_utc,
        )

        planner_session = await get_or_create_planner_session(
            session,
            user_id=user.id,
            recommendation_run_id=None,
            recommendation_context_hash="session-test",
            planner=planner,
            budget_level="under_75",
            timezone="America/New_York",
        )
        assert planner_session is not None

        await append_planner_session_event(
            session,
            planner_session=planner_session,
            event_type=PLANNER_EVENT_STOP_LOCKED,
            recommendation_id="main-venue-event",
        )
        await append_planner_session_event(
            session,
            planner_session=planner_session,
            event_type=PLANNER_EVENT_STOP_SKIPPED,
            recommendation_id="main-venue-event",
        )
        recomposition = recompose_remaining_route(
            reduce_planner_session(
                planner_session,
                await list_planner_session_events(session, planner_session.id),
            ),
            now_utc=datetime(2026, 4, 26, 0, 30, tzinfo=UTC),
        )
        await append_planner_session_event(
            session,
            planner_session=planner_session,
            event_type=PLANNER_EVENT_ROUTE_RECOMPUTED,
            recommendation_id=recomposition.active_stop_event_id,
            metadata={
                "activeStopEventId": recomposition.active_stop_event_id,
                "sessionStatus": recomposition.session_status,
                "remainingStops": [stop.model_dump(mode="json") for stop in recomposition.remaining_stops],
                "droppedStops": [stop.model_dump(mode="json") for stop in recomposition.dropped_stops],
                "replacements": [stop.model_dump(mode="json") for stop in recomposition.replacements],
                "reason": recomposition.reason,
            },
        )

        events = await list_planner_session_events(session, planner_session.id)
        state = reduce_planner_session(planner_session, events)

        assert [event.event_type for event in events] == [
            PLANNER_EVENT_SESSION_CREATED,
            PLANNER_EVENT_STOP_LOCKED,
            PLANNER_EVENT_STOP_SKIPPED,
            PLANNER_EVENT_ROUTE_RECOMPUTED,
        ]
        assert "main-venue-event" in state.skipped_event_ids
        assert state.active_stop_event_id == "late-venue-event"
        assert state.remaining_stops[0].eventId == "late-venue-event"
        assert "timing" in (state.recomposition_reason or "").lower()

    await engine.dispose()


@pytest.mark.asyncio
async def test_planner_session_debug_payload_summarizes_timeline_and_scores() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="planner-debug@example.com")
        session.add(user)
        await session.flush()
        stop = TonightPlannerStop(
            role="main_event",
            roleLabel="Main event",
            venueId="main-venue",
            venueName="Elsewhere",
            eventId="main-event",
            eventTitle="Headliner",
            neighborhood="Bushwick",
            startsAt="2026-04-26T01:00:00+00:00",
            priceLabel="$35",
            scoreBand="high",
            hopLabel="18 min transit",
            roleReason="Anchor",
            confidence="high",
            confidenceLabel="Confident anchor",
            confidenceReason="Strong fit.",
            selected=True,
            fallbacks=[],
        )
        planner_session = PlannerSession(
            user_id=user.id,
            recommendation_context_hash="debug-hash",
            initial_route_snapshot={"stops": [stop.model_dump(mode="json")]},
            active_stop_event_id="main-event",
            status="active",
            budget_level="under_75",
            timezone="America/New_York",
        )
        session.add(planner_session)
        await session.flush()
        await append_planner_session_event(
            session,
            planner_session=planner_session,
            event_type=PLANNER_EVENT_SESSION_CREATED,
            recommendation_id="main-event",
            metadata={"activeStopEventId": "main-event"},
        )
        await append_planner_session_event(
            session,
            planner_session=planner_session,
            event_type=PLANNER_EVENT_ROUTE_RECOMPUTED,
            recommendation_id="main-event",
            metadata={
                "activeStopEventId": "main-event",
                "sessionStatus": "active",
                "remainingStops": [stop.model_dump(mode="json")],
                "droppedStops": [],
                "reason": "Pulse recomposed the remaining route around live timing.",
                "scores": [
                    {
                        "eventId": "main-event",
                        "venueName": "Elsewhere",
                        "role": "main_event",
                        "score": 0.812,
                        "reasons": ["high shortlist band", "budget fit 0.78"],
                    }
                ],
            },
        )

        response = await get_planner_session_debug(session, user_id=user.id)

        assert len(response.sessions) == 1
        debug_session = response.sessions[0]
        assert debug_session.sessionId == planner_session.id
        assert debug_session.contextHash == "debug-hash"
        assert debug_session.recompositionReason == "Pulse recomposed the remaining route around live timing."
        assert debug_session.recompositionScores[0].venueName == "Elsewhere"
        assert [event.eventType for event in debug_session.events] == [
            PLANNER_EVENT_SESSION_CREATED,
            PLANNER_EVENT_ROUTE_RECOMPUTED,
        ]

    await engine.dispose()


@pytest.mark.asyncio
async def test_event_plan_sessions_route_matches_planner_sessions_alias() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="event-plan-route@example.com")
        session.add(user)
        await session.flush()
        stop = _planner_stop(event_id="main-event")
        planner_session = PlannerSession(
            user_id=user.id,
            recommendation_context_hash="route-hash",
            initial_route_snapshot={"stops": [stop.model_dump(mode="json")]},
            active_stop_event_id="main-event",
            status="active",
            budget_level="under_75",
            timezone="America/New_York",
        )
        session.add(planner_session)
        await session.flush()

        neutral_response = await event_plan_sessions(session=session, user=user)
        legacy_response = await planner_sessions(session=session, user=user)

        assert neutral_response.model_dump() == legacy_response.model_dump()
        assert neutral_response.sessions[0].sessionId == planner_session.id

    await engine.dispose()


def test_planner_session_lifecycle_marks_completed_when_route_is_resolved() -> None:
    stop = _planner_stop(event_id="main-event")
    planner_session = PlannerSession(
        id="session-1",
        user_id="user-1",
        initial_route_snapshot={"stops": [stop.model_dump(mode="json")]},
        active_stop_event_id="main-event",
        status=PLANNER_SESSION_ACTIVE,
        budget_level="under_75",
        timezone="America/New_York",
        created_at=datetime(2026, 4, 25, 20, 0, tzinfo=UTC),
    )
    state = reduce_planner_session(
        planner_session,
        [
            PlannerSessionEvent(
                session_id="session-1",
                event_type=PLANNER_EVENT_SESSION_CREATED,
                recommendation_id="main-event",
                metadata_json={"activeStopEventId": "main-event"},
                created_at=datetime(2026, 4, 25, 20, 0, tzinfo=UTC),
            ),
            PlannerSessionEvent(
                session_id="session-1",
                event_type="stop_attended",
                recommendation_id="main-event",
                metadata_json={},
                created_at=datetime(2026, 4, 25, 23, 0, tzinfo=UTC),
            ),
        ],
    )

    lifecycle = evaluate_session_lifecycle(
        planner_session,
        state,
        current_planner=None,
        now_utc=datetime(2026, 4, 26, 0, 0, tzinfo=UTC),
    )

    assert lifecycle is not None
    assert lifecycle["status"] == PLANNER_SESSION_COMPLETED
    assert lifecycle["eventType"] == PLANNER_EVENT_SESSION_COMPLETED
    assert lifecycle["rule"] == "all_stops_resolved"


def test_planner_session_lifecycle_expires_by_age_and_route_viability() -> None:
    old_stop = _planner_stop(event_id="old-event", starts_at="2026-04-26T12:00:00+00:00")
    old_session = PlannerSession(
        id="old-session",
        user_id="user-1",
        initial_route_snapshot={"stops": [old_stop.model_dump(mode="json")]},
        active_stop_event_id="old-event",
        status=PLANNER_SESSION_ACTIVE,
        budget_level="under_75",
        timezone="America/New_York",
        created_at=datetime(2026, 4, 24, 0, 0, tzinfo=UTC),
    )
    old_state = reduce_planner_session(old_session, [])

    age_lifecycle = evaluate_session_lifecycle(
        old_session,
        old_state,
        current_planner=None,
        now_utc=datetime(2026, 4, 26, 1, 0, tzinfo=UTC),
    )

    stale_stop = _planner_stop(event_id="stale-event", starts_at="2026-04-26T12:00:00+00:00")
    stale_session = PlannerSession(
        id="stale-session",
        user_id="user-1",
        initial_route_snapshot={"stops": [stale_stop.model_dump(mode="json")]},
        active_stop_event_id="stale-event",
        status=PLANNER_SESSION_ACTIVE,
        budget_level="under_75",
        timezone="America/New_York",
        created_at=datetime(2026, 4, 26, 10, 0, tzinfo=UTC),
    )
    stale_state = reduce_planner_session(stale_session, [])

    viability_lifecycle = evaluate_session_lifecycle(
        stale_session,
        stale_state,
        current_planner=None,
        now_utc=datetime(2026, 4, 26, 12, 45, tzinfo=UTC),
    )

    assert age_lifecycle is not None
    assert age_lifecycle["status"] == PLANNER_SESSION_EXPIRED
    assert age_lifecycle["rule"] == "session_age"
    assert viability_lifecycle is not None
    assert viability_lifecycle["status"] == PLANNER_SESSION_EXPIRED
    assert viability_lifecycle["rule"] == "route_not_viable"


@pytest.mark.asyncio
async def test_get_or_create_planner_session_rejects_stale_active_session_and_creates_fresh() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="planner-stale@example.com")
        session.add(user)
        await session.flush()

        old_stop = _planner_stop(
            event_id="old-event",
            venue_id="old-venue",
            venue_name="Old Venue",
            starts_at=(datetime.now(tz=UTC) - timedelta(hours=3)).isoformat(),
        )
        old_session = PlannerSession(
            user_id=user.id,
            recommendation_context_hash="same-context",
            initial_route_snapshot={"stops": [old_stop.model_dump(mode="json")]},
            active_stop_event_id="old-event",
            status=PLANNER_SESSION_ACTIVE,
            budget_level="under_75",
            timezone="America/New_York",
            created_at=datetime.now(tz=UTC) - timedelta(hours=6),
        )
        session.add(old_session)
        await session.flush()

        new_stop = _planner_stop(
            event_id="new-event",
            venue_id="new-venue",
            venue_name="New Venue",
            starts_at=(datetime.now(tz=UTC) + timedelta(hours=2)).isoformat(),
        )
        planner = TonightPlannerResponse(
            status="ready",
            stops=[new_stop],
            summary="Fresh event plan.",
        )

        fresh_session = await get_or_create_planner_session(
            session,
            user_id=user.id,
            recommendation_run_id=None,
            recommendation_context_hash="same-context",
            planner=planner,
            budget_level="under_75",
            timezone="America/New_York",
        )

        await session.refresh(old_session)
        fresh_events = await list_planner_session_events(session, fresh_session.id)
        old_events = await list_planner_session_events(session, old_session.id)

        assert fresh_session is not None
        assert fresh_session.id != old_session.id
        assert old_session.status == PLANNER_SESSION_EXPIRED
        assert any(event.event_type == PLANNER_EVENT_SESSION_EXPIRED for event in old_events)
        assert fresh_events[0].metadata_json["createdFreshBecauseStale"] is True
        assert fresh_events[0].metadata_json["replacedSessionId"] == old_session.id
        debug_response = await get_planner_session_debug(session, user_id=user.id)
        fresh_debug = next(item for item in debug_response.sessions if item.sessionId == fresh_session.id)
        old_debug = next(item for item in debug_response.sessions if item.sessionId == old_session.id)
        assert fresh_debug.createdFreshBecauseStale is True
        assert fresh_debug.replacedSessionId == old_session.id
        assert old_debug.lifecycleReason is not None
        assert "expired" in old_debug.lifecycleReason

    await engine.dispose()


@pytest.mark.asyncio
async def test_expire_stale_planner_sessions_marks_changed_planning_window() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="planner-window@example.com")
        session.add(user)
        await session.flush()
        old_stop = _planner_stop(
            event_id="old-event",
            venue_id="old-venue",
            venue_name="Old Venue",
            starts_at="2026-04-26T20:00:00+00:00",
        )
        planner_session = PlannerSession(
            user_id=user.id,
            recommendation_context_hash="old-context",
            initial_route_snapshot={"stops": [old_stop.model_dump(mode="json")]},
            active_stop_event_id="old-event",
            status=PLANNER_SESSION_ACTIVE,
            budget_level="under_75",
            timezone="America/New_York",
            created_at=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        )
        session.add(planner_session)
        await session.flush()
        current_stop = _planner_stop(
            event_id="new-event",
            venue_id="new-venue",
            venue_name="New Venue",
            starts_at="2026-04-26T21:00:00+00:00",
        )
        current_planner = TonightPlannerResponse(status="ready", stops=[current_stop])

        stale_session = await expire_stale_planner_sessions(
            session,
            user_id=user.id,
            current_planner=current_planner,
            now_utc=datetime(2026, 4, 26, 13, 0, tzinfo=UTC),
        )

        await session.refresh(planner_session)
        events = await list_planner_session_events(session, planner_session.id)

        assert stale_session is not None
        assert stale_session.id == planner_session.id
        assert planner_session.status == PLANNER_SESSION_EXPIRED
        assert events[-1].event_type == PLANNER_EVENT_SESSION_EXPIRED
        assert events[-1].metadata_json["rule"] == "planning_window_changed"

    await engine.dispose()


def test_recompose_remaining_route_uses_fallback_when_active_stop_is_exhausted() -> None:
    main_stop = TonightPlannerStop(
        role="main_event",
        roleLabel="Main event",
        venueId="main-venue",
        venueName="Elsewhere",
        eventId="main-event",
        eventTitle="Headliner",
        neighborhood="Bushwick",
        startsAt="2026-04-26T01:00:00+00:00",
        priceLabel="$35",
        scoreBand="medium",
        hopLabel="24 min transit",
        roleReason="Anchor",
        confidence="medium",
        confidenceLabel="Good fit",
        confidenceReason="Solid anchor.",
        selected=True,
        fallbacks=[
            {
                "venueId": "backup-venue",
                "venueName": "Good Room",
                "eventId": "backup-event",
                "eventTitle": "Backup set",
                "neighborhood": "Greenpoint",
                "startsAt": "2026-04-26T01:20:00+00:00",
                "priceLabel": "$28",
                "scoreBand": "high",
                "hopLabel": "16 min transit",
                "fallbackReason": "Use this if Elsewhere falls through.",
                "selected": False,
            }
        ],
    )
    state = reduce_planner_session(
        PlannerSession(
            id="session-1",
            user_id="user-1",
            recommendation_context_hash="hash",
            initial_route_snapshot={"stops": [main_stop.model_dump(mode="json")]},
            active_stop_event_id="main-event",
            status="active",
            budget_level="under_75",
            timezone="America/New_York",
        ),
        [
            PlannerSessionEvent(
                session_id="session-1",
                event_type=PLANNER_EVENT_SESSION_CREATED,
                recommendation_id="main-event",
                metadata_json={"activeStopEventId": "main-event"},
                created_at=datetime(2026, 4, 25, 22, 0, tzinfo=UTC),
            ),
            PlannerSessionEvent(
                session_id="session-1",
                event_type=PLANNER_EVENT_STOP_SKIPPED,
                recommendation_id="main-event",
                metadata_json={},
                created_at=datetime(2026, 4, 25, 22, 5, tzinfo=UTC),
            ),
        ],
    )

    recomposition = recompose_remaining_route(state, now_utc=datetime(2026, 4, 25, 22, 10, tzinfo=UTC))

    assert recomposition.active_stop_event_id == "backup-event"
    assert recomposition.remaining_stops[0].venueName == "Good Room"
    assert recomposition.dropped_stops[0].eventId == "main-event"
    assert recomposition.replacements[0].eventId == "backup-event"


@pytest.mark.asyncio
async def test_recommendation_interactions_accept_planner_actions() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="planner-actions@example.com")
        session.add(user)
        await session.flush()
        planner_session = PlannerSession(
            user_id=user.id,
            recommendation_context_hash="interaction-test",
            initial_route_snapshot={"stops": []},
            active_stop_event_id="rec-1",
            status="active",
            budget_level="under_75",
            timezone="America/New_York",
        )
        session.add(planner_session)
        await session.flush()

        payload = RecommendationInteractionsPayload(
            events=[
                {
                    "recommendationId": "rec-1",
                    "action": PLANNER_COMMIT_FEEDBACK_ACTION,
                    "plannerSessionId": planner_session.id,
                },
                {
                    "recommendationId": "rec-2",
                    "action": PLANNER_SWAP_FEEDBACK_ACTION,
                    "plannerSessionId": planner_session.id,
                },
                {
                    "recommendationId": "rec-2",
                    "action": PLANNER_SWAP_FEEDBACK_ACTION,
                    "plannerSessionId": planner_session.id,
                },
                {
                    "recommendationId": "rec-2",
                    "action": PLANNER_ATTENDED_FEEDBACK_ACTION,
                    "plannerSessionId": planner_session.id,
                },
                {
                    "recommendationId": "rec-3",
                    "action": PLANNER_SKIPPED_FEEDBACK_ACTION,
                    "plannerSessionId": planner_session.id,
                },
                {"recommendationId": "rec-3", "action": "unknown_action"},
            ]
        )

        await recommendation_interactions(
            payload=payload,
            session=session,
            user=user,
        )
        await session.commit()

        feedback_rows = list((await session.scalars(select(FeedbackEvent))).all())
        planner_event_rows = list((await session.scalars(select(PlannerSessionEvent))).all())

        assert len(feedback_rows) == 4
        assert {row.action for row in feedback_rows} == {
            PLANNER_ATTENDED_FEEDBACK_ACTION,
            PLANNER_COMMIT_FEEDBACK_ACTION,
            PLANNER_SKIPPED_FEEDBACK_ACTION,
            PLANNER_SWAP_FEEDBACK_ACTION,
        }
        assert {row.event_type for row in planner_event_rows} >= {
            PLANNER_EVENT_STOP_LOCKED,
            PLANNER_EVENT_ROUTE_RECOMPUTED,
        }


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
        session.add(
            FeedbackEvent(
                user_id=user.id,
                recommendation_id=occurrence.id,
                action=PLANNER_COMMIT_FEEDBACK_ACTION,
                created_at=datetime.now(tz=UTC),
            )
        )
        session.add(
            FeedbackEvent(
                user_id=user.id,
                recommendation_id=occurrence.id,
                action=PLANNER_ATTENDED_FEEDBACK_ACTION,
                created_at=datetime.now(tz=UTC) + timedelta(minutes=1),
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
            selected_recommendation_id: str | None = None,
            selected_action: str | None = None,
            outcome_recommendation_id: str | None = None,
            outcome_action: str | None = None,
        ) -> TonightPlannerResponse:
            captured["item_count"] = len(items)
            captured["pin_count"] = len(pins)
            captured["budget_level"] = budget_level
            captured["timezone"] = timezone
            captured["now_utc"] = now_utc
            captured["selected_recommendation_id"] = selected_recommendation_id
            captured["selected_action"] = selected_action
            captured["outcome_recommendation_id"] = outcome_recommendation_id
            captured["outcome_action"] = outcome_action
            return TonightPlannerResponse(
                status="ready",
                summary="Test planner",
                executionStatus="idle",
                activeTargetEventId=occurrence.id,
                activeTargetVenueName=venue.name,
                outcomeStatus="attended",
                outcomeNote=f"{venue.name} is confirmed as part of tonight's plan.",
                rerouteStatus="idle",
                rerouteNote=None,
                rerouteOption=None,
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
                        selected=False,
                        fallbacks=[],
                    )
                ],
            )

        monkeypatch.setattr("app.services.recommendations.refresh_recommendations_for_user", fake_refresh)
        monkeypatch.setattr("app.services.recommendations.build_event_plan", fake_planner)

        response = await get_map_recommendations(session, user)

        planner_sessions = list((await session.scalars(select(PlannerSession))).all())
        planner_session_events = list((await session.scalars(select(PlannerSessionEvent))).all())

        assert response.tonightPlanner.summary == "Test planner"
        assert response.tonightPlanner.sessionId == planner_sessions[0].id
        assert response.tonightPlanner.sessionStatus == "active"
        assert response.tonightPlanner.activeStop is not None
        assert response.tonightPlanner.remainingStops[0].eventId == occurrence.id
        assert response.eventPlan.sessionId == response.tonightPlanner.sessionId
        assert response.eventPlan.remainingStops[0].eventId == occurrence.id
        assert response.eventPlan.summary == "Test planner"
        assert len(planner_sessions) == 1
        assert planner_session_events[0].event_type == PLANNER_EVENT_SESSION_CREATED
        assert captured["item_count"] == 1
        assert captured["pin_count"] == 1
        assert captured["budget_level"] == "under_30"
        assert captured["timezone"] == "America/New_York"
        assert captured["selected_recommendation_id"] is None
        assert captured["selected_action"] is None
        assert captured["outcome_recommendation_id"] is None
        assert captured["outcome_action"] is None

    await engine.dispose()

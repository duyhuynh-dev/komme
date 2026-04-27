from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation import PlannerSession, PlannerSessionEvent
from app.schemas.recommendations import (
    TonightPlannerFallbackOption,
    TonightPlannerResponse,
    TonightPlannerStop,
)

PLANNER_SESSION_ACTIVE = "active"
PLANNER_SESSION_COMPLETED = "completed"
PLANNER_SESSION_EXHAUSTED = "exhausted"

PLANNER_EVENT_SESSION_CREATED = "session_created"
PLANNER_EVENT_STOP_LOCKED = "stop_locked"
PLANNER_EVENT_STOP_SWAPPED = "stop_swapped"
PLANNER_EVENT_STOP_ATTENDED = "stop_attended"
PLANNER_EVENT_STOP_SKIPPED = "stop_skipped"
PLANNER_EVENT_ROUTE_RECOMPUTED = "route_recomputed"


@dataclass
class PlannerRecomposition:
    remaining_stops: list[TonightPlannerStop] = field(default_factory=list)
    dropped_stops: list[TonightPlannerStop] = field(default_factory=list)
    replacements: list[TonightPlannerStop] = field(default_factory=list)
    reason: str = "Pulse kept the remaining route as-is."
    active_stop_event_id: str | None = None
    session_status: str = PLANNER_SESSION_ACTIVE


@dataclass
class PlannerSessionState:
    session_id: str
    session_status: str
    active_stop_event_id: str | None
    initial_stops: list[TonightPlannerStop]
    current_route: list[TonightPlannerStop]
    attended_event_ids: set[str] = field(default_factory=set)
    skipped_event_ids: set[str] = field(default_factory=set)
    locked_event_ids: set[str] = field(default_factory=set)
    swapped_event_ids: set[str] = field(default_factory=set)
    remaining_stops: list[TonightPlannerStop] = field(default_factory=list)
    dropped_stops: list[TonightPlannerStop] = field(default_factory=list)
    replacements: list[TonightPlannerStop] = field(default_factory=list)
    recomposition_reason: str | None = None
    last_event_at: datetime | None = None


def planner_event_type_for_action(action: str) -> str | None:
    return {
        "planner_commit": PLANNER_EVENT_STOP_LOCKED,
        "planner_swap": PLANNER_EVENT_STOP_SWAPPED,
        "planner_attended": PLANNER_EVENT_STOP_ATTENDED,
        "planner_skipped": PLANNER_EVENT_STOP_SKIPPED,
    }.get(action)


async def get_or_create_planner_session(
    session: AsyncSession,
    *,
    user_id: str,
    recommendation_run_id: str | None,
    recommendation_context_hash: str | None,
    planner: TonightPlannerResponse,
    budget_level: str,
    timezone: str,
) -> PlannerSession | None:
    if planner.status == "empty" or not planner.stops:
        return None

    query = (
        select(PlannerSession)
        .where(
            PlannerSession.user_id == user_id,
            PlannerSession.status == PLANNER_SESSION_ACTIVE,
        )
        .order_by(desc(PlannerSession.created_at), desc(PlannerSession.id))
        .limit(1)
    )
    if recommendation_context_hash:
        query = query.where(PlannerSession.recommendation_context_hash == recommendation_context_hash)
    elif recommendation_run_id:
        query = query.where(PlannerSession.recommendation_run_id == recommendation_run_id)

    existing = await session.scalar(query)
    if existing is not None:
        return existing

    active_stop = _initial_active_stop(planner.stops)
    planner_session = PlannerSession(
        user_id=user_id,
        recommendation_run_id=recommendation_run_id,
        recommendation_context_hash=recommendation_context_hash,
        initial_route_snapshot={
            "status": planner.status,
            "summary": planner.summary,
            "planningNote": planner.planningNote,
            "stops": [_stop_dump(stop) for stop in planner.stops],
        },
        active_stop_event_id=active_stop.eventId if active_stop else None,
        status=PLANNER_SESSION_ACTIVE,
        budget_level=budget_level,
        timezone=timezone,
    )
    session.add(planner_session)
    await session.flush()
    await append_planner_session_event(
        session,
        planner_session=planner_session,
        event_type=PLANNER_EVENT_SESSION_CREATED,
        recommendation_id=active_stop.eventId if active_stop else None,
        metadata={
            "activeStopEventId": active_stop.eventId if active_stop else None,
            "routeStopCount": len(planner.stops),
        },
    )
    return planner_session


async def append_planner_session_event(
    session: AsyncSession,
    *,
    planner_session: PlannerSession,
    event_type: str,
    recommendation_id: str | None,
    metadata: dict | None = None,
) -> PlannerSessionEvent:
    row = PlannerSessionEvent(
        session_id=planner_session.id,
        event_type=event_type,
        recommendation_id=recommendation_id,
        metadata_json=metadata or {},
        created_at=datetime.now(tz=UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def append_planner_action_event(
    session: AsyncSession,
    *,
    user_id: str,
    planner_session_id: str | None,
    action: str,
    recommendation_id: str,
    metadata: dict | None = None,
) -> PlannerSession | None:
    event_type = planner_event_type_for_action(action)
    if event_type is None or not planner_session_id:
        return None

    planner_session = await session.get(PlannerSession, planner_session_id)
    if planner_session is None or planner_session.user_id != user_id:
        return None

    await append_planner_session_event(
        session,
        planner_session=planner_session,
        event_type=event_type,
        recommendation_id=recommendation_id,
        metadata=metadata,
    )

    events = await list_planner_session_events(session, planner_session.id)
    state = reduce_planner_session(planner_session, events)
    if event_type in {PLANNER_EVENT_STOP_SWAPPED, PLANNER_EVENT_STOP_ATTENDED, PLANNER_EVENT_STOP_SKIPPED}:
        recomposition = recompose_remaining_route(state, now_utc=datetime.now(tz=UTC))
        await append_planner_session_event(
            session,
            planner_session=planner_session,
            event_type=PLANNER_EVENT_ROUTE_RECOMPUTED,
            recommendation_id=recomposition.active_stop_event_id,
            metadata={
                "activeStopEventId": recomposition.active_stop_event_id,
                "sessionStatus": recomposition.session_status,
                "remainingStops": [_stop_dump(stop) for stop in recomposition.remaining_stops],
                "droppedStops": [_stop_dump(stop) for stop in recomposition.dropped_stops],
                "replacements": [_stop_dump(stop) for stop in recomposition.replacements],
                "reason": recomposition.reason,
            },
        )
        planner_session.active_stop_event_id = recomposition.active_stop_event_id
        planner_session.status = recomposition.session_status
    elif event_type in {PLANNER_EVENT_STOP_LOCKED, PLANNER_EVENT_STOP_SWAPPED}:
        planner_session.active_stop_event_id = recommendation_id

    await session.flush()
    return planner_session


async def list_planner_session_events(
    session: AsyncSession,
    planner_session_id: str,
) -> list[PlannerSessionEvent]:
    return list(
        (
            await session.scalars(
                select(PlannerSessionEvent)
                .where(PlannerSessionEvent.session_id == planner_session_id)
                .order_by(PlannerSessionEvent.created_at.asc(), PlannerSessionEvent.id.asc())
            )
        ).all()
    )


async def apply_planner_session_state(
    session: AsyncSession,
    *,
    planner: TonightPlannerResponse,
    planner_session: PlannerSession | None,
) -> TonightPlannerResponse:
    if planner_session is None:
        return planner

    events = await list_planner_session_events(session, planner_session.id)
    state = reduce_planner_session(planner_session, events)
    if not state.remaining_stops and planner_session.status == PLANNER_SESSION_ACTIVE:
        recomposition = recompose_remaining_route(state, now_utc=datetime.now(tz=UTC))
        state.remaining_stops = recomposition.remaining_stops
        state.dropped_stops = recomposition.dropped_stops
        state.replacements = recomposition.replacements
        state.recomposition_reason = recomposition.reason
        state.active_stop_event_id = recomposition.active_stop_event_id
        state.session_status = recomposition.session_status

    active_stop = _find_stop(state.current_route, state.active_stop_event_id)
    planner.sessionId = planner_session.id
    planner.sessionStatus = state.session_status
    planner.activeTargetEventId = state.active_stop_event_id
    planner.activeTargetVenueName = active_stop.venueName if active_stop else planner.activeTargetVenueName
    planner.activeStop = active_stop
    planner.remainingStops = state.remaining_stops
    planner.droppedStops = state.dropped_stops
    planner.recompositionReason = state.recomposition_reason
    planner.lastEventAt = _iso_or_none(state.last_event_at)
    if state.remaining_stops:
        planner.stops = state.remaining_stops
    return planner


def reduce_planner_session(
    planner_session: PlannerSession,
    events: list[PlannerSessionEvent],
) -> PlannerSessionState:
    initial_stops = _load_stops(planner_session.initial_route_snapshot.get("stops", []))
    state = PlannerSessionState(
        session_id=planner_session.id,
        session_status=planner_session.status,
        active_stop_event_id=planner_session.active_stop_event_id,
        initial_stops=initial_stops,
        current_route=[stop.model_copy(deep=True) for stop in initial_stops],
        remaining_stops=[stop.model_copy(deep=True) for stop in initial_stops],
        recomposition_reason=None,
    )

    for event in events:
        state.last_event_at = event.created_at
        metadata = event.metadata_json or {}
        recommendation_id = event.recommendation_id

        if event.event_type == PLANNER_EVENT_SESSION_CREATED:
            state.active_stop_event_id = metadata.get("activeStopEventId") or recommendation_id
        elif event.event_type == PLANNER_EVENT_STOP_LOCKED and recommendation_id:
            state.locked_event_ids.add(recommendation_id)
            state.active_stop_event_id = recommendation_id
        elif event.event_type == PLANNER_EVENT_STOP_SWAPPED and recommendation_id:
            state.swapped_event_ids.add(recommendation_id)
            state.current_route = _route_with_swap(state.current_route, state.initial_stops, recommendation_id)
            state.active_stop_event_id = recommendation_id
        elif event.event_type == PLANNER_EVENT_STOP_ATTENDED and recommendation_id:
            state.attended_event_ids.add(recommendation_id)
            state.active_stop_event_id = _next_route_event_id(state.current_route, recommendation_id, state)
        elif event.event_type == PLANNER_EVENT_STOP_SKIPPED and recommendation_id:
            state.skipped_event_ids.add(recommendation_id)
            state.active_stop_event_id = _next_route_event_id(state.current_route, recommendation_id, state)
        elif event.event_type == PLANNER_EVENT_ROUTE_RECOMPUTED:
            state.remaining_stops = _load_stops(metadata.get("remainingStops", []))
            state.dropped_stops = _load_stops(metadata.get("droppedStops", []))
            state.replacements = _load_stops(metadata.get("replacements", []))
            state.recomposition_reason = metadata.get("reason")
            state.active_stop_event_id = metadata.get("activeStopEventId")
            state.session_status = metadata.get("sessionStatus") or state.session_status
            if state.remaining_stops:
                state.current_route = [
                    stop
                    for stop in state.current_route
                    if stop.eventId in state.attended_event_ids
                ] + [stop.model_copy(deep=True) for stop in state.remaining_stops]

    if not state.remaining_stops:
        state.remaining_stops = [
            stop.model_copy(deep=True)
            for stop in state.current_route
            if stop.eventId not in state.attended_event_ids and stop.eventId not in state.skipped_event_ids
        ]
    for stop in state.current_route:
        stop.selected = stop.eventId == state.active_stop_event_id or stop.eventId in state.locked_event_ids
    return state


def recompose_remaining_route(
    state: PlannerSessionState,
    *,
    now_utc: datetime,
) -> PlannerRecomposition:
    previous_stop = _previous_context_stop(state)
    exhausted_event_ids = state.attended_event_ids | state.skipped_event_ids
    candidates = [
        stop.model_copy(deep=True)
        for stop in state.current_route
        if stop.eventId not in exhausted_event_ids and _is_time_viable(stop, now_utc)
    ]

    replacements: list[TonightPlannerStop] = []
    dropped: list[TonightPlannerStop] = []
    for stop in state.current_route:
        if stop.eventId in state.attended_event_ids:
            continue
        if stop.eventId in state.skipped_event_ids or not _is_time_viable(stop, now_utc):
            dropped.append(stop.model_copy(deep=True))
            replacement = _best_fallback_replacement(
                stop,
                previous_stop=previous_stop,
                exhausted_event_ids=exhausted_event_ids | {candidate.eventId for candidate in candidates},
                now_utc=now_utc,
            )
            if replacement is not None:
                replacements.append(replacement)
                candidates.append(replacement)

    ranked = sorted(
        candidates,
        key=lambda stop: _remaining_stop_score(stop, previous_stop=previous_stop, now_utc=now_utc),
        reverse=True,
    )
    ordered = _order_remaining_stops(ranked)
    active_stop_event_id = ordered[0].eventId if ordered else None
    for stop in ordered:
        stop.selected = stop.eventId == active_stop_event_id

    if ordered:
        reason_parts = ["Pulse recomposed the remaining route around live timing"]
        if previous_stop:
            reason_parts.append(f"continuity from {previous_stop.venueName}")
        if replacements:
            reason_parts.append(f"{len(replacements)} replacement option")
        if dropped:
            reason_parts.append(f"{len(dropped)} dropped stop")
        reason = ", ".join(reason_parts) + "."
        status = PLANNER_SESSION_ACTIVE
    else:
        reason = "Pulse could not find a viable remaining stop after timing, fallback exhaustion, and continuity checks."
        status = PLANNER_SESSION_EXHAUSTED

    return PlannerRecomposition(
        remaining_stops=ordered,
        dropped_stops=dropped,
        replacements=replacements,
        reason=reason,
        active_stop_event_id=active_stop_event_id,
        session_status=status,
    )


def _initial_active_stop(stops: list[TonightPlannerStop]) -> TonightPlannerStop | None:
    return next((stop for stop in stops if stop.role == "main_event"), stops[0] if stops else None)


def _load_stops(payload: list[dict]) -> list[TonightPlannerStop]:
    return [TonightPlannerStop(**item) for item in payload]


def _stop_dump(stop: TonightPlannerStop) -> dict:
    return stop.model_dump(mode="json")


def _route_with_swap(
    current_route: list[TonightPlannerStop],
    initial_stops: list[TonightPlannerStop],
    recommendation_id: str,
) -> list[TonightPlannerStop]:
    if _find_stop(current_route, recommendation_id):
        return [stop.model_copy(deep=True) for stop in current_route]

    for index, stop in enumerate(current_route):
        fallback = _find_fallback([stop], recommendation_id) or _find_fallback(initial_stops, recommendation_id)
        if fallback is None:
            continue
        replacement = _fallback_to_stop(fallback, parent=stop)
        return [
            *(item.model_copy(deep=True) for item in current_route[:index]),
            replacement,
            *(item.model_copy(deep=True) for item in current_route[index + 1 :]),
        ]
    return [stop.model_copy(deep=True) for stop in current_route]


def _fallback_to_stop(
    fallback: TonightPlannerFallbackOption,
    *,
    parent: TonightPlannerStop,
) -> TonightPlannerStop:
    return TonightPlannerStop(
        role=parent.role,
        roleLabel=parent.roleLabel,
        venueId=fallback.venueId,
        venueName=fallback.venueName,
        eventId=fallback.eventId,
        eventTitle=fallback.eventTitle,
        neighborhood=fallback.neighborhood,
        startsAt=fallback.startsAt,
        priceLabel=fallback.priceLabel,
        scoreBand=fallback.scoreBand,
        hopLabel=fallback.hopLabel,
        roleReason=fallback.fallbackReason,
        confidence="medium",
        confidenceLabel="Recomputed fit",
        confidenceReason="Selected from planner fallback options after execution changed.",
        selected=False,
        fallbacks=[],
    )


def _find_stop(stops: list[TonightPlannerStop], event_id: str | None) -> TonightPlannerStop | None:
    if not event_id:
        return None
    return next((stop for stop in stops if stop.eventId == event_id), None)


def _find_fallback(
    stops: list[TonightPlannerStop],
    event_id: str,
) -> TonightPlannerFallbackOption | None:
    return next((fallback for stop in stops for fallback in stop.fallbacks if fallback.eventId == event_id), None)


def _next_route_event_id(
    route: list[TonightPlannerStop],
    current_event_id: str,
    state: PlannerSessionState,
) -> str | None:
    blocked = state.attended_event_ids | state.skipped_event_ids
    for index, stop in enumerate(route):
        if stop.eventId != current_event_id:
            continue
        for next_stop in route[index + 1 :]:
            if next_stop.eventId not in blocked:
                return next_stop.eventId
    return next((stop.eventId for stop in route if stop.eventId not in blocked), None)


def _previous_context_stop(state: PlannerSessionState) -> TonightPlannerStop | None:
    attended = [_find_stop(state.current_route, event_id) for event_id in state.attended_event_ids]
    return next((stop for stop in reversed(attended) if stop is not None), None)


def _best_fallback_replacement(
    stop: TonightPlannerStop,
    *,
    previous_stop: TonightPlannerStop | None,
    exhausted_event_ids: set[str],
    now_utc: datetime,
) -> TonightPlannerStop | None:
    options = [
        _fallback_to_stop(fallback, parent=stop)
        for fallback in stop.fallbacks
        if fallback.eventId not in exhausted_event_ids and _is_time_viable(fallback, now_utc)
    ]
    if not options:
        return None
    return max(options, key=lambda option: _remaining_stop_score(option, previous_stop=previous_stop, now_utc=now_utc))


def _order_remaining_stops(stops: list[TonightPlannerStop]) -> list[TonightPlannerStop]:
    role_order = {"pregame": 0, "main_event": 1, "late_option": 2, "backup": 3}
    return sorted(stops, key=lambda stop: (role_order.get(stop.role, 5), _start_timestamp(stop)))


def _remaining_stop_score(
    stop: TonightPlannerStop,
    *,
    previous_stop: TonightPlannerStop | None,
    now_utc: datetime,
) -> float:
    score = 0.0
    score += {"high": 0.32, "medium": 0.22, "low": 0.12}.get(stop.scoreBand, 0.16)
    score += {"high": 0.18, "medium": 0.12, "watch": 0.04}.get(stop.confidence, 0.08)
    score += _budget_fit_for_label(stop.priceLabel) * 0.18
    score += _time_viability_score(stop, now_utc) * 0.14
    score += _hop_fit(stop.hopLabel) * 0.1
    if previous_stop and previous_stop.neighborhood == stop.neighborhood:
        score += 0.08
    elif previous_stop and _shared_boroughish_label(previous_stop.neighborhood, stop.neighborhood):
        score += 0.04
    return score


def _is_time_viable(
    stop: TonightPlannerStop | TonightPlannerFallbackOption,
    now_utc: datetime,
) -> bool:
    starts_at = _parse_start(stop.startsAt)
    if starts_at is None:
        return False
    return starts_at >= now_utc - timedelta(minutes=30)


def _time_viability_score(stop: TonightPlannerStop, now_utc: datetime) -> float:
    starts_at = _parse_start(stop.startsAt)
    if starts_at is None:
        return 0.0
    minutes_until = (starts_at - now_utc).total_seconds() / 60
    if 20 <= minutes_until <= 180:
        return 1.0
    if -30 <= minutes_until < 20 or 180 < minutes_until <= 300:
        return 0.72
    return 0.42


def _parse_start(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _start_timestamp(stop: TonightPlannerStop) -> float:
    starts_at = _parse_start(stop.startsAt)
    return starts_at.timestamp() if starts_at else float("inf")


def _budget_fit_for_label(price_label: str) -> float:
    prices = [float(match) for match in re.findall(r"\$?(\d+(?:\.\d+)?)", price_label or "")]
    if not prices:
        return 0.76
    price = max(prices)
    if price <= 30:
        return 1.0
    if price <= 75:
        return 0.78
    return 0.42


def _hop_fit(label: str | None) -> float:
    if not label:
        return 0.62
    match = re.search(r"(\d+)", label)
    if not match:
        return 0.62
    minutes = int(match.group(1))
    if minutes <= 20:
        return 1.0
    if minutes <= 35:
        return 0.82
    if minutes <= 50:
        return 0.62
    return 0.42


def _shared_boroughish_label(left: str, right: str) -> bool:
    left_lower = left.lower()
    right_lower = right.lower()
    return any(token in left_lower and token in right_lower for token in ["bushwick", "brooklyn", "lower", "east", "greenpoint"])


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()

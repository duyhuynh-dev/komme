from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation import PlannerSession, PlannerSessionEvent
from app.schemas.recommendations import (
    PlannerSessionDebugEvent,
    PlannerSessionDebugItem,
    PlannerSessionDebugResponse,
    PlannerSessionDebugStopScore,
    TonightPlannerFallbackOption,
    TonightPlannerResponse,
    TonightPlannerStop,
)

PLANNER_SESSION_ACTIVE = "active"
PLANNER_SESSION_COMPLETED = "completed"
PLANNER_SESSION_EXPIRED = "expired"

PLANNER_SESSION_MAX_AGE = timedelta(hours=48)
PLANNER_SESSION_PLAN_END_GRACE = timedelta(hours=4)

PLANNER_EVENT_SESSION_CREATED = "session_created"
PLANNER_EVENT_STOP_LOCKED = "stop_locked"
PLANNER_EVENT_STOP_SWAPPED = "stop_swapped"
PLANNER_EVENT_STOP_ATTENDED = "stop_attended"
PLANNER_EVENT_STOP_SKIPPED = "stop_skipped"
PLANNER_EVENT_ROUTE_RECOMPUTED = "route_recomputed"
PLANNER_EVENT_SESSION_COMPLETED = "session_completed"
PLANNER_EVENT_SESSION_EXPIRED = "session_expired"


@dataclass
class PlannerRecomposition:
    remaining_stops: list[TonightPlannerStop] = field(default_factory=list)
    dropped_stops: list[TonightPlannerStop] = field(default_factory=list)
    replacements: list[TonightPlannerStop] = field(default_factory=list)
    reason: str = "Pulse kept the remaining route as-is."
    active_stop_event_id: str | None = None
    session_status: str = PLANNER_SESSION_ACTIVE
    diagnostics: list[dict] = field(default_factory=list)


@dataclass
class PlannerSessionState:
    session_id: str
    session_status: str
    active_stop_event_id: str | None
    initial_stops: list[TonightPlannerStop]
    current_route: list[TonightPlannerStop]
    plan_window_start: str | None = None
    plan_window_end: str | None = None
    plan_window_label: str | None = None
    attended_event_ids: set[str] = field(default_factory=set)
    skipped_event_ids: set[str] = field(default_factory=set)
    locked_event_ids: set[str] = field(default_factory=set)
    swapped_event_ids: set[str] = field(default_factory=set)
    remaining_stops: list[TonightPlannerStop] = field(default_factory=list)
    dropped_stops: list[TonightPlannerStop] = field(default_factory=list)
    replacements: list[TonightPlannerStop] = field(default_factory=list)
    recomposition_reason: str | None = None
    lifecycle_reason: str | None = None
    created_fresh_because_stale: bool = False
    replaced_session_id: str | None = None
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

    now_utc = datetime.now(tz=UTC)
    stale_session = await expire_stale_planner_sessions(
        session,
        user_id=user_id,
        current_planner=planner,
        now_utc=now_utc,
    )

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
        events = await list_planner_session_events(session, existing.id)
        lifecycle = evaluate_session_lifecycle(
            existing,
            reduce_planner_session(existing, events),
            current_planner=planner,
            now_utc=now_utc,
        )
        if lifecycle is not None:
            await mark_planner_session_lifecycle(
                session,
                planner_session=existing,
                status=lifecycle["status"],
                reason=lifecycle["reason"],
                event_type=lifecycle["eventType"],
                metadata={"rule": lifecycle["rule"], "replacementContextHash": recommendation_context_hash},
            )
            stale_session = existing
        else:
            return existing

    fresh_reason = None
    if stale_session is not None:
        fresh_reason = (
            f"Created a fresh event plan because prior session {stale_session.id} "
            f"was {stale_session.status}."
        )

    active_stop = _initial_active_stop(planner.stops)
    planner_session = PlannerSession(
        user_id=user_id,
        recommendation_run_id=recommendation_run_id,
        recommendation_context_hash=recommendation_context_hash,
        initial_route_snapshot={
            "status": planner.status,
            "summary": planner.summary,
            "planningNote": planner.planningNote,
            "planWindowStart": planner.planWindowStart,
            "planWindowEnd": planner.planWindowEnd,
            "planWindowLabel": planner.planWindowLabel,
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
            "planWindowStart": planner.planWindowStart,
            "planWindowEnd": planner.planWindowEnd,
            "planWindowLabel": planner.planWindowLabel,
            "createdFreshBecauseStale": stale_session is not None,
            "replacedSessionId": stale_session.id if stale_session is not None else None,
            "lifecycleReason": fresh_reason,
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
    if planner_session.status != PLANNER_SESSION_ACTIVE:
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
                "scores": recomposition.diagnostics,
            },
        )
        planner_session.active_stop_event_id = recomposition.active_stop_event_id
        if recomposition.session_status == PLANNER_SESSION_ACTIVE:
            planner_session.status = PLANNER_SESSION_ACTIVE
        else:
            lifecycle = evaluate_session_lifecycle(
                planner_session,
                state,
                current_planner=None,
                now_utc=datetime.now(tz=UTC),
            ) or _lifecycle_decision(
                status=PLANNER_SESSION_EXPIRED,
                event_type=PLANNER_EVENT_SESSION_EXPIRED,
                rule="route_recomputed_empty",
                reason=recomposition.reason,
            )
            await mark_planner_session_lifecycle(
                session,
                planner_session=planner_session,
                status=lifecycle["status"],
                reason=lifecycle["reason"],
                event_type=lifecycle["eventType"],
                metadata={"rule": lifecycle["rule"]},
            )
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
    planner.lifecycleReason = state.lifecycle_reason
    planner.createdFreshBecauseStale = state.created_fresh_because_stale
    planner.lastEventAt = _iso_or_none(state.last_event_at)
    if state.remaining_stops:
        planner.stops = state.remaining_stops
    return planner


def reduce_planner_session(
    planner_session: PlannerSession,
    events: list[PlannerSessionEvent],
) -> PlannerSessionState:
    snapshot = planner_session.initial_route_snapshot or {}
    initial_stops = _load_stops(snapshot.get("stops", []))
    state = PlannerSessionState(
        session_id=planner_session.id,
        session_status=planner_session.status,
        active_stop_event_id=planner_session.active_stop_event_id,
        initial_stops=initial_stops,
        current_route=[stop.model_copy(deep=True) for stop in initial_stops],
        plan_window_start=snapshot.get("planWindowStart"),
        plan_window_end=snapshot.get("planWindowEnd"),
        plan_window_label=snapshot.get("planWindowLabel"),
        remaining_stops=[stop.model_copy(deep=True) for stop in initial_stops],
        recomposition_reason=None,
    )

    for event in events:
        state.last_event_at = event.created_at
        metadata = event.metadata_json or {}
        recommendation_id = event.recommendation_id

        if event.event_type == PLANNER_EVENT_SESSION_CREATED:
            state.active_stop_event_id = metadata.get("activeStopEventId") or recommendation_id
            state.plan_window_start = metadata.get("planWindowStart") or state.plan_window_start
            state.plan_window_end = metadata.get("planWindowEnd") or state.plan_window_end
            state.plan_window_label = metadata.get("planWindowLabel") or state.plan_window_label
            state.created_fresh_because_stale = bool(metadata.get("createdFreshBecauseStale"))
            state.replaced_session_id = metadata.get("replacedSessionId")
            if metadata.get("lifecycleReason"):
                state.lifecycle_reason = metadata.get("lifecycleReason")
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
        elif event.event_type in {PLANNER_EVENT_SESSION_COMPLETED, PLANNER_EVENT_SESSION_EXPIRED}:
            state.session_status = metadata.get("sessionStatus") or (
                PLANNER_SESSION_COMPLETED
                if event.event_type == PLANNER_EVENT_SESSION_COMPLETED
                else PLANNER_SESSION_EXPIRED
            )
            state.lifecycle_reason = metadata.get("reason")
            state.active_stop_event_id = None
            state.remaining_stops = []

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
        status = PLANNER_SESSION_EXPIRED

    return PlannerRecomposition(
        remaining_stops=ordered,
        dropped_stops=dropped,
        replacements=replacements,
        reason=reason,
        active_stop_event_id=active_stop_event_id,
        session_status=status,
        diagnostics=[
            _score_diagnostics(stop, previous_stop=previous_stop, now_utc=now_utc)
            for stop in ordered
        ],
    )


async def get_planner_session_debug(
    session: AsyncSession,
    *,
    user_id: str,
    limit: int = 5,
) -> PlannerSessionDebugResponse:
    planner_sessions = list(
        (
            await session.scalars(
                select(PlannerSession)
                .where(PlannerSession.user_id == user_id)
                .order_by(desc(PlannerSession.updated_at), desc(PlannerSession.created_at))
                .limit(limit)
            )
        ).all()
    )

    items: list[PlannerSessionDebugItem] = []
    for planner_session in planner_sessions:
        events = await list_planner_session_events(session, planner_session.id)
        state = reduce_planner_session(planner_session, events)
        latest_recomposition = _latest_recomposition_event(events)
        latest_recomposition_metadata = latest_recomposition.metadata_json if latest_recomposition else {}
        scores = [
            PlannerSessionDebugStopScore(
                eventId=str(item.get("eventId") or ""),
                venueName=str(item.get("venueName") or "Unknown venue"),
                role=str(item.get("role") or "stop"),
                score=float(item.get("score") or 0.0),
                reasons=[str(reason) for reason in item.get("reasons", [])],
            )
            for item in latest_recomposition_metadata.get("scores", [])
        ]
        items.append(
            PlannerSessionDebugItem(
                sessionId=planner_session.id,
                sessionStatus=state.session_status,
                recommendationRunId=planner_session.recommendation_run_id,
                contextHash=planner_session.recommendation_context_hash,
                activeStopEventId=state.active_stop_event_id,
                budgetLevel=planner_session.budget_level,
                timezone=planner_session.timezone,
                planWindowStart=state.plan_window_start,
                planWindowEnd=state.plan_window_end,
                planWindowLabel=state.plan_window_label,
                createdAt=_iso_or_none(planner_session.created_at) or "",
                updatedAt=_iso_or_none(planner_session.updated_at) or "",
                initialStopCount=len(state.initial_stops),
                remainingStopCount=len(state.remaining_stops),
                droppedStopCount=len(state.dropped_stops),
                recompositionReason=state.recomposition_reason,
                lifecycleReason=state.lifecycle_reason,
                createdFreshBecauseStale=state.created_fresh_because_stale,
                replacedSessionId=state.replaced_session_id,
                recompositionScores=scores,
                events=[
                    PlannerSessionDebugEvent(
                        eventId=event.id,
                        eventType=event.event_type,
                        recommendationId=event.recommendation_id,
                        createdAt=_iso_or_none(event.created_at) or "",
                        metadata=event.metadata_json or {},
                    )
                    for event in events
                ],
            )
        )
    return PlannerSessionDebugResponse(sessions=items)


async def expire_stale_planner_sessions(
    session: AsyncSession,
    *,
    user_id: str,
    current_planner: TonightPlannerResponse | None,
    now_utc: datetime,
) -> PlannerSession | None:
    stale_session: PlannerSession | None = None
    active_sessions = list(
        (
            await session.scalars(
                select(PlannerSession)
                .where(
                    PlannerSession.user_id == user_id,
                    PlannerSession.status == PLANNER_SESSION_ACTIVE,
                )
                .order_by(desc(PlannerSession.created_at), desc(PlannerSession.id))
            )
        ).all()
    )
    for planner_session in active_sessions:
        events = await list_planner_session_events(session, planner_session.id)
        state = reduce_planner_session(planner_session, events)
        lifecycle = evaluate_session_lifecycle(
            planner_session,
            state,
            current_planner=current_planner,
            now_utc=now_utc,
        )
        if lifecycle is None:
            continue
        await mark_planner_session_lifecycle(
            session,
            planner_session=planner_session,
            status=lifecycle["status"],
            reason=lifecycle["reason"],
            event_type=lifecycle["eventType"],
            metadata={"rule": lifecycle["rule"]},
        )
        stale_session = planner_session
    return stale_session


async def mark_planner_session_lifecycle(
    session: AsyncSession,
    *,
    planner_session: PlannerSession,
    status: str,
    reason: str,
    event_type: str,
    metadata: dict | None = None,
) -> PlannerSessionEvent:
    planner_session.status = status
    planner_session.active_stop_event_id = None
    payload = {
        "sessionStatus": status,
        "reason": reason,
        **(metadata or {}),
    }
    return await append_planner_session_event(
        session,
        planner_session=planner_session,
        event_type=event_type,
        recommendation_id=None,
        metadata=payload,
    )


def evaluate_session_lifecycle(
    planner_session: PlannerSession,
    state: PlannerSessionState,
    *,
    current_planner: TonightPlannerResponse | None,
    now_utc: datetime,
) -> dict | None:
    if planner_session.status != PLANNER_SESSION_ACTIVE and state.session_status != PLANNER_SESSION_ACTIVE:
        return None

    created_at = _timestamp_utc(planner_session.created_at)
    if now_utc - created_at > PLANNER_SESSION_MAX_AGE:
        return _lifecycle_decision(
            status=PLANNER_SESSION_EXPIRED,
            event_type=PLANNER_EVENT_SESSION_EXPIRED,
            rule="session_age",
            reason="Planner session expired because it exceeded the 48-hour execution window.",
        )

    plan_end = _plan_window_end(state.initial_stops)
    if plan_end is not None and now_utc > plan_end:
        return _lifecycle_decision(
            status=PLANNER_SESSION_EXPIRED,
            event_type=PLANNER_EVENT_SESSION_EXPIRED,
            rule="plan_window_end",
            reason="Planner session expired because its event plan window has passed.",
        )

    route_event_ids = {stop.eventId for stop in state.current_route}
    resolved_event_ids = state.attended_event_ids | state.skipped_event_ids
    if route_event_ids and route_event_ids.issubset(resolved_event_ids):
        return _lifecycle_decision(
            status=PLANNER_SESSION_COMPLETED,
            event_type=PLANNER_EVENT_SESSION_COMPLETED,
            rule="all_stops_resolved",
            reason="Planner session completed because every route stop was attended or skipped.",
        )

    unresolved_stops = [
        stop
        for stop in state.current_route
        if stop.eventId not in resolved_event_ids
    ]
    if unresolved_stops and not any(_is_time_viable(stop, now_utc) for stop in unresolved_stops):
        return _lifecycle_decision(
            status=PLANNER_SESSION_EXPIRED,
            event_type=PLANNER_EVENT_SESSION_EXPIRED,
            rule="route_not_viable",
            reason="Planner session expired because no unresolved route stop is still time-viable.",
        )

    if current_planner is not None and current_planner.stops:
        if _plan_windows_conflict(state, current_planner):
            return _lifecycle_decision(
                status=PLANNER_SESSION_EXPIRED,
                event_type=PLANNER_EVENT_SESSION_EXPIRED,
                rule="planning_window_changed",
                reason="Planner session expired because the requested event plan window changed.",
            )

        current_event_ids = {stop.eventId for stop in current_planner.stops}
        if route_event_ids and route_event_ids.isdisjoint(current_event_ids):
            return _lifecycle_decision(
                status=PLANNER_SESSION_EXPIRED,
                event_type=PLANNER_EVENT_SESSION_EXPIRED,
                rule="planning_window_changed",
                reason="Planner session expired because the current planning window no longer overlaps its route.",
            )

    return None


def _plan_windows_conflict(
    state: PlannerSessionState,
    current_planner: TonightPlannerResponse,
) -> bool:
    stored_window = (state.plan_window_start, state.plan_window_end)
    current_window = (current_planner.planWindowStart, current_planner.planWindowEnd)
    if not any(stored_window) or not any(current_window):
        return False
    return stored_window != current_window


def _lifecycle_decision(
    *,
    status: str,
    event_type: str,
    rule: str,
    reason: str,
) -> dict:
    return {
        "status": status,
        "eventType": event_type,
        "rule": rule,
        "reason": reason,
    }


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


def _score_diagnostics(
    stop: TonightPlannerStop,
    *,
    previous_stop: TonightPlannerStop | None,
    now_utc: datetime,
) -> dict:
    score = _remaining_stop_score(stop, previous_stop=previous_stop, now_utc=now_utc)
    reasons = [
        f"{stop.scoreBand} shortlist band",
        f"{stop.confidence} planner confidence",
        f"budget fit {_budget_fit_for_label(stop.priceLabel):.2f}",
        f"time viability {_time_viability_score(stop, now_utc):.2f}",
        f"travel continuity {_hop_fit(stop.hopLabel):.2f}",
    ]
    if previous_stop and previous_stop.neighborhood == stop.neighborhood:
        reasons.append(f"same-neighborhood continuity from {previous_stop.venueName}")
    elif previous_stop:
        reasons.append(f"neighborhood continuity checked against {previous_stop.venueName}")
    return {
        "eventId": stop.eventId,
        "venueName": stop.venueName,
        "role": stop.role,
        "score": round(score, 3),
        "reasons": reasons,
    }


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


def _plan_window_end(stops: list[TonightPlannerStop]) -> datetime | None:
    starts = [_parse_start(stop.startsAt) for stop in stops]
    viable_starts = [start for start in starts if start is not None]
    if not viable_starts:
        return None
    return max(viable_starts) + PLANNER_SESSION_PLAN_END_GRACE


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


def _latest_recomposition_event(events: list[PlannerSessionEvent]) -> PlannerSessionEvent | None:
    return next(
        (event for event in reversed(events) if event.event_type == PLANNER_EVENT_ROUTE_RECOMPUTED),
        None,
    )


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _timestamp_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

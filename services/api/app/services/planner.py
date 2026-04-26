from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.schemas.recommendations import (
    MapVenuePin,
    TonightPlannerFallbackOption,
    TonightPlannerRerouteOption,
    TonightPlannerResponse,
    TonightPlannerStop,
    VenueRecommendationCard,
)
from app.services.travel import estimate_travel_bands, haversine_miles


@dataclass(frozen=True)
class PlannerCandidate:
    card: VenueRecommendationCard
    pin: MapVenuePin
    shortlist_index: int
    start_local: datetime
    anchor_hop_label: str | None
    anchor_hop_minutes: int
    budget_fit: float
    source_confidence: float
    tonight: bool


@dataclass(frozen=True)
class PlannerSelection:
    role: str
    roleLabel: str
    candidate: PlannerCandidate
    role_score: float


def build_tonight_planner(
    items: list[VenueRecommendationCard],
    pins: list[MapVenuePin],
    *,
    budget_level: str = "under_75",
    timezone: str = "America/New_York",
    now_utc: datetime | None = None,
    selected_recommendation_id: str | None = None,
    selected_action: str | None = None,
    outcome_recommendation_id: str | None = None,
    outcome_action: str | None = None,
) -> TonightPlannerResponse:
    if not items:
        return TonightPlannerResponse(
            summary="Pulse needs a live shortlist before it can sketch out tonight.",
            planningNote="Refresh the shortlist once fresh events are in, then Pulse can build a sequence.",
        )

    zone = _planner_timezone(timezone)
    current_utc = now_utc or datetime.now(tz=UTC)
    now_local = current_utc.astimezone(zone)
    tonight_start, tonight_end = _tonight_window(now_local, zone)
    pin_by_venue_id = {pin.venueId: pin for pin in pins}

    candidates: list[PlannerCandidate] = []
    for shortlist_index, card in enumerate(items):
        pin = pin_by_venue_id.get(card.venueId)
        if pin is None:
            continue

        start_local = _parse_local_start(card.startsAt, zone)
        if start_local is None:
            continue
        if start_local < now_local - timedelta(minutes=30):
            continue
        if start_local > now_local + timedelta(hours=36):
            continue

        anchor_hop_label, anchor_hop_minutes = _anchor_hop(card)
        candidates.append(
            PlannerCandidate(
                card=card,
                pin=pin,
                shortlist_index=shortlist_index,
                start_local=start_local,
                anchor_hop_label=anchor_hop_label,
                anchor_hop_minutes=anchor_hop_minutes,
                budget_fit=_budget_fit_for_label(budget_level, card.priceLabel),
                source_confidence=card.provenance.sourceConfidence,
                tonight=tonight_start <= start_local <= tonight_end,
            )
        )

    if not candidates:
        return TonightPlannerResponse(
            summary="Pulse could not find a workable tonight window in the current shortlist.",
            planningNote="Try checking for new events or refreshing the shortlist once more options land.",
        )

    tonight_candidates = [candidate for candidate in candidates if candidate.tonight]
    scoped_candidates = tonight_candidates if len(tonight_candidates) >= 2 else candidates
    using_tonight_window = len(tonight_candidates) >= 2

    main_event = _pick_best(
        scoped_candidates,
        lambda candidate: _main_event_score(candidate, using_tonight_window=using_tonight_window),
    )
    if main_event is None:
        return TonightPlannerResponse(
            status="limited",
            summary="Pulse found shortlist events, but not a strong anchor stop for tonight yet.",
            planningNote="The shortlist needs one clearer anchor before the planner can build a fuller night.",
        )

    remaining = [candidate for candidate in scoped_candidates if candidate.card.venueId != main_event.card.venueId]
    pregame = _pick_best(remaining, lambda candidate: _pregame_score(candidate, main_event))
    pregame_score = _pregame_score(pregame, main_event) if pregame is not None else 0.0

    trailing_pool = [
        candidate
        for candidate in remaining
        if pregame is None or candidate.card.venueId != pregame.card.venueId
    ]
    late_option = _pick_best(trailing_pool, lambda candidate: _late_option_score(candidate, main_event))
    late_option_score = _late_option_score(late_option, main_event) if late_option is not None else 0.0
    backup = _pick_best(trailing_pool, lambda candidate: _backup_score(candidate, main_event))
    backup_score = _backup_score(backup, main_event) if backup is not None else 0.0

    selections: list[PlannerSelection] = []
    if pregame is not None and pregame_score >= 0.52:
        selections.append(
            PlannerSelection(
                role="pregame",
                roleLabel="Pregame",
                candidate=pregame,
                role_score=pregame_score,
            )
        )

    main_score = _main_event_score(main_event, using_tonight_window=using_tonight_window)
    selections.append(
        PlannerSelection(
            role="main_event",
            roleLabel="Main event",
            candidate=main_event,
            role_score=main_score,
        )
    )

    trailing_selection: PlannerSelection | None = None
    if late_option is not None and late_option_score >= 0.54:
        trailing_selection = PlannerSelection(
            role="late_option",
            roleLabel="Late option",
            candidate=late_option,
            role_score=late_option_score,
        )
    elif backup is not None and backup_score >= 0.48:
        trailing_selection = PlannerSelection(
            role="backup",
            roleLabel="Backup",
            candidate=backup,
            role_score=backup_score,
        )
    elif trailing_pool:
        fallback_backup = _pick_best(
            trailing_pool,
            lambda candidate: _backup_score(candidate, main_event),
        )
        if fallback_backup is not None:
            trailing_selection = PlannerSelection(
                role="backup",
                roleLabel="Backup",
                candidate=fallback_backup,
                role_score=_backup_score(fallback_backup, main_event),
            )

    if trailing_selection is not None and trailing_selection.candidate.card.venueId not in {
        selection.candidate.card.venueId for selection in selections
    }:
        selections.append(trailing_selection)

    used_venue_ids = {selection.candidate.card.venueId for selection in selections}
    stops: list[TonightPlannerStop] = []
    for index, selection in enumerate(selections):
        previous_candidate = selections[index - 1].candidate if index > 0 else None
        fallback_trigger = _fallback_trigger(selection)
        fallbacks = (
            _build_fallbacks(
                selection=selection,
                main_event=main_event,
                candidates=scoped_candidates,
                used_venue_ids=used_venue_ids,
                previous_candidate=previous_candidate,
                reason_key=fallback_trigger,
            )
            if fallback_trigger is not None
            else []
        )
        confidence, confidence_label, confidence_reason = _selection_confidence(selection)
        stops.append(
            TonightPlannerStop(
                role=selection.role,
                roleLabel=selection.roleLabel,
                venueId=selection.candidate.card.venueId,
                venueName=selection.candidate.card.venueName,
                eventId=selection.candidate.card.eventId,
                eventTitle=selection.candidate.card.eventTitle,
                neighborhood=selection.candidate.card.neighborhood,
                startsAt=selection.candidate.card.startsAt,
                priceLabel=selection.candidate.card.priceLabel,
                scoreBand=selection.candidate.card.scoreBand,
                hopLabel=_hop_label(previous_candidate, selection.candidate),
                roleReason=_role_reason(selection, main_event),
                confidence=confidence,
                confidenceLabel=confidence_label,
                confidenceReason=confidence_reason,
                fallbacks=fallbacks,
            )
        )

    status = "ready" if using_tonight_window and len(stops) >= 2 else "limited"
    summary = _planner_summary(stops)
    if status == "ready":
        planning_note = "Built from the current shortlist using start times, neighborhood hops, travel fit, and budget fit."
    elif using_tonight_window:
        planning_note = "Pulse found one clear anchor and kept the rest conservative where timing or confidence softened."
    else:
        planning_note = "Tonight looks thin in the live shortlist, so Pulse kept the plan light and surfaced backup options."

    planner = TonightPlannerResponse(
        status=status,
        summary=summary,
        planningNote=planning_note,
        stops=stops,
    )
    _apply_execution_state(
        planner,
        selected_recommendation_id=selected_recommendation_id,
        selected_action=selected_action,
    )
    _apply_outcome_state(
        planner,
        outcome_recommendation_id=outcome_recommendation_id,
        outcome_action=outcome_action,
    )
    _apply_reroute_state(planner)
    return planner


def _planner_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name or "America/New_York")
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/New_York")


def _tonight_window(now_local: datetime, zone: ZoneInfo) -> tuple[datetime, datetime]:
    anchor_day = now_local.date()
    if now_local.hour < 5:
        anchor_day = anchor_day - timedelta(days=1)

    start = datetime.combine(anchor_day, time(17, 0), tzinfo=zone)
    end = datetime.combine(anchor_day + timedelta(days=1), time(4, 0), tzinfo=zone)
    return start, end


def _parse_local_start(value: str, zone: ZoneInfo) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(zone)


def _anchor_hop(card: VenueRecommendationCard) -> tuple[str | None, int]:
    transit = next((band for band in card.travel if band.mode == "transit"), None)
    if transit is not None:
        return transit.label, transit.minutes
    if card.travel:
        return card.travel[0].label, card.travel[0].minutes
    return None, 45


def _pick_best(
    candidates: list[PlannerCandidate],
    scorer,
) -> PlannerCandidate | None:
    best: PlannerCandidate | None = None
    best_score = float("-inf")
    for candidate in candidates:
        score = scorer(candidate)
        if score > best_score:
            best = candidate
            best_score = score
            continue
        if best is not None and score == best_score and candidate.shortlist_index < best.shortlist_index:
            best = candidate
    return best


def _main_event_score(candidate: PlannerCandidate | None, *, using_tonight_window: bool) -> float:
    if candidate is None:
        return 0.0
    tonight_bonus = 0.08 if candidate.tonight and using_tonight_window else 0.0
    return (
        (candidate.card.score * 0.52)
        + (candidate.source_confidence * 0.16)
        + (_travel_fit(candidate.anchor_hop_minutes) * 0.1)
        + (candidate.budget_fit * 0.1)
        + (_main_time_fit(candidate.start_local) * 0.14)
        + tonight_bonus
    )


def _pregame_score(candidate: PlannerCandidate | None, main_event: PlannerCandidate) -> float:
    if candidate is None:
        return 0.0
    gap_minutes = _minutes_between(candidate.start_local, main_event.start_local)
    if gap_minutes < 35 or gap_minutes > 270:
        return 0.0
    return (
        (candidate.card.score * 0.28)
        + (candidate.budget_fit * 0.22)
        + (_travel_fit(candidate.anchor_hop_minutes) * 0.15)
        + (_proximity_fit(candidate.pin, main_event.pin) * 0.22)
        + (_pregame_gap_fit(gap_minutes) * 0.13)
    )


def _late_option_score(candidate: PlannerCandidate | None, main_event: PlannerCandidate) -> float:
    if candidate is None:
        return 0.0
    gap_minutes = _minutes_between(main_event.start_local, candidate.start_local)
    if gap_minutes < 45 or gap_minutes > 240:
        return 0.0
    return (
        (candidate.card.score * 0.28)
        + (_travel_fit(candidate.anchor_hop_minutes) * 0.12)
        + (_proximity_fit(main_event.pin, candidate.pin) * 0.24)
        + (candidate.budget_fit * 0.12)
        + (_late_gap_fit(gap_minutes) * 0.14)
        + (_late_time_fit(candidate.start_local) * 0.1)
    )


def _backup_score(candidate: PlannerCandidate | None, main_event: PlannerCandidate) -> float:
    if candidate is None:
        return 0.0
    gap_minutes = abs(_minutes_between(candidate.start_local, main_event.start_local))
    return (
        (candidate.card.score * 0.34)
        + (candidate.source_confidence * 0.14)
        + (_travel_fit(candidate.anchor_hop_minutes) * 0.08)
        + (_proximity_fit(candidate.pin, main_event.pin) * 0.16)
        + (candidate.budget_fit * 0.1)
        + (_backup_gap_fit(gap_minutes) * 0.18)
    )


def _travel_fit(minutes: int) -> float:
    if minutes <= 20:
        return 0.96
    if minutes <= 35:
        return 0.84
    if minutes <= 50:
        return 0.68
    return 0.5


def _proximity_fit(left: MapVenuePin, right: MapVenuePin) -> float:
    distance = haversine_miles(left.latitude, left.longitude, right.latitude, right.longitude)
    if distance <= 1.0:
        return 0.98
    if distance <= 2.2:
        return 0.88
    if distance <= 3.8:
        return 0.74
    if distance <= 5.4:
        return 0.58
    return 0.4


def _main_time_fit(start_local: datetime) -> float:
    hour = _night_hour(start_local)
    if 18.0 <= hour <= 21.5:
        return 1.0
    if 17.0 <= hour < 18.0 or 21.5 < hour <= 23.0:
        return 0.82
    if 23.0 < hour <= 25.0:
        return 0.6
    return 0.42


def _pregame_gap_fit(gap_minutes: int) -> float:
    if 50 <= gap_minutes <= 150:
        return 1.0
    if 35 <= gap_minutes < 50 or 150 < gap_minutes <= 210:
        return 0.76
    if 210 < gap_minutes <= 270:
        return 0.54
    return 0.0


def _late_gap_fit(gap_minutes: int) -> float:
    if 60 <= gap_minutes <= 150:
        return 1.0
    if 45 <= gap_minutes < 60 or 150 < gap_minutes <= 210:
        return 0.72
    return 0.0


def _late_time_fit(start_local: datetime) -> float:
    hour = _night_hour(start_local)
    if 22.0 <= hour <= 24.5:
        return 1.0
    if 21.0 <= hour < 22.0 or 24.5 < hour <= 26.0:
        return 0.74
    return 0.48


def _backup_gap_fit(gap_minutes: int) -> float:
    if gap_minutes <= 75:
        return 1.0
    if gap_minutes <= 140:
        return 0.78
    if gap_minutes <= 220:
        return 0.56
    return 0.34


def _night_hour(start_local: datetime) -> float:
    hour = start_local.hour + (start_local.minute / 60)
    if hour < 5:
        hour += 24
    return hour


def _selection_confidence(selection: PlannerSelection) -> tuple[str, str, str]:
    candidate = selection.candidate
    watch_reasons: list[str] = []
    medium_reasons: list[str] = []

    if selection.role == "backup":
        watch_reasons.append("this stop is intentionally held as the pivot")
    if candidate.source_confidence < 0.72:
        watch_reasons.append("source confidence is softer here")
    if selection.role == "late_option" and _night_hour(candidate.start_local) >= 23.5:
        watch_reasons.append("timing pushes late into the night")
    if candidate.budget_fit < 0.58:
        medium_reasons.append("price fit is looser")
    if candidate.card.score < 0.66 or selection.role_score < 0.54:
        medium_reasons.append("the fit is thinner than the main anchor")

    if watch_reasons:
        return "watch", "Keep a backup ready", _join_fragments(watch_reasons + medium_reasons)
    if medium_reasons:
        return "medium", "Good fit", _join_fragments(medium_reasons)
    if selection.role == "main_event":
        return "high", "Confident anchor", "This is the strongest mix of shortlist score, trust, timing, and travel fit."
    return "high", "Strong fit", "Timing, travel, and price all line up cleanly for this stop."


def _fallback_trigger(selection: PlannerSelection) -> str | None:
    candidate = selection.candidate
    if selection.role == "backup":
        return None
    if selection.role == "late_option" and _night_hour(candidate.start_local) >= 23.5:
        return "late"
    if candidate.source_confidence < 0.72:
        return "low_confidence"
    if candidate.budget_fit < 0.58:
        return "budget"
    if candidate.card.score < 0.66 or selection.role_score < 0.54:
        return "weak"
    return None


def _build_fallbacks(
    *,
    selection: PlannerSelection,
    main_event: PlannerCandidate,
    candidates: list[PlannerCandidate],
    used_venue_ids: set[str],
    previous_candidate: PlannerCandidate | None,
    reason_key: str,
) -> list[TonightPlannerFallbackOption]:
    fallback_pool = [candidate for candidate in candidates if candidate.card.venueId not in used_venue_ids]
    if not fallback_pool:
        return []

    if selection.role == "pregame":
        scorer = lambda candidate: _pregame_score(candidate, main_event)
    elif selection.role == "main_event":
        scorer = lambda candidate: max(
            _main_event_score(candidate, using_tonight_window=candidate.tonight),
            _backup_score(candidate, main_event),
        )
    else:
        scorer = lambda candidate: max(
            _late_option_score(candidate, main_event),
            _backup_score(candidate, main_event),
        )

    ranked_options = sorted(
        (
            (candidate, scorer(candidate))
            for candidate in fallback_pool
        ),
        key=lambda item: (item[1], -item[0].shortlist_index),
        reverse=True,
    )

    results: list[TonightPlannerFallbackOption] = []
    for candidate, score in ranked_options:
        if score < 0.44:
            continue
        results.append(
            TonightPlannerFallbackOption(
                venueId=candidate.card.venueId,
                venueName=candidate.card.venueName,
                eventId=candidate.card.eventId,
                eventTitle=candidate.card.eventTitle,
                neighborhood=candidate.card.neighborhood,
                startsAt=candidate.card.startsAt,
                priceLabel=candidate.card.priceLabel,
                scoreBand=candidate.card.scoreBand,
                hopLabel=_hop_label(previous_candidate, candidate),
                fallbackReason=_fallback_reason(reason_key, selection.candidate.card.venueName),
            )
        )
        if len(results) == 2:
            break

    return results


def _fallback_reason(reason_key: str, venue_name: str) -> str:
    if reason_key == "late":
        return f"Use this if {venue_name} starts too late to keep the night moving."
    if reason_key == "budget":
        return f"Use this if {venue_name} stretches the budget more than tonight should."
    if reason_key == "low_confidence":
        return f"Use this if {venue_name} feels less trustworthy once you check the details."
    return f"Use this if {venue_name} starts to look thin."


def _hop_label(previous_candidate: PlannerCandidate | None, candidate: PlannerCandidate) -> str | None:
    if previous_candidate is None:
        return candidate.anchor_hop_label
    hop = _hop_between(previous_candidate.pin, candidate.pin)
    return hop[0]


def _hop_between(left: MapVenuePin, right: MapVenuePin) -> tuple[str, int]:
    bands = estimate_travel_bands(left.latitude, left.longitude, right.latitude, right.longitude)
    transit = next((band for band in bands if band["mode"] == "transit"), bands[0])
    return str(transit["label"]), int(transit["minutes"])


def _role_reason(selection: PlannerSelection, main_event: PlannerCandidate) -> str:
    if selection.role == "pregame":
        gap_minutes = max(0, _minutes_between(selection.candidate.start_local, main_event.start_local))
        hop_label, _ = _hop_between(selection.candidate.pin, main_event.pin)
        return (
            f"Starts about {_minutes_label(gap_minutes)} before {main_event.card.venueName} "
            f"and keeps the handoff to roughly {hop_label}."
        )
    if selection.role == "main_event":
        return "This is the strongest anchor from the live shortlist once timing, travel, price, and trust are combined."
    if selection.role == "late_option":
        hop_label, _ = _hop_between(main_event.pin, selection.candidate.pin)
        return f"Starts after {main_event.card.venueName} and keeps the next hop to roughly {hop_label}."
    return f"Keep this as the pivot if {main_event.card.venueName} slips or the fit softens."


def _planner_summary(stops: list[TonightPlannerStop]) -> str:
    if not stops:
        return "Pulse has not found a workable night sequence yet."

    pregame = next((stop for stop in stops if stop.role == "pregame"), None)
    main_event = next((stop for stop in stops if stop.role == "main_event"), stops[0])
    trailing = next((stop for stop in stops if stop.role in {"late_option", "backup"}), None)

    if pregame and trailing and trailing.role == "late_option":
        return (
            f"Start in {pregame.neighborhood}, anchor the night at {main_event.venueName}, "
            f"then keep {trailing.venueName} for the later stretch."
        )
    if pregame and trailing and trailing.role == "backup":
        return (
            f"Open with {pregame.venueName}, lock in {main_event.venueName}, "
            f"and hold {trailing.venueName} if the main route shifts."
        )
    if pregame:
        return f"Open at {pregame.venueName}, then build the night around {main_event.venueName}."
    if trailing and trailing.role == "late_option":
        return f"Build around {main_event.venueName} first, then keep {trailing.venueName} lined up if the night runs later."
    if trailing and trailing.role == "backup":
        return f"Center the night on {main_event.venueName} and keep {trailing.venueName} ready as the pivot."
    return f"{main_event.venueName} is the clearest anchor from the current shortlist tonight."


def _apply_execution_state(
    planner: TonightPlannerResponse,
    *,
    selected_recommendation_id: str | None,
    selected_action: str | None,
) -> None:
    if not selected_recommendation_id:
        return

    selected_stop: TonightPlannerStop | None = None
    selected_fallback: TonightPlannerFallbackOption | None = None

    for stop in planner.stops:
        if stop.eventId == selected_recommendation_id:
            stop.selected = True
            selected_stop = stop
        for fallback in stop.fallbacks:
            if fallback.eventId == selected_recommendation_id:
                fallback.selected = True
                selected_fallback = fallback

    if selected_fallback is not None:
        planner.activeTargetEventId = selected_fallback.eventId
        planner.activeTargetVenueName = selected_fallback.venueName
    elif selected_stop is not None:
        planner.activeTargetEventId = selected_stop.eventId
        planner.activeTargetVenueName = selected_stop.venueName

    if selected_fallback is not None or selected_action == "planner_swap":
        planner.executionStatus = "swapped"
        if selected_fallback is not None:
            planner.executionNote = f"{selected_fallback.venueName} is currently your active planner swap."
        elif selected_stop is not None:
            planner.executionNote = f"Pulse rerouted tonight toward {selected_stop.venueName}."
        return

    if selected_stop is not None:
        planner.executionStatus = "locked"
        planner.executionNote = f"{selected_stop.venueName} is currently locked into tonight's plan."


def _apply_outcome_state(
    planner: TonightPlannerResponse,
    *,
    outcome_recommendation_id: str | None,
    outcome_action: str | None,
) -> None:
    if not planner.activeTargetEventId or not planner.activeTargetVenueName:
        return

    planner.outcomeStatus = "pending"
    if outcome_recommendation_id != planner.activeTargetEventId or not outcome_action:
        return

    if outcome_action == "planner_attended":
        planner.outcomeStatus = "attended"
        planner.outcomeNote = f"{planner.activeTargetVenueName} is confirmed as part of tonight's plan."
    elif outcome_action == "planner_skipped":
        planner.outcomeStatus = "skipped"
        planner.outcomeNote = f"{planner.activeTargetVenueName} was marked as passed tonight."


def _apply_reroute_state(planner: TonightPlannerResponse) -> None:
    if planner.outcomeStatus != "skipped" or not planner.activeTargetEventId:
        return

    reroute_option = _find_reroute_option(planner, skipped_event_id=planner.activeTargetEventId)
    if reroute_option is None:
        planner.rerouteStatus = "unavailable"
        planner.rerouteNote = "Pulse could not find a clean replacement from the current shortlist right now."
        return

    planner.rerouteStatus = "available"
    planner.rerouteOption = reroute_option
    if reroute_option.sourceKind == "fallback":
        planner.rerouteNote = f"Pulse would pivot to {reroute_option.venueName} next to keep the night moving."
    else:
        planner.rerouteNote = f"Pulse would jump ahead to {reroute_option.venueName} and keep the rest of tonight on track."


def _find_reroute_option(
    planner: TonightPlannerResponse,
    *,
    skipped_event_id: str,
) -> TonightPlannerRerouteOption | None:
    for index, stop in enumerate(planner.stops):
        if stop.eventId == skipped_event_id:
            reroute = _reroute_from_stop_skip(planner.stops, stop_index=index)
            if reroute is not None:
                return reroute
            break

        if any(fallback.eventId == skipped_event_id for fallback in stop.fallbacks):
            reroute = _reroute_from_fallback_skip(planner.stops, stop_index=index, skipped_event_id=skipped_event_id)
            if reroute is not None:
                return reroute
            break

    return None


def _reroute_from_stop_skip(
    stops: list[TonightPlannerStop],
    *,
    stop_index: int,
) -> TonightPlannerRerouteOption | None:
    skipped_stop = stops[stop_index]
    for fallback in skipped_stop.fallbacks:
        if not fallback.selected:
            return _reroute_from_fallback_option(
                fallback,
                reason=f"Fallback keeps the plan moving after {skipped_stop.venueName} was passed.",
            )

    next_stop = _next_reroute_stop(stops, start_index=stop_index + 1, skipped_event_id=skipped_stop.eventId)
    if next_stop is not None:
        return _reroute_from_stop(
            next_stop,
            reason=f"Jump ahead after {skipped_stop.venueName} dropped out of tonight's route.",
        )
    return None


def _reroute_from_fallback_skip(
    stops: list[TonightPlannerStop],
    *,
    stop_index: int,
    skipped_event_id: str,
) -> TonightPlannerRerouteOption | None:
    parent_stop = stops[stop_index]
    for fallback in parent_stop.fallbacks:
        if fallback.eventId != skipped_event_id and not fallback.selected:
            return _reroute_from_fallback_option(
                fallback,
                reason=f"Pulse found another swap path after {parent_stop.venueName} missed this pivot.",
            )

    next_stop = _next_reroute_stop(stops, start_index=stop_index + 1, skipped_event_id=skipped_event_id)
    if next_stop is not None:
        return _reroute_from_stop(
            next_stop,
            reason=f"Jump ahead after the current swap fell through near {parent_stop.venueName}.",
        )
    return None


def _next_reroute_stop(
    stops: list[TonightPlannerStop],
    *,
    start_index: int,
    skipped_event_id: str,
) -> TonightPlannerStop | None:
    for stop in stops[start_index:]:
        if stop.eventId != skipped_event_id:
            return stop
    return None


def _reroute_from_stop(
    stop: TonightPlannerStop,
    *,
    reason: str,
) -> TonightPlannerRerouteOption:
    return TonightPlannerRerouteOption(
        venueId=stop.venueId,
        venueName=stop.venueName,
        eventId=stop.eventId,
        eventTitle=stop.eventTitle,
        neighborhood=stop.neighborhood,
        startsAt=stop.startsAt,
        priceLabel=stop.priceLabel,
        scoreBand=stop.scoreBand,
        hopLabel=stop.hopLabel,
        roleLabel=stop.roleLabel,
        sourceKind="next_stop",
        rerouteReason=reason,
    )


def _reroute_from_fallback_option(
    fallback: TonightPlannerFallbackOption,
    *,
    reason: str,
) -> TonightPlannerRerouteOption:
    return TonightPlannerRerouteOption(
        venueId=fallback.venueId,
        venueName=fallback.venueName,
        eventId=fallback.eventId,
        eventTitle=fallback.eventTitle,
        neighborhood=fallback.neighborhood,
        startsAt=fallback.startsAt,
        priceLabel=fallback.priceLabel,
        scoreBand=fallback.scoreBand,
        hopLabel=fallback.hopLabel,
        sourceKind="fallback",
        rerouteReason=reason,
    )


def _minutes_between(left: datetime, right: datetime) -> int:
    return round((right - left).total_seconds() / 60)


def _minutes_label(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    remainder = minutes % 60
    if remainder == 0:
        return f"{hours}h"
    return f"{hours}h {remainder}m"


def _join_fragments(fragments: list[str]) -> str:
    cleaned = [fragment for fragment in fragments if fragment]
    if not cleaned:
        return "Pulse sees enough support to keep this in the main plan."
    if len(cleaned) == 1:
        return cleaned[0][:1].upper() + cleaned[0][1:] + "."
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}."


def _budget_fit_for_label(budget_level: str, price_label: str) -> float:
    price_value = _price_value(price_label)
    if price_value is None:
        return 0.78
    if budget_level == "flexible":
        return 0.9
    if budget_level == "free":
        return 1.0 if price_value <= 0 else 0.25

    threshold = 30 if budget_level == "under_30" else 75
    if price_value <= threshold:
        return 0.92
    if price_value <= threshold + 15:
        return 0.72
    return 0.45


def _price_value(price_label: str) -> float | None:
    normalized = price_label.strip().lower()
    if not normalized:
        return None
    if "free" in normalized:
        return 0.0

    numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", normalized)]
    if not numbers:
        return None
    if len(numbers) >= 2:
        return round((numbers[0] + numbers[1]) / 2, 2)
    return numbers[0]

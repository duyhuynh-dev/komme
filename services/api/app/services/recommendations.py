import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import CanonicalEvent, EventOccurrence, EventSource, Venue
from app.models.profile import ProfileRun, UserInterestProfile
from app.models.recommendation import (
    DIGEST_SECURITY_CLICK_FEEDBACK_ACTION,
    PLANNER_ATTENDED_FEEDBACK_ACTION,
    PLANNER_COMMIT_FEEDBACK_ACTION,
    PLANNER_SKIPPED_FEEDBACK_ACTION,
    PLANNER_SWAP_FEEDBACK_ACTION,
    DigestDelivery,
    FeedbackEvent,
    RecommendationRun,
    VenueRecommendation,
)
from app.models.user import OAuthConnection, User, UserAnchorLocation, UserConstraint
from app.schemas.recommendations import (
    ArchiveResponse,
    ArchiveSnapshot,
    RecommendationDebugSummary,
    RecommendationDebugVenue,
    RecommendationDriverSummary,
    RecommendationFeedbackReasonSummary,
    RecommendationMovementCue,
    RecommendationMovementExplanation,
    RecommendationOutcomeAttribution,
    RecommendationSupplyQualityRollup,
    RecommendationTopicSourceSummary,
    RecommendationRunComparison,
    RecommendationRunComparisonItem,
    MapVenuePin,
    MapContext,
    RecommendationsMapResponse,
    RecommendationFreshness,
    RecommendationPersonalizationSource,
    RecommendationProvenance,
    RecommendationReason,
    RecommendationScoreBreakdownItem,
    TravelEstimate,
    VenueRecommendationCard,
)
from app.services.event_plan import (
    apply_event_plan_session_state,
    build_event_plan,
    get_or_create_event_plan_session,
)
from app.services.source_health import build_connected_source_health, provider_label
from app.services.travel import estimate_travel_bands

DEFAULT_VIEWPORT = {
    "latitude": 40.73061,
    "longitude": -73.935242,
    "latitudeDelta": 0.22,
    "longitudeDelta": 0.22,
}
SERVICE_AREA_NAME = "New York City"
NYC_SERVICE_AREA = {
    "min_latitude": 40.45,
    "max_latitude": 40.95,
    "min_longitude": -74.35,
    "max_longitude": -73.65,
}
RECOMMENDATION_MAX_AGE = timedelta(minutes=30)
FEEDBACK_LOOKBACK_WINDOW = timedelta(days=28)
PLANNER_EXECUTION_LOOKBACK_WINDOW = timedelta(hours=36)
OCCURRENCE_LOOKBACK_WINDOW = timedelta(hours=2)
OCCURRENCE_LOOKAHEAD_WINDOW = timedelta(days=60)
RECOMMENDATION_RUN_HISTORY_LIMIT = 3
TOPIC_KEYWORD_MAP = {
    "underground_dance": ["techno", "warehouse", "club", "dance", "rave", "dj"],
    "indie_live_music": ["indie", "band", "concert", "live music", "show", "songwriter", "alt-pop"],
    "gallery_nights": ["gallery", "art", "opening", "installation", "visual"],
    "creative_meetups": ["meetup", "creative", "community", "networking"],
    "collector_marketplaces": ["market", "popup", "fair", "vintage", "swap", "collector"],
    "student_intellectual_scene": ["reading", "book", "lecture", "talk", "screening", "community"],
    "ambitious_professional_scene": ["networking", "panel", "speaker", "founder", "industry", "cocktail"],
    "style_design_shopping": ["design", "fashion", "vintage", "market", "popup", "boutique"],
}
TOPIC_CATEGORY_HINTS = {
    "underground_dance": ["club", "dance", "dj", "electronic", "live music", "nightlife"],
    "indie_live_music": ["concert", "live music", "performance", "show"],
    "gallery_nights": ["art", "culture", "exhibition", "gallery", "screening"],
    "creative_meetups": ["community", "conversation", "meetup", "networking", "talk", "workshop"],
    "collector_marketplaces": ["bazaar", "fair", "market", "popup", "shopping", "swap", "vintage"],
    "student_intellectual_scene": ["book", "campus", "discussion", "lecture", "reading", "screening", "seminar", "talk"],
    "ambitious_professional_scene": ["career", "founder", "industry", "networking", "panel", "professional", "speaker", "talk"],
    "style_design_shopping": ["boutique", "design", "fashion", "market", "popup", "shopping", "thrift", "vintage"],
}
BROAD_CULTURAL_THEME_KEYS = {
    "collector_marketplaces",
    "student_intellectual_scene",
    "ambitious_professional_scene",
    "style_design_shopping",
    "creative_meetups",
}
REASON_META_KEY = "_pulseMeta"
REASON_META_SCORE_SUMMARY = "score_summary"
REASON_META_SCORE_BREAKDOWN = "score_breakdown"
REASON_META_PERSONALIZATION_PROVENANCE = "personalization_provenance"
SAVE_FEEDBACK_REASON_KEYS = {
    "easy_to_get_to",
    "good_price",
    "right_vibe",
    "love_lineup",
    "good_area",
    "great_venue",
}
DISMISS_FEEDBACK_REASON_KEYS = {
    "too_far",
    "too_expensive",
    "wrong_vibe",
    "bad_timing",
    "already_seen",
    "not_trustworthy",
}


@dataclass
class FeedbackSignals:
    saved_venues: dict[str, float] = field(default_factory=dict)
    dismissed_venues: dict[str, float] = field(default_factory=dict)
    confirmed_saved_venues: dict[str, float] = field(default_factory=dict)
    planner_attended_venues: dict[str, float] = field(default_factory=dict)
    opened_venues: dict[str, float] = field(default_factory=dict)
    exposed_venues: dict[str, float] = field(default_factory=dict)
    digest_click_venues: dict[str, float] = field(default_factory=dict)
    ticket_click_venues: dict[str, float] = field(default_factory=dict)
    archive_revisit_venues: dict[str, float] = field(default_factory=dict)
    saved_topics: dict[str, float] = field(default_factory=dict)
    dismissed_topics: dict[str, float] = field(default_factory=dict)
    confirmed_saved_topics: dict[str, float] = field(default_factory=dict)
    planner_attended_topics: dict[str, float] = field(default_factory=dict)
    opened_topics: dict[str, float] = field(default_factory=dict)
    exposed_topics: dict[str, float] = field(default_factory=dict)
    digest_click_topics: dict[str, float] = field(default_factory=dict)
    ticket_click_topics: dict[str, float] = field(default_factory=dict)
    archive_revisit_topics: dict[str, float] = field(default_factory=dict)
    saved_neighborhoods: dict[str, float] = field(default_factory=dict)
    dismissed_neighborhoods: dict[str, float] = field(default_factory=dict)
    saved_reasons: dict[str, float] = field(default_factory=dict)
    dismissed_reasons: dict[str, float] = field(default_factory=dict)
    confirmed_saved_reasons: dict[str, float] = field(default_factory=dict)
    saved_reason_counts: dict[str, int] = field(default_factory=dict)
    dismissed_reason_counts: dict[str, int] = field(default_factory=dict)
    confirmed_saved_reason_counts: dict[str, int] = field(default_factory=dict)
    reason_labels: dict[str, str] = field(default_factory=dict)


@dataclass
class AnchorResolution:
    requested_anchor: UserAnchorLocation | None
    active_anchor: UserAnchorLocation | None
    requested_within_service_area: bool = True
    used_fallback_anchor: bool = False
    fallback_reason: str | None = None


@dataclass
class CandidateScoreComponents:
    interest_fit: float
    category_fit: float
    distance_fit: float
    budget_fit: float
    source_confidence: float
    transit_minutes: int
    weighted_interest: float
    weighted_category: float
    weighted_distance: float
    weighted_budget: float
    weighted_source: float
    source_weight_adjustment: float = 0.0
    source_weight_labels: list[str] = field(default_factory=list)
    stale_provider_adjustment: float = 0.0
    stale_provider_labels: list[str] = field(default_factory=list)
    supply_trust_adjustment: float = 0.0
    supply_trust_labels: list[str] = field(default_factory=list)


@dataclass
class SupplyTrustAssessment:
    raw_confidence: float
    effective_confidence: float
    confidence_adjustment: float
    labels: list[str] = field(default_factory=list)
    debug_reasons: list[str] = field(default_factory=list)


async def _latest_run(session: AsyncSession, user_id: str) -> RecommendationRun | None:
    return await session.scalar(
        select(RecommendationRun)
        .where(RecommendationRun.user_id == user_id)
        .order_by(desc(RecommendationRun.created_at))
        .limit(1)
    )


async def _latest_runs(session: AsyncSession, user_id: str, *, limit: int) -> list[RecommendationRun]:
    return list(
        (
            await session.scalars(
                select(RecommendationRun)
                .where(RecommendationRun.user_id == user_id)
                .order_by(desc(RecommendationRun.created_at), desc(RecommendationRun.id))
                .limit(limit)
            )
        ).all()
    )


async def _user_anchor(session: AsyncSession, user_id: str) -> UserAnchorLocation | None:
    anchors = list(
        (
            await session.scalars(
                select(UserAnchorLocation)
                .where(UserAnchorLocation.user_id == user_id)
                .order_by(desc(UserAnchorLocation.created_at))
            )
        ).all()
    )
    return _resolve_anchor(anchors).active_anchor


async def _user_anchor_resolution(session: AsyncSession, user_id: str) -> AnchorResolution:
    anchors = list(
        (
            await session.scalars(
                select(UserAnchorLocation)
                .where(UserAnchorLocation.user_id == user_id)
                .order_by(desc(UserAnchorLocation.created_at))
            )
        ).all()
    )
    return _resolve_anchor(anchors)


async def _user_constraints(session: AsyncSession, user_id: str) -> UserConstraint | None:
    return await session.scalar(select(UserConstraint).where(UserConstraint.user_id == user_id).limit(1))


async def _latest_planner_execution(session: AsyncSession, user_id: str) -> FeedbackEvent | None:
    since = datetime.now(tz=UTC) - PLANNER_EXECUTION_LOOKBACK_WINDOW
    return await session.scalar(
        select(FeedbackEvent)
        .where(
            FeedbackEvent.user_id == user_id,
            FeedbackEvent.created_at >= since,
            FeedbackEvent.action.in_([PLANNER_COMMIT_FEEDBACK_ACTION, PLANNER_SWAP_FEEDBACK_ACTION]),
        )
        .order_by(desc(FeedbackEvent.created_at), desc(FeedbackEvent.id))
        .limit(1)
    )


async def _latest_planner_outcome(session: AsyncSession, user_id: str) -> FeedbackEvent | None:
    since = datetime.now(tz=UTC) - PLANNER_EXECUTION_LOOKBACK_WINDOW
    return await session.scalar(
        select(FeedbackEvent)
        .where(
            FeedbackEvent.user_id == user_id,
            FeedbackEvent.created_at >= since,
            FeedbackEvent.action.in_([PLANNER_ATTENDED_FEEDBACK_ACTION, PLANNER_SKIPPED_FEEDBACK_ACTION]),
        )
        .order_by(desc(FeedbackEvent.created_at), desc(FeedbackEvent.id))
        .limit(1)
    )


async def _feedback_signals(session: AsyncSession, user_id: str) -> FeedbackSignals:
    since = datetime.now(tz=UTC) - FEEDBACK_LOOKBACK_WINDOW
    feedback_rows = list(
        (
            await session.scalars(
                select(FeedbackEvent)
                .where(FeedbackEvent.user_id == user_id, FeedbackEvent.created_at >= since)
                .order_by(desc(FeedbackEvent.created_at))
            )
        ).all()
    )
    if not feedback_rows:
        return FeedbackSignals()

    learning_rows = [row for row in feedback_rows if row.action != DIGEST_SECURITY_CLICK_FEEDBACK_ACTION]
    if not learning_rows:
        return FeedbackSignals()

    occurrence_ids = {row.recommendation_id for row in learning_rows}
    occurrences = list(
        (
            await session.scalars(
                select(EventOccurrence).where(EventOccurrence.id.in_(occurrence_ids))
            )
        ).all()
    )
    occurrences_by_id = {occurrence.id: occurrence for occurrence in occurrences}

    venue_ids = {occurrence.venue_id for occurrence in occurrences}
    event_ids = {occurrence.event_id for occurrence in occurrences}
    venues = (
        list((await session.scalars(select(Venue).where(Venue.id.in_(venue_ids)))).all())
        if venue_ids
        else []
    )
    events = (
        list((await session.scalars(select(CanonicalEvent).where(CanonicalEvent.id.in_(event_ids)))).all())
        if event_ids
        else []
    )
    venues_by_id = {venue.id: venue for venue in venues}
    events_by_id = {event.id: event for event in events}
    saved_rows = [row for row in learning_rows if row.action == "save"]
    saved_venue_ids = {
        occurrence.venue_id
        for row in saved_rows
        if (occurrence := occurrences_by_id.get(row.recommendation_id)) is not None
    }
    recent_runs = list(
        (
            await session.scalars(
                select(RecommendationRun)
                .where(RecommendationRun.user_id == user_id, RecommendationRun.created_at >= since)
                .order_by(RecommendationRun.created_at.asc(), RecommendationRun.id.asc())
            )
        ).all()
    )
    recent_run_by_id = {run.id: run for run in recent_runs}
    recent_run_ids = list(recent_run_by_id)
    sent_digest_run_ids = set()
    if recent_run_ids:
        sent_digest_run_ids = {
            delivery.recommendation_run_id
            for delivery in (
                await session.scalars(
                    select(DigestDelivery).where(
                        DigestDelivery.user_id == user_id,
                        DigestDelivery.recommendation_run_id.in_(recent_run_ids),
                        DigestDelivery.status == "sent",
                    )
                )
            ).all()
        }
    future_venue_runs: dict[str, list[dict]] = {}
    if recent_run_ids and saved_venue_ids:
        venue_recommendations = list(
            (
                await session.scalars(
                    select(VenueRecommendation).where(
                        VenueRecommendation.run_id.in_(recent_run_ids),
                        VenueRecommendation.venue_id.in_(saved_venue_ids),
                    )
                )
            ).all()
        )
        for recommendation in venue_recommendations:
            run = recent_run_by_id.get(recommendation.run_id)
            if run is None:
                continue
            future_venue_runs.setdefault(recommendation.venue_id, []).append(
                {
                    "run_id": recommendation.run_id,
                    "created_at": _timestamp_utc(run.created_at),
                    "rank": recommendation.rank,
                    "emailed": recommendation.run_id in sent_digest_run_ids,
                }
            )
        for entries in future_venue_runs.values():
            entries.sort(key=lambda item: (item["created_at"], item["run_id"]))

    signals = FeedbackSignals()

    for row in learning_rows:
        occurrence = occurrences_by_id.get(row.recommendation_id)
        if occurrence is None:
            continue

        weight = _feedback_recency_weight(row.created_at)
        venue = venues_by_id.get(occurrence.venue_id)
        event = events_by_id.get(occurrence.event_id)
        metadata = occurrence.metadata_json or {}
        topic_keys = metadata.get("topicKeys") or (
            _derive_topic_keys(event, metadata.get("tags", [])) if event is not None else []
        )

        if row.action in {"save", "dismiss"}:
            venue_store = signals.saved_venues if row.action == "save" else signals.dismissed_venues
            topic_store = signals.saved_topics if row.action == "save" else signals.dismissed_topics
            neighborhood_store = (
                signals.saved_neighborhoods if row.action == "save" else signals.dismissed_neighborhoods
            )

            if venue is not None:
                _add_feedback_weight(venue_store, venue.id, weight)
                _add_feedback_weight(neighborhood_store, venue.neighborhood, weight)

            for topic_key in topic_keys:
                _add_feedback_weight(topic_store, topic_key, weight)

            reason_store = signals.saved_reasons if row.action == "save" else signals.dismissed_reasons
            reason_count_store = (
                signals.saved_reason_counts if row.action == "save" else signals.dismissed_reason_counts
            )
            for reason_key, reason_label in _feedback_reason_entries(row.reasons_json):
                _add_feedback_weight(reason_store, reason_key, weight)
                _increment_feedback_count(reason_count_store, reason_key)
                signals.reason_labels[reason_key] = reason_label

        if row.action in {
            "opened",
            "exposed",
            "digest_click",
            "ticket_click",
            "archive_revisit",
            PLANNER_ATTENDED_FEEDBACK_ACTION,
        }:
            interaction_weight = _interaction_signal_weight(row.action, created_at=row.created_at)
            if row.action == "opened":
                venue_store = signals.opened_venues
                topic_store = signals.opened_topics
            elif row.action == "exposed":
                venue_store = signals.exposed_venues
                topic_store = signals.exposed_topics
            elif row.action == "digest_click":
                venue_store = signals.digest_click_venues
                topic_store = signals.digest_click_topics
            elif row.action == "ticket_click":
                venue_store = signals.ticket_click_venues
                topic_store = signals.ticket_click_topics
            elif row.action == PLANNER_ATTENDED_FEEDBACK_ACTION:
                venue_store = signals.planner_attended_venues
                topic_store = signals.planner_attended_topics
            else:
                venue_store = signals.archive_revisit_venues
                topic_store = signals.archive_revisit_topics

            if venue is not None:
                _add_feedback_weight(venue_store, venue.id, interaction_weight)

            for topic_key in topic_keys:
                _add_feedback_weight(topic_store, topic_key, interaction_weight)

        if row.action != "save":
            continue

        confirmed_weight = _confirmed_save_outcome_weight(
            created_at=row.created_at,
            future_runs=future_venue_runs.get(occurrence.venue_id, []),
        )
        if confirmed_weight <= 0:
            continue

        confirmed_weight *= weight
        if venue is not None:
            _add_feedback_weight(signals.confirmed_saved_venues, venue.id, confirmed_weight)

        for topic_key in topic_keys:
            _add_feedback_weight(signals.confirmed_saved_topics, topic_key, confirmed_weight)

        for reason_key, reason_label in _feedback_reason_entries(row.reasons_json):
            _add_feedback_weight(signals.confirmed_saved_reasons, reason_key, confirmed_weight)
            _increment_feedback_count(signals.confirmed_saved_reason_counts, reason_key)
            signals.reason_labels[reason_key] = reason_label

    return signals


def _timestamp_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _within_nyc_service_area(latitude: float, longitude: float) -> bool:
    return (
        NYC_SERVICE_AREA["min_latitude"] <= latitude <= NYC_SERVICE_AREA["max_latitude"]
        and NYC_SERVICE_AREA["min_longitude"] <= longitude <= NYC_SERVICE_AREA["max_longitude"]
    )


def _select_active_anchor(anchors: list[UserAnchorLocation]) -> UserAnchorLocation | None:
    return _resolve_anchor(anchors).active_anchor


def _resolve_anchor(anchors: list[UserAnchorLocation]) -> AnchorResolution:
    if not anchors:
        return AnchorResolution(requested_anchor=None, active_anchor=None)

    requested_anchor = anchors[0]
    requested_within_service_area = True
    if requested_anchor.latitude is not None and requested_anchor.longitude is not None:
        requested_within_service_area = _within_nyc_service_area(
            requested_anchor.latitude,
            requested_anchor.longitude,
        )

    for anchor in anchors:
        if anchor.latitude is not None and anchor.longitude is not None:
            if _within_nyc_service_area(anchor.latitude, anchor.longitude):
                return AnchorResolution(
                    requested_anchor=requested_anchor,
                    active_anchor=anchor,
                    requested_within_service_area=requested_within_service_area,
                    used_fallback_anchor=anchor is not requested_anchor,
                    fallback_reason=_fallback_reason(requested_anchor, anchor)
                    if anchor is not requested_anchor
                    else None,
                )
            continue

        if anchor.zip_code or anchor.neighborhood:
            return AnchorResolution(
                requested_anchor=requested_anchor,
                active_anchor=anchor,
                requested_within_service_area=requested_within_service_area,
                used_fallback_anchor=anchor is not requested_anchor,
                fallback_reason=_fallback_reason(requested_anchor, anchor)
                if anchor is not requested_anchor
                else None,
            )

    fallback_reason = None
    if (
        requested_anchor.latitude is not None
        and requested_anchor.longitude is not None
        and not requested_within_service_area
    ):
        fallback_reason = (
            f"Pulse is currently scoped to {SERVICE_AREA_NAME}, so live locations outside the city are not used yet."
        )

    return AnchorResolution(
        requested_anchor=requested_anchor,
        active_anchor=requested_anchor,
        requested_within_service_area=requested_within_service_area,
        used_fallback_anchor=False,
        fallback_reason=fallback_reason,
    )


def _fallback_reason(
    requested_anchor: UserAnchorLocation | None,
    active_anchor: UserAnchorLocation | None,
) -> str | None:
    if requested_anchor is None or active_anchor is None:
        return None

    if (
        requested_anchor.source == "live"
        and requested_anchor.latitude is not None
        and requested_anchor.longitude is not None
        and not _within_nyc_service_area(requested_anchor.latitude, requested_anchor.longitude)
    ):
        return (
            f"Pulse is currently scoped to {SERVICE_AREA_NAME}, so the map stayed anchored to "
            f"{_anchor_label(active_anchor)}."
        )

    return None


def _anchor_label(anchor: UserAnchorLocation | None) -> str:
    if anchor is None:
        return "NYC"
    if anchor.neighborhood:
        return anchor.neighborhood
    if anchor.zip_code:
        return anchor.zip_code
    if anchor.source == "live":
        return "Current location"
    return "NYC"


def _build_map_context(resolution: AnchorResolution) -> MapContext:
    active_anchor = resolution.active_anchor
    requested_anchor = resolution.requested_anchor
    return MapContext(
        serviceArea=SERVICE_AREA_NAME,
        activeAnchorLabel=_anchor_label(active_anchor),
        activeAnchorSource=active_anchor.source if active_anchor else "default",
        requestedAnchorLabel=_anchor_label(requested_anchor) if requested_anchor else None,
        requestedAnchorSource=requested_anchor.source if requested_anchor else None,
        requestedAnchorWithinServiceArea=resolution.requested_within_service_area,
        usedFallbackAnchor=resolution.used_fallback_anchor,
        fallbackReason=resolution.fallback_reason,
    )


def _anchor_coordinates(anchor: UserAnchorLocation | None) -> tuple[float, float]:
    if anchor and anchor.latitude is not None and anchor.longitude is not None:
        return anchor.latitude, anchor.longitude

    zip_to_coordinate = {
        "10003": (40.7315, -73.9897),
        "11211": (40.7176, -73.9533),
        "10014": (40.7347, -74.0060),
    }
    if anchor and anchor.zip_code and anchor.zip_code in zip_to_coordinate:
        return zip_to_coordinate[anchor.zip_code]

    return (DEFAULT_VIEWPORT["latitude"], DEFAULT_VIEWPORT["longitude"])


def _viewport_for_anchor(anchor: UserAnchorLocation | None) -> dict[str, float]:
    latitude, longitude = _anchor_coordinates(anchor)
    return {
        "latitude": latitude,
        "longitude": longitude,
        "latitudeDelta": DEFAULT_VIEWPORT["latitudeDelta"],
        "longitudeDelta": DEFAULT_VIEWPORT["longitudeDelta"],
    }


def _clamp_score(value: float) -> float:
    return max(0.05, min(0.99, round(value, 3)))


def _feedback_recency_weight(created_at: datetime) -> float:
    age = datetime.now(tz=UTC) - _timestamp_utc(created_at)
    if age <= timedelta(days=7):
        return 1.0
    if age <= timedelta(days=14):
        return 0.7
    return 0.45


def _confirmed_save_outcome_weight(*, created_at: datetime, future_runs: list[dict]) -> float:
    later_runs = [item for item in future_runs if item["created_at"] > _timestamp_utc(created_at)]
    if not later_runs:
        return 0.0

    capped_runs = later_runs[:4]
    top_rank_hits = sum(1 for item in capped_runs if item["rank"] <= 3)
    digest_hit = any(item["emailed"] for item in capped_runs)

    weight = 0.32
    weight += min(0.30, len(capped_runs) * 0.10)
    weight += min(0.18, top_rank_hits * 0.06)
    if digest_hit:
        weight += 0.24

    return min(1.04, weight)


def _interaction_signal_weight(action: str, *, created_at: datetime) -> float:
    base_weight = 0.0
    if action == "opened":
        base_weight = 0.65
    elif action == "exposed":
        base_weight = 0.32
    elif action == "digest_click":
        base_weight = 1.35
    elif action == "archive_revisit":
        base_weight = 0.82
    elif action == "ticket_click":
        base_weight = 1.1
    elif action == PLANNER_ATTENDED_FEEDBACK_ACTION:
        base_weight = 1.6
    return round(base_weight * _feedback_recency_weight(created_at), 3)


def _add_feedback_weight(store: dict[str, float], key: str | None, weight: float) -> None:
    normalized_key = _normalize_text(key)
    if not normalized_key:
        return
    store[normalized_key] = store.get(normalized_key, 0.0) + weight


def _increment_feedback_count(store: dict[str, int], key: str | None) -> None:
    normalized_key = _normalize_text(key)
    if not normalized_key:
        return
    store[normalized_key] = store.get(normalized_key, 0) + 1


def _feedback_reason_label(key: str, label: str | None = None) -> str:
    if label and label.strip():
        return label.strip()
    return key.replace("_", " ").strip().title()


def _feedback_reason_entries(payload: list[dict] | None) -> list[tuple[str, str]]:
    if not payload:
        return []

    allowed_keys = SAVE_FEEDBACK_REASON_KEYS | DISMISS_FEEDBACK_REASON_KEYS
    entries: list[tuple[str, str]] = []
    seen_keys: set[str] = set()
    for item in payload:
        key = _normalize_text(item.get("key")) if isinstance(item, dict) else ""
        if not key or key not in allowed_keys or key in seen_keys:
            continue
        seen_keys.add(key)
        entries.append((key, _feedback_reason_label(key, item.get("label"))))
    return entries


def _feedback_recency_label(created_at: datetime, *, now: datetime | None = None) -> str:
    delta = _timestamp_utc(now or datetime.now(tz=UTC)) - _timestamp_utc(created_at)
    if delta < timedelta(hours=1):
        minutes = max(1, int(delta.total_seconds() // 60))
        return f"{minutes}m ago"
    if delta < timedelta(days=1):
        hours = max(1, int(delta.total_seconds() // 3600))
        return f"{hours}h ago"
    days = max(1, delta.days)
    return f"{days}d ago"


def _attribution_source(action: str) -> str:
    if action in {PLANNER_ATTENDED_FEEDBACK_ACTION, PLANNER_SKIPPED_FEEDBACK_ACTION}:
        return "planner"
    if action == "digest_click":
        return "digest"
    return "feedback"


def _attribution_direction(action: str) -> str:
    if action in {
        "save",
        "digest_click",
        "ticket_click",
        "archive_revisit",
        PLANNER_ATTENDED_FEEDBACK_ACTION,
    }:
        return "positive"
    if action == "dismiss":
        return "negative"
    return "neutral"


def _attribution_explanation(
    *,
    action: str,
    venue_name: str | None,
    reason_labels: list[str],
    topic_keys: list[str],
    digest_driven: bool = False,
) -> str:
    target = venue_name or "this recommendation"
    if action == "save":
        suffix = f" with {_join_labels(reason_labels)}" if reason_labels else ""
        return f"Recent save on {target}{suffix} is feeding positive feedback weights."
    if action == "dismiss":
        suffix = f" with {_join_labels(reason_labels)}" if reason_labels else ""
        return f"Recent dismiss on {target}{suffix} is feeding cautionary feedback weights."
    if action == PLANNER_ATTENDED_FEEDBACK_ACTION:
        if digest_driven:
            return (
                f"You first clicked {target} from a digest, then marked it attended in the planner, "
                "so Pulse treats this as high-trust real-world intent."
            )
        return f"Planner attendance at {target} is treated as strong real-world positive intent."
    if action == PLANNER_SKIPPED_FEEDBACK_ACTION:
        return f"Planner skip for {target} is visible here, but does not add negative ranking weight."
    if action == "ticket_click":
        if digest_driven:
            return f"Ticket click on {target} followed a digest click, so Pulse treats it as stronger intent."
        return f"Ticket click on {target} is feeding positive intent weights."
    if action == "archive_revisit":
        if digest_driven:
            return f"Archive revisit for {target} followed a digest click, keeping this outcome trace warmer."
        return f"Archive revisit for {target} keeps this venue or similar topics active."
    if action == "digest_click":
        return f"Digest click on {target} is feeding positive response weights."
    topic_suffix = f" for {_join_labels(topic_keys)}" if topic_keys else ""
    return f"Recent {action.replace('_', ' ')}{topic_suffix} is visible in feedback history."


async def _outcome_attributions(
    session: AsyncSession,
    user_id: str,
    *,
    limit: int = 8,
    now: datetime | None = None,
) -> list[RecommendationOutcomeAttribution]:
    since = datetime.now(tz=UTC) - FEEDBACK_LOOKBACK_WINDOW
    supported_actions = {
        "save",
        "dismiss",
        "digest_click",
        "ticket_click",
        "archive_revisit",
        PLANNER_ATTENDED_FEEDBACK_ACTION,
        PLANNER_SKIPPED_FEEDBACK_ACTION,
    }
    rows = list(
        (
            await session.scalars(
                select(FeedbackEvent)
                .where(
                    FeedbackEvent.user_id == user_id,
                    FeedbackEvent.created_at >= since,
                    FeedbackEvent.action.in_(supported_actions),
                )
                .order_by(desc(FeedbackEvent.created_at), desc(FeedbackEvent.id))
                .limit(limit * 2)
            )
        ).all()
    )
    if not rows:
        return []

    occurrence_ids = {row.recommendation_id for row in rows}
    occurrences = list(
        (await session.scalars(select(EventOccurrence).where(EventOccurrence.id.in_(occurrence_ids)))).all()
    )
    occurrences_by_id = {occurrence.id: occurrence for occurrence in occurrences}
    venue_ids = {occurrence.venue_id for occurrence in occurrences}
    event_ids = {occurrence.event_id for occurrence in occurrences}
    venues = list((await session.scalars(select(Venue).where(Venue.id.in_(venue_ids)))).all()) if venue_ids else []
    events = (
        list((await session.scalars(select(CanonicalEvent).where(CanonicalEvent.id.in_(event_ids)))).all())
        if event_ids
        else []
    )
    venues_by_id = {venue.id: venue for venue in venues}
    events_by_id = {event.id: event for event in events}
    digest_clicks_by_occurrence: dict[str, datetime] = {}
    for row in rows:
        if row.action != "digest_click":
            continue
        current = digest_clicks_by_occurrence.get(row.recommendation_id)
        if current is None or _timestamp_utc(row.created_at) < _timestamp_utc(current):
            digest_clicks_by_occurrence[row.recommendation_id] = row.created_at

    attributions: list[RecommendationOutcomeAttribution] = []
    for row in rows:
        occurrence = occurrences_by_id.get(row.recommendation_id)
        venue = venues_by_id.get(occurrence.venue_id) if occurrence is not None else None
        event = events_by_id.get(occurrence.event_id) if occurrence is not None else None
        metadata = (occurrence.metadata_json or {}) if occurrence is not None else {}
        topic_keys = metadata.get("topicKeys") or (
            _derive_topic_keys(event, metadata.get("tags", [])) if event is not None else []
        )
        reason_entries = _feedback_reason_entries(row.reasons_json)
        reason_keys = [key for key, _ in reason_entries]
        reason_labels = [label for _, label in reason_entries]
        digest_clicked_at = digest_clicks_by_occurrence.get(row.recommendation_id)
        digest_driven = (
            digest_clicked_at is not None
            and row.action in {"ticket_click", "archive_revisit", PLANNER_ATTENDED_FEEDBACK_ACTION}
            and _timestamp_utc(row.created_at) >= _timestamp_utc(digest_clicked_at)
        )
        attributions.append(
            RecommendationOutcomeAttribution(
                action=row.action,
                source=_attribution_source(row.action),
                venueId=venue.id if venue is not None else None,
                venueName=venue.name if venue is not None else None,
                eventId=event.id if event is not None else None,
                eventTitle=event.title if event is not None else None,
                topicKeys=topic_keys,
                reasonKeys=reason_keys,
                recencyLabel=_feedback_recency_label(row.created_at, now=now),
                direction=_attribution_direction(row.action),
                explanation=_attribution_explanation(
                    action=row.action,
                    venue_name=venue.name if venue is not None else None,
                    reason_labels=reason_labels,
                    topic_keys=topic_keys,
                    digest_driven=digest_driven,
                ),
            )
        )
        if len(attributions) >= limit:
            break

    return attributions


def _average_feedback_weight(keys: list[str], store: dict[str, float]) -> float:
    normalized_keys = [_normalize_text(key) for key in keys if _normalize_text(key)]
    if not normalized_keys:
        return 0.0
    weights = [store.get(key, 0.0) for key in normalized_keys]
    return sum(weights) / len(weights)


def _taste_source_weight(source_provider: str | None) -> float:
    if not source_provider:
        return 1.0
    provider = source_provider
    weights = {
        "manual": 1.0,
        "spotify": 0.78,
        "reddit_export": 0.9,
        "reddit": 0.9,
        "mock": 0.72,
        "unknown": 0.82,
    }
    return weights.get(provider, 0.82)


def _topic_weight(topic: UserInterestProfile, *, apply_source_weight: bool = True) -> float:
    if topic.muted:
        return 0.05
    base = 0.24 + (topic.confidence * 0.64)
    if topic.boosted:
        base += 0.12
    if apply_source_weight:
        base *= _taste_source_weight(topic.source_provider)
    return min(0.99, base)


def _topic_is_from_stale_provider(topic: UserInterestProfile, stale_provider_keys: set[str]) -> bool:
    return topic.source_provider == "spotify" and topic.source_provider in stale_provider_keys


def _interest_fit(
    topic_keys: list[str],
    profiles_by_key: dict[str, UserInterestProfile],
    *,
    stale_provider_keys: set[str] | None = None,
    apply_source_weights: bool = True,
) -> tuple[float, list[UserInterestProfile], list[UserInterestProfile], list[UserInterestProfile]]:
    stale_provider_keys = stale_provider_keys or set()
    if not topic_keys:
        return (0.34, [], [], [])

    matched_topics: list[UserInterestProfile] = []
    muted_topics: list[UserInterestProfile] = []
    stale_topics: list[UserInterestProfile] = []
    weights: list[float] = []

    for key in topic_keys:
        topic = profiles_by_key.get(key)
        if topic is None:
            continue

        if _topic_is_from_stale_provider(topic, stale_provider_keys):
            stale_topics.append(topic)
            continue

        if topic.muted:
            muted_topics.append(topic)
        else:
            matched_topics.append(topic)
        weights.append(_topic_weight(topic, apply_source_weight=apply_source_weights))

    if not weights:
        return (0.34, [], [], stale_topics)

    average_weight = sum(weights) / len(weights)
    strongest_weight = max(weights)
    diversity_bonus = min(0.10, max(0, len(matched_topics) - 1) * 0.04)
    score = (average_weight * 0.62) + (strongest_weight * 0.38) + diversity_bonus
    if muted_topics and not matched_topics:
        score *= 0.35
    elif muted_topics:
        score -= 0.12 * len(muted_topics)

    return (_clamp_score(score), matched_topics, muted_topics, stale_topics)


def _category_affinity(
    category: str,
    tags: list[str],
    profiles_by_key: dict[str, UserInterestProfile],
    *,
    stale_provider_keys: set[str] | None = None,
    apply_source_weights: bool = True,
) -> float:
    stale_provider_keys = stale_provider_keys or set()
    blob = " ".join(
        filter(
            None,
            [
                _normalize_text(category),
                " ".join(_normalize_text(tag) for tag in tags),
            ],
        )
    )
    if not blob:
        return 0.0

    matching_weights: list[float] = []
    for topic_key, topic in profiles_by_key.items():
        if topic.muted or _topic_is_from_stale_provider(topic, stale_provider_keys):
            continue
        hints = TOPIC_CATEGORY_HINTS.get(topic_key, [])
        if any(hint in blob for hint in hints):
            matching_weights.append(_topic_weight(topic, apply_source_weight=apply_source_weights))

    if not matching_weights:
        return 0.0

    strongest = max(matching_weights)
    breadth_bonus = min(0.05, max(0, len(matching_weights) - 1) * 0.025)
    return min(0.18, (strongest * 0.16) + breadth_bonus)


def _transit_minutes(travel: list[dict]) -> int:
    for band in travel:
        if band["mode"] == "transit":
            return band["minutes"]
    return 45


def _distance_fit(transit_minutes: int) -> float:
    if transit_minutes <= 25:
        return 0.95
    if transit_minutes <= 40:
        return 0.82
    if transit_minutes <= 55:
        return 0.68
    return 0.52


def _budget_fit(constraints: UserConstraint | None, occurrence: EventOccurrence) -> float:
    max_price = occurrence.max_price if occurrence.max_price is not None else occurrence.min_price
    budget_level = constraints.budget_level if constraints and constraints.budget_level else "under_75"

    if max_price is None:
        return 0.78
    if budget_level == "flexible":
        return 0.9
    if budget_level == "free":
        return 1.0 if max_price <= 0 else 0.25

    budget_threshold = 30 if budget_level == "under_30" else 75
    if max_price <= budget_threshold:
        return 0.92
    if max_price <= budget_threshold + 15:
        return 0.72
    return 0.45


def _score_band(score: float) -> str:
    if score >= 0.78:
        return "high"
    if score >= 0.58:
        return "medium"
    return "low"


def _join_labels(labels: list[str]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def _feedback_topic_labels(
    topic_keys: list[str],
    profiles_by_key: dict[str, UserInterestProfile],
) -> list[str]:
    labels: list[str] = []
    for key in topic_keys:
        topic = profiles_by_key.get(key)
        if topic is None or topic.label in labels:
            continue
        labels.append(topic.label)
    return labels


def _reason_weight(store: dict[str, float], key: str) -> float:
    return store.get(_normalize_text(key), 0.0)


def _reason_feedback_adjustment(
    *,
    topic_labels: list[str],
    transit_minutes: int,
    budget_fit: float,
    source_confidence: float,
    feedback_signals: FeedbackSignals,
) -> tuple[float, dict | None]:
    adjustment = 0.0
    strongest_reason: tuple[float, dict] | None = None

    def record_reason(abs_contribution: float, title: str, detail: str) -> None:
        nonlocal strongest_reason
        reason = {"title": title, "detail": detail}
        if strongest_reason is None or abs_contribution > strongest_reason[0]:
            strongest_reason = (abs_contribution, reason)

    saved_easy_weight = _reason_weight(feedback_signals.saved_reasons, "easy_to_get_to")
    confirmed_easy_weight = _reason_weight(feedback_signals.confirmed_saved_reasons, "easy_to_get_to")
    dismissed_far_weight = _reason_weight(feedback_signals.dismissed_reasons, "too_far")
    saved_price_weight = _reason_weight(feedback_signals.saved_reasons, "good_price")
    confirmed_price_weight = _reason_weight(feedback_signals.confirmed_saved_reasons, "good_price")
    dismissed_price_weight = _reason_weight(feedback_signals.dismissed_reasons, "too_expensive")
    saved_vibe_weight = _reason_weight(feedback_signals.saved_reasons, "right_vibe") + _reason_weight(
        feedback_signals.saved_reasons, "love_lineup"
    )
    confirmed_vibe_weight = _reason_weight(feedback_signals.confirmed_saved_reasons, "right_vibe") + _reason_weight(
        feedback_signals.confirmed_saved_reasons, "love_lineup"
    )
    dismissed_vibe_weight = _reason_weight(feedback_signals.dismissed_reasons, "wrong_vibe")
    dismissed_trust_weight = _reason_weight(feedback_signals.dismissed_reasons, "not_trustworthy")

    if transit_minutes <= 30 and (saved_easy_weight or confirmed_easy_weight):
        contribution = min(0.085, 0.015 + (saved_easy_weight * 0.02) + (confirmed_easy_weight * 0.03))
        adjustment += contribution
        record_reason(
            contribution,
            "Validated distance pattern" if confirmed_easy_weight >= 0.3 else "Distance pattern",
            (
                "Easy-to-get-to saves kept surviving later runs, so faster trips now get a stronger lift."
                if confirmed_easy_weight >= 0.3
                else "You often save easy-to-get-to spots, so faster trips now get a lift."
            ),
        )

    if transit_minutes >= 40 and dismissed_far_weight:
        contribution = min(0.10, 0.025 + (dismissed_far_weight * 0.03))
        adjustment -= contribution
        record_reason(
            contribution,
            "Distance pattern",
            "You often dismiss long trips, so this commute holds the score back.",
        )

    if budget_fit >= 0.82 and (saved_price_weight or confirmed_price_weight):
        contribution = min(0.075, 0.012 + (saved_price_weight * 0.018) + (confirmed_price_weight * 0.028))
        adjustment += contribution
        record_reason(
            contribution,
            "Validated budget pattern" if confirmed_price_weight >= 0.3 else "Budget pattern",
            (
                "Good-value saves kept holding through later runs, so budget-friendly options now get more trust."
                if confirmed_price_weight >= 0.3
                else "You tend to save good-value picks, so budget-friendly options get a boost."
            ),
        )

    if budget_fit <= 0.58 and dismissed_price_weight:
        contribution = min(0.09, 0.02 + (dismissed_price_weight * 0.03))
        adjustment -= contribution
        record_reason(
            contribution,
            "Budget pattern",
            "You often dismiss pricier picks, so this price point drags on the rank.",
        )

    if topic_labels and (saved_vibe_weight or confirmed_vibe_weight):
        contribution = min(0.085, 0.015 + (saved_vibe_weight * 0.018) + (confirmed_vibe_weight * 0.028))
        adjustment += contribution
        record_reason(
            contribution,
            "Validated taste pattern" if confirmed_vibe_weight >= 0.3 else "Taste pattern",
            (
                f"Saved {_join_labels(topic_labels)} picks kept surviving later runs, so this vibe now gets more trust."
                if confirmed_vibe_weight >= 0.3
                else f"You keep saving {_join_labels(topic_labels)} picks for the vibe, so this gets a lift."
            ),
        )

    if topic_labels and dismissed_vibe_weight:
        contribution = min(0.09, 0.02 + (dismissed_vibe_weight * 0.03))
        adjustment -= contribution
        record_reason(
            contribution,
            "Taste pattern",
            f"You often dismiss {_join_labels(topic_labels)} picks as the wrong vibe, so this is ranked more cautiously.",
        )

    if source_confidence <= 0.76 and dismissed_trust_weight:
        contribution = min(0.07, 0.015 + (dismissed_trust_weight * 0.025))
        adjustment -= contribution
        record_reason(
            contribution,
            "Trust pattern",
            "You have been skeptical of lower-trust signals, so lighter-confidence sources now get discounted.",
        )

    return adjustment, strongest_reason[1] if strongest_reason is not None else None


def _feedback_adjustment(
    topic_keys: list[str],
    profiles_by_key: dict[str, UserInterestProfile],
    venue: Venue,
    feedback_signals: FeedbackSignals,
    *,
    transit_minutes: int,
    budget_fit: float,
    source_confidence: float,
) -> tuple[float, dict | None]:
    adjustment = 0.0

    saved_venue_weight = feedback_signals.saved_venues.get(_normalize_text(venue.id), 0.0)
    dismissed_venue_weight = feedback_signals.dismissed_venues.get(_normalize_text(venue.id), 0.0)
    confirmed_saved_venue_weight = feedback_signals.confirmed_saved_venues.get(_normalize_text(venue.id), 0.0)
    planner_attended_venue_weight = feedback_signals.planner_attended_venues.get(_normalize_text(venue.id), 0.0)
    opened_venue_weight = feedback_signals.opened_venues.get(_normalize_text(venue.id), 0.0)
    exposed_venue_weight = feedback_signals.exposed_venues.get(_normalize_text(venue.id), 0.0)
    digest_click_venue_weight = feedback_signals.digest_click_venues.get(_normalize_text(venue.id), 0.0)
    ticket_click_venue_weight = feedback_signals.ticket_click_venues.get(_normalize_text(venue.id), 0.0)
    archive_revisit_venue_weight = feedback_signals.archive_revisit_venues.get(_normalize_text(venue.id), 0.0)
    saved_topic_weight = _average_feedback_weight(topic_keys, feedback_signals.saved_topics)
    dismissed_topic_weight = _average_feedback_weight(topic_keys, feedback_signals.dismissed_topics)
    confirmed_saved_topic_weight = _average_feedback_weight(topic_keys, feedback_signals.confirmed_saved_topics)
    planner_attended_topic_weight = _average_feedback_weight(topic_keys, feedback_signals.planner_attended_topics)
    opened_topic_weight = _average_feedback_weight(topic_keys, feedback_signals.opened_topics)
    exposed_topic_weight = _average_feedback_weight(topic_keys, feedback_signals.exposed_topics)
    digest_click_topic_weight = _average_feedback_weight(topic_keys, feedback_signals.digest_click_topics)
    ticket_click_topic_weight = _average_feedback_weight(topic_keys, feedback_signals.ticket_click_topics)
    archive_revisit_topic_weight = _average_feedback_weight(topic_keys, feedback_signals.archive_revisit_topics)
    neighborhood_key = _normalize_text(venue.neighborhood)
    neighborhood_delta = (
        feedback_signals.saved_neighborhoods.get(neighborhood_key, 0.0)
        - feedback_signals.dismissed_neighborhoods.get(neighborhood_key, 0.0)
    )

    if saved_venue_weight:
        adjustment += min(0.18, 0.10 + (saved_venue_weight * 0.05))
    if dismissed_venue_weight:
        adjustment -= min(0.34, 0.18 + (dismissed_venue_weight * 0.08))
    if confirmed_saved_venue_weight:
        adjustment += min(0.10, 0.03 + (confirmed_saved_venue_weight * 0.04))
    if planner_attended_venue_weight:
        adjustment += min(0.16, 0.05 + (planner_attended_venue_weight * 0.055))
    if opened_venue_weight:
        adjustment += min(0.09, 0.02 + (opened_venue_weight * 0.045))
    if digest_click_venue_weight:
        adjustment += min(0.14, 0.04 + (digest_click_venue_weight * 0.055))
    if ticket_click_venue_weight:
        adjustment += min(0.12, 0.03 + (ticket_click_venue_weight * 0.05))
    if archive_revisit_venue_weight:
        adjustment += min(0.10, 0.025 + (archive_revisit_venue_weight * 0.04))

    topic_delta = saved_topic_weight - dismissed_topic_weight
    adjustment += max(-0.12, min(0.12, topic_delta * 0.10))
    adjustment += max(0.0, min(0.08, confirmed_saved_topic_weight * 0.05))
    adjustment += max(0.0, min(0.10, planner_attended_topic_weight * 0.055))
    adjustment += max(0.0, min(0.06, opened_topic_weight * 0.035))
    adjustment += max(0.0, min(0.09, digest_click_topic_weight * 0.045))
    adjustment += max(0.0, min(0.08, ticket_click_topic_weight * 0.04))
    adjustment += max(0.0, min(0.07, archive_revisit_topic_weight * 0.035))
    adjustment += max(-0.06, min(0.06, neighborhood_delta * 0.04))

    exposure_drag = max(
        0.0,
        exposed_venue_weight
        - (opened_venue_weight * 0.9)
        - (saved_venue_weight * 0.75)
        - (confirmed_saved_venue_weight * 0.6)
        - (planner_attended_venue_weight * 0.8),
    )
    topic_exposure_drag = max(
        0.0,
        exposed_topic_weight
        - (opened_topic_weight * 0.9)
        - (saved_topic_weight * 0.6)
        - (confirmed_saved_topic_weight * 0.5)
        - (planner_attended_topic_weight * 0.65),
    )
    adjustment -= min(0.055, (exposure_drag * 0.025) + (topic_exposure_drag * 0.015))

    feedback_reason: dict | None = None
    topic_labels = _feedback_topic_labels(topic_keys, profiles_by_key)

    if planner_attended_venue_weight >= 0.35 and digest_click_venue_weight >= 0.35:
        feedback_reason = {
            "title": "Digest-to-attendance",
            "detail": (
                f"You clicked {venue.name} from a Pulse digest and later marked it attended, "
                "so Pulse treats this as high-trust real-world intent."
            ),
        }
    elif planner_attended_venue_weight >= 0.35:
        feedback_reason = {
            "title": "Went before",
            "detail": f"You marked {venue.name} as part of a real night out, so Pulse now trusts it as higher-confidence intent.",
        }
    elif ticket_click_venue_weight >= 0.45 and digest_click_venue_weight >= 0.35:
        feedback_reason = {
            "title": "Digest-to-ticket intent",
            "detail": (
                f"You clicked {venue.name} from a Pulse digest and then opened tickets, "
                "so Pulse treats it as stronger intent."
            ),
        }
    elif archive_revisit_venue_weight >= 0.4 and digest_click_venue_weight >= 0.35:
        feedback_reason = {
            "title": "Digest-to-archive revisit",
            "detail": (
                f"You clicked {venue.name} from a Pulse digest and later revisited it in the archive, "
                "so Pulse keeps this signal warmer."
            ),
        }
    elif confirmed_saved_venue_weight >= 0.35:
        feedback_reason = {
            "title": "Validated save",
            "detail": f"You saved {venue.name} and it kept surviving later runs, so Pulse now trusts that signal more.",
        }
    elif digest_click_venue_weight >= 0.4:
        feedback_reason = {
            "title": "Acted from digest",
            "detail": f"You clicked {venue.name} directly from a Pulse digest, so Pulse treats it as stronger real-world intent.",
        }
    elif ticket_click_venue_weight >= 0.45:
        feedback_reason = {
            "title": "Clicked through before",
            "detail": f"You clicked into {venue.name} before, so Pulse treats it as a stronger real-world contender.",
        }
    elif archive_revisit_venue_weight >= 0.4:
        feedback_reason = {
            "title": "Archived revisit",
            "detail": f"You came back to {venue.name} in the archive, so Pulse keeps it more active in future runs.",
        }
    elif opened_venue_weight >= 0.4:
        feedback_reason = {
            "title": "Reopened before",
            "detail": f"You keep revisiting {venue.name}, so Pulse treats it as a stronger active interest.",
        }
    elif dismissed_venue_weight >= 0.45:
        feedback_reason = {
            "title": "Dismissed before",
            "detail": f"You recently dismissed {venue.name}, so Pulse now holds it back.",
        }
    elif saved_venue_weight >= 0.45:
        feedback_reason = {
            "title": "Saved before",
            "detail": f"You have saved {venue.name} before, so similar runs get a lift.",
        }
    elif topic_delta <= -0.35 and topic_labels:
        feedback_reason = {
            "title": "Dismiss pattern",
            "detail": f"You often dismiss {_join_labels(topic_labels)} picks, so this is ranked more cautiously.",
        }
    elif planner_attended_topic_weight >= 0.35 and topic_labels:
        feedback_reason = {
            "title": "Night-out pattern",
            "detail": f"You actually made it to {_join_labels(topic_labels)} picks, so Pulse now treats that theme as stronger real-world intent.",
        }
    elif confirmed_saved_topic_weight >= 0.35 and topic_labels:
        feedback_reason = {
            "title": "Validated pattern",
            "detail": f"Saved {_join_labels(topic_labels)} picks kept showing up in later runs, so this signal now gets more trust.",
        }
    elif digest_click_topic_weight >= 0.35 and topic_labels:
        feedback_reason = {
            "title": "Digest response pattern",
            "detail": f"You act on {_join_labels(topic_labels)} picks from digest emails, so Pulse treats that theme as stronger intent.",
        }
    elif ticket_click_topic_weight >= 0.35 and topic_labels:
        feedback_reason = {
            "title": "Click-through pattern",
            "detail": f"You click into {_join_labels(topic_labels)} picks more often, so Pulse treats that theme as stronger intent.",
        }
    elif archive_revisit_topic_weight >= 0.35 and topic_labels:
        feedback_reason = {
            "title": "Archive return pattern",
            "detail": f"You revisit {_join_labels(topic_labels)} picks in the archive, so Pulse keeps that theme warmer.",
        }
    elif opened_topic_weight >= 0.35 and topic_labels:
        feedback_reason = {
            "title": "Return pattern",
            "detail": f"You keep reopening {_join_labels(topic_labels)} picks, so Pulse treats that theme as more active right now.",
        }
    elif topic_delta >= 0.35 and topic_labels:
        feedback_reason = {
            "title": "Save pattern",
            "detail": f"You tend to save {_join_labels(topic_labels)} picks, so this gets a small lift.",
        }
    elif (exposure_drag >= 0.7 or topic_exposure_drag >= 0.7) and topic_labels:
        feedback_reason = {
            "title": "Seen, not opened",
            "detail": f"Pulse has shown you a few {_join_labels(topic_labels)} picks that you did not reopen, so this gets a softer rank.",
        }
    elif neighborhood_delta <= -0.6 and venue.neighborhood:
        feedback_reason = {
            "title": "Area pattern",
            "detail": f"Pulse has seen more dismisses around {venue.neighborhood}, so this area is weighted down a bit.",
        }
    elif neighborhood_delta >= 0.6 and venue.neighborhood:
        feedback_reason = {
            "title": "Area pattern",
            "detail": f"You have saved a few spots around {venue.neighborhood}, so this area gets a gentle boost.",
        }

    reason_adjustment, reason_feedback = _reason_feedback_adjustment(
        topic_labels=topic_labels,
        transit_minutes=transit_minutes,
        budget_fit=budget_fit,
        source_confidence=source_confidence,
        feedback_signals=feedback_signals,
    )
    adjustment += reason_adjustment
    if reason_feedback is not None and (feedback_reason is None or abs(reason_adjustment) >= 0.04):
        feedback_reason = reason_feedback

    return max(-0.38, min(0.22, adjustment)), feedback_reason


def _reason_items(
    matched_topics: list[UserInterestProfile],
    muted_topics: list[UserInterestProfile],
    travel: list[dict],
    budget_fit: float,
    venue: Venue,
    feedback_reason: dict | None = None,
    source_weight_labels: list[str] | None = None,
) -> list[dict]:
    reasons: list[dict] = []
    boosted_labels = [topic.label for topic in matched_topics if topic.boosted]
    matched_labels = [topic.label for topic in matched_topics if not topic.boosted]

    if boosted_labels:
        reasons.append(
            {
                "title": "Boosted fit",
                "detail": f"You boosted {_join_labels(boosted_labels)}, so {venue.name} moved up in this run.",
            }
        )
    elif matched_labels:
        reasons.append(
            {
                "title": "Profile match",
                "detail": f"This venue lines up with your {_join_labels(matched_labels)} signals.",
            }
        )

    if source_weight_labels:
        reasons.append(
            {
                "title": "Source-weighted taste",
                "detail": (
                    f"{venue.name} matched your taste, but passive source signals were bounded by "
                    f"{_join_labels(source_weight_labels)}."
                ),
            }
        )

    if feedback_reason is not None:
        reasons.append(feedback_reason)

    if muted_topics:
        reasons.append(
            {
                "title": "Muted signal",
                "detail": f"Muted topics like {_join_labels([topic.label for topic in muted_topics])} now reduce this score.",
            }
        )

    transit_minutes = _transit_minutes(travel)
    reasons.append(
        {
            "title": "Travel fit",
            "detail": f"About {transit_minutes} min by transit from your current NYC anchor.",
        }
    )

    reasons.append(
        {
            "title": "Budget fit",
            "detail": "Comfortably inside budget." if budget_fit >= 0.85 else "A little pricier, but still workable.",
        }
    )
    return reasons[:3]


def _candidate_score(
    topic_keys: list[str],
    profiles_by_key: dict[str, UserInterestProfile],
    source_confidence: float,
    transit_minutes: int,
    budget_fit: float,
    *,
    category: str = "",
    tags: list[str] | None = None,
    stale_provider_keys: set[str] | None = None,
    raw_source_confidence: float | None = None,
    supply_trust_labels: list[str] | None = None,
) -> tuple[float, list[UserInterestProfile], list[UserInterestProfile]]:
    score, matched_topics, muted_topics, _ = _candidate_score_with_components(
        topic_keys,
        profiles_by_key,
        source_confidence,
        transit_minutes,
        budget_fit,
        category=category,
        tags=tags,
        stale_provider_keys=stale_provider_keys,
        raw_source_confidence=raw_source_confidence,
        supply_trust_labels=supply_trust_labels,
    )
    return score, matched_topics, muted_topics


def _candidate_score_with_components(
    topic_keys: list[str],
    profiles_by_key: dict[str, UserInterestProfile],
    source_confidence: float,
    transit_minutes: int,
    budget_fit: float,
    *,
    category: str = "",
    tags: list[str] | None = None,
    stale_provider_keys: set[str] | None = None,
    raw_source_confidence: float | None = None,
    supply_trust_labels: list[str] | None = None,
) -> tuple[float, list[UserInterestProfile], list[UserInterestProfile], CandidateScoreComponents]:
    stale_provider_keys = stale_provider_keys or set()
    raw_source_confidence = source_confidence if raw_source_confidence is None else raw_source_confidence
    unweighted_interest_fit, _, _, _ = _interest_fit(
        topic_keys,
        profiles_by_key,
        apply_source_weights=False,
    )
    interest_fit, matched_topics, muted_topics, stale_topics = _interest_fit(
        topic_keys,
        profiles_by_key,
        stale_provider_keys=stale_provider_keys,
    )
    unweighted_category_fit = _category_affinity(
        category,
        tags or [],
        profiles_by_key,
        stale_provider_keys=stale_provider_keys,
        apply_source_weights=False,
    )
    category_fit = _category_affinity(
        category,
        tags or [],
        profiles_by_key,
        stale_provider_keys=stale_provider_keys,
    )
    distance_fit = _distance_fit(transit_minutes)
    weighted_interest = interest_fit * 0.64
    weighted_category = category_fit * 0.15
    weighted_distance = distance_fit * 0.11
    weighted_budget = budget_fit * 0.10
    weighted_source = source_confidence * 0.05
    total_score = _clamp_score(
        weighted_interest
        + weighted_category
        + weighted_distance
        + weighted_budget
        + weighted_source
    )
    return (
        total_score,
        matched_topics,
        muted_topics,
        CandidateScoreComponents(
            interest_fit=interest_fit,
            category_fit=category_fit,
            distance_fit=distance_fit,
            budget_fit=budget_fit,
            source_confidence=source_confidence,
            transit_minutes=transit_minutes,
            weighted_interest=weighted_interest,
            weighted_category=weighted_category,
            weighted_distance=weighted_distance,
            weighted_budget=weighted_budget,
            weighted_source=weighted_source,
            source_weight_adjustment=round(
                ((interest_fit - unweighted_interest_fit) * 0.64)
                + ((category_fit - unweighted_category_fit) * 0.15),
                3,
            ),
            source_weight_labels=sorted(
                {
                    (
                        f"{provider_label(topic.source_provider or 'unknown')} "
                        f"{round(_taste_source_weight(topic.source_provider), 2)}x"
                    )
                    for topic in matched_topics
                    if abs(_taste_source_weight(topic.source_provider) - 1.0) >= 0.03
                }
            ),
            stale_provider_adjustment=round((interest_fit - unweighted_interest_fit) * 0.64, 3)
            if stale_topics
            else 0.0,
            stale_provider_labels=sorted({topic.label for topic in stale_topics}),
            supply_trust_adjustment=round((source_confidence - raw_source_confidence) * 0.05, 3),
            supply_trust_labels=supply_trust_labels or [],
        ),
    )


def _impact_label(contribution: float) -> str:
    magnitude = abs(contribution)
    if contribution < 0:
        if magnitude >= 0.12:
            return "holding it back"
        if magnitude >= 0.05:
            return "soft drag"
        return "small drag"

    if magnitude >= 0.35:
        return "driving this pick"
    if magnitude >= 0.12:
        return "strong support"
    if magnitude >= 0.05:
        return "helping"
    return "small lift"


def _score_breakdown_items(
    *,
    components: CandidateScoreComponents,
    matched_labels: list[str],
    muted_labels: list[str],
    feedback_adjustment: float,
    feedback_reason: dict | None,
) -> list[dict]:
    items: list[dict] = [
        {
            "key": "profile_fit",
            "label": "Profile fit",
            "impactLabel": _impact_label(components.weighted_interest),
            "detail": (
                f"Matched {_join_labels(matched_labels)}."
                if matched_labels
                else "No direct theme match, so this leaned on weaker defaults."
            ),
            "contribution": round(components.weighted_interest, 3),
            "direction": "positive",
            "summaryLabel": "profile fit",
        },
        {
            "key": "distance_fit",
            "label": "Travel fit",
            "impactLabel": _impact_label(components.weighted_distance),
            "detail": f"About {components.transit_minutes} min by transit from your current NYC anchor.",
            "contribution": round(components.weighted_distance, 3),
            "direction": "positive",
            "summaryLabel": "travel convenience",
        },
        {
            "key": "budget_fit",
            "label": "Budget fit",
            "impactLabel": _impact_label(components.weighted_budget),
            "detail": (
                "Comfortably inside budget."
                if components.budget_fit >= 0.85
                else "A little pricier, but still workable."
            ),
            "contribution": round(components.weighted_budget, 3),
            "direction": "positive",
            "summaryLabel": "budget fit",
        },
        {
            "key": "source_trust",
            "label": "Source trust",
            "impactLabel": _impact_label(components.weighted_source),
            "detail": (
                "Backed by a highly trusted source."
                if components.source_confidence >= 0.88
                else "Supported by a solid source signal."
                if components.source_confidence >= 0.78
                else "Still useful, but from a lighter-confidence source."
            ),
            "contribution": round(components.weighted_source, 3),
            "direction": "positive",
            "summaryLabel": "source trust",
        },
    ]

    if components.supply_trust_labels:
        items.append(
            {
                "key": "supply_trust",
                "label": "Supply freshness",
                "impactLabel": _impact_label(components.supply_trust_adjustment),
                "detail": "Event supply trust adjusted confidence: "
                f"{_join_labels(components.supply_trust_labels)}.",
                "contribution": components.supply_trust_adjustment,
                "direction": "negative" if components.supply_trust_adjustment < 0 else "positive",
                "summaryLabel": "supply trust",
            }
        )

    if components.weighted_category >= 0.015:
        items.append(
            {
                "key": "category_fit",
                "label": "Category overlap",
                "impactLabel": _impact_label(components.weighted_category),
                "detail": "Event tags and category echoed your active themes.",
                "contribution": round(components.weighted_category, 3),
                "direction": "positive",
                "summaryLabel": "category overlap",
            }
        )

    if abs(components.source_weight_adjustment) >= 0.015 and components.source_weight_labels:
        items.append(
            {
                "key": "taste_source_weight",
                "label": "Taste source weight",
                "impactLabel": _impact_label(components.source_weight_adjustment),
                "detail": (
                    "Passive taste was weighted by source trust: "
                    f"{_join_labels(components.source_weight_labels)}."
                ),
                "contribution": components.source_weight_adjustment,
                "direction": "positive" if components.source_weight_adjustment >= 0 else "negative",
                "summaryLabel": "taste source weighting",
            }
        )

    if components.stale_provider_adjustment <= -0.015 and components.stale_provider_labels:
        items.append(
            {
                "key": "stale_provider_guard",
                "label": "Provider freshness",
                "impactLabel": _impact_label(components.stale_provider_adjustment),
                "detail": (
                    "Latest Spotify sync failed, so Pulse suppressed stale "
                    f"{_join_labels(components.stale_provider_labels)} signals for this run."
                ),
                "contribution": components.stale_provider_adjustment,
                "direction": "negative",
                "summaryLabel": "stale Spotify taste",
            }
        )

    if muted_labels and feedback_reason is None:
        items.append(
            {
                "key": "muted_topics",
                "label": "Muted topics",
                "impactLabel": "holding it back",
                "detail": f"Muted topics like {_join_labels(muted_labels)} reduced this pick's ceiling.",
                "contribution": round(-0.06, 3),
                "direction": "negative",
                "summaryLabel": "muted topics",
            }
        )

    if abs(feedback_adjustment) >= 0.015:
        feedback_title = feedback_reason.get("title") if feedback_reason is not None else ""
        if feedback_adjustment >= 0 and isinstance(feedback_title, str) and feedback_title.startswith("Validated"):
            summary_label = "validated saves"
        elif feedback_adjustment >= 0 and feedback_title in {
            "Acted from digest",
            "Digest response pattern",
            "Digest-to-attendance",
            "Digest-to-ticket intent",
            "Digest-to-archive revisit",
        }:
            summary_label = "digest clicks"
        elif feedback_adjustment >= 0 and feedback_title in {"Clicked through before", "Click-through pattern"}:
            summary_label = "ticket clicks"
        elif feedback_adjustment >= 0 and feedback_title in {"Archived revisit", "Archive return pattern"}:
            summary_label = "archive revisits"
        elif feedback_adjustment >= 0 and feedback_title in {"Reopened before", "Return pattern"}:
            summary_label = "repeat opens"
        elif feedback_adjustment < 0 and feedback_title == "Seen, not opened":
            summary_label = "stale exposure"
        else:
            summary_label = "recent feedback" if feedback_adjustment >= 0 else "recent dismiss patterns"
        items.append(
            {
                "key": "feedback",
                "label": "Recent feedback",
                "impactLabel": _impact_label(feedback_adjustment),
                "detail": (
                    feedback_reason["detail"]
                    if feedback_reason is not None
                    else "Recent saves and dismisses nudged this venue's rank."
                ),
                "contribution": round(feedback_adjustment, 3),
                "direction": "positive" if feedback_adjustment >= 0 else "negative",
                "summaryLabel": summary_label,
            }
        )

    return sorted(items, key=lambda item: abs(item["contribution"]), reverse=True)


def _score_summary(score_breakdown: list[dict]) -> str | None:
    positive_items = [item for item in score_breakdown if item["contribution"] > 0.025]
    negative_items = [item for item in score_breakdown if item["contribution"] < -0.025]

    if positive_items[:2]:
        lead_labels = [item["summaryLabel"] for item in positive_items[:2]]
        if len(lead_labels) == 1:
            summary = f"Mostly driven by {lead_labels[0]}."
        else:
            summary = f"Led by {lead_labels[0]} and {lead_labels[1]}."
    elif positive_items:
        summary = f"Mostly driven by {positive_items[0]['summaryLabel']}."
    else:
        summary = "This pick is hanging together on smaller supporting signals."

    if negative_items:
        summary = f"{summary[:-1]}, with {negative_items[0]['summaryLabel']} holding it back."

    return summary


def _personalization_source_label(source_provider: str) -> str:
    return provider_label(source_provider)


def _personalization_provenance(
    *,
    matched_topics: list[UserInterestProfile],
    score_breakdown: list[dict],
    feedback_adjustment: float,
) -> list[dict]:
    grouped_topics: dict[str, list[UserInterestProfile]] = {}
    for topic in matched_topics:
        source_provider = topic.source_provider or "unknown"
        grouped_topics.setdefault(source_provider, []).append(topic)

    sources: list[dict] = [
        {
            "sourceProvider": source_provider,
            "label": _personalization_source_label(source_provider),
            "influence": "supporting",
            "topicLabels": [
                topic.label
                for topic in sorted(source_topics, key=lambda topic: (-topic.confidence, topic.label.lower()))
            ],
            "detail": _personalization_source_detail(source_provider, source_topics),
        }
        for source_provider, source_topics in grouped_topics.items()
    ]

    if abs(feedback_adjustment) >= 0.015:
        sources.append(
            {
                "sourceProvider": "feedback",
                "label": provider_label("feedback"),
                "influence": "supporting" if feedback_adjustment > 0 else "reducing",
                "topicLabels": [],
                "detail": "Your recent saves, dismissals, and planner actions adjusted this venue's rank.",
            }
        )

    stale_items = [item for item in score_breakdown if item.get("key") == "stale_provider_guard"]
    if stale_items:
        sources.append(
            {
                "sourceProvider": "spotify",
                "label": provider_label("spotify"),
                "influence": "suppressed",
                "topicLabels": [],
                "detail": stale_items[0].get("detail"),
            }
        )

    return sorted(
        sources,
        key=lambda source: (
            {"supporting": 0, "reducing": 1, "suppressed": 2}.get(source["influence"], 3),
            source["label"],
        ),
    )


def _personalization_source_detail(source_provider: str, topics: list[UserInterestProfile]) -> str:
    matched = _join_labels([topic.label for topic in topics])
    if source_provider == "spotify":
        return f"Spotify-derived taste matched {matched}."
    if source_provider == "manual":
        return f"Manual preferences matched {matched}."
    if source_provider in {"reddit", "reddit_export"}:
        return f"Connected profile taste matched {matched}."
    return f"Matched {matched}."


def _pack_reason_payload(
    reasons: list[dict],
    *,
    score_summary: str | None,
    score_breakdown: list[dict],
    personalization_provenance: list[dict] | None = None,
) -> list[dict]:
    payload = [dict(reason) for reason in reasons]
    if score_summary:
        payload.append({REASON_META_KEY: REASON_META_SCORE_SUMMARY, "summary": score_summary})
    if score_breakdown:
        payload.append({REASON_META_KEY: REASON_META_SCORE_BREAKDOWN, "items": score_breakdown})
    if personalization_provenance:
        payload.append(
            {
                REASON_META_KEY: REASON_META_PERSONALIZATION_PROVENANCE,
                "items": personalization_provenance,
            }
        )
    return payload


def _unpack_reason_payload(
    payload: list[dict] | None,
) -> tuple[
    list[RecommendationReason],
    str | None,
    list[RecommendationScoreBreakdownItem],
    list[RecommendationPersonalizationSource],
]:
    reasons: list[RecommendationReason] = []
    score_summary: str | None = None
    score_breakdown: list[RecommendationScoreBreakdownItem] = []
    personalization_provenance: list[RecommendationPersonalizationSource] = []

    for item in payload or []:
        meta_key = item.get(REASON_META_KEY)
        if meta_key == REASON_META_SCORE_SUMMARY:
            candidate_summary = item.get("summary")
            if isinstance(candidate_summary, str):
                score_summary = candidate_summary
            continue
        if meta_key == REASON_META_SCORE_BREAKDOWN:
            candidate_items = item.get("items") or []
            score_breakdown = [RecommendationScoreBreakdownItem(**candidate) for candidate in candidate_items]
            continue
        if meta_key == REASON_META_PERSONALIZATION_PROVENANCE:
            candidate_items = item.get("items") or []
            personalization_provenance = [
                RecommendationPersonalizationSource(**candidate) for candidate in candidate_items
            ]
            continue
        if "title" in item and "detail" in item:
            reasons.append(RecommendationReason(title=item["title"], detail=item["detail"]))

    return reasons, score_summary, score_breakdown, personalization_provenance


def _constraints_snapshot(constraints: UserConstraint | None) -> dict:
    if constraints is None:
        return {
            "city": SERVICE_AREA_NAME,
            "neighborhood": None,
            "zipCode": None,
            "radiusMiles": 8,
            "budgetLevel": "under_75",
            "preferredDays": ["Thursday", "Friday", "Saturday"],
            "socialMode": "either",
        }

    return {
        "city": constraints.city,
        "neighborhood": constraints.neighborhood,
        "zipCode": constraints.zip_code,
        "radiusMiles": constraints.radius_miles,
        "budgetLevel": constraints.budget_level,
        "preferredDays": constraints.preferred_days_csv.split(",") if constraints.preferred_days_csv else [],
        "socialMode": constraints.social_mode,
    }


def _topic_labels(rows: list[UserInterestProfile], *, muted: bool) -> list[str]:
    return [row.label for row in rows if row.muted is muted]


def _topic_source_label(source_provider: str) -> str:
    return provider_label(source_provider)


def _latest_profile_runs_by_provider(runs: list[ProfileRun]) -> dict[str, ProfileRun]:
    latest: dict[str, ProfileRun] = {}
    for run in runs:
        current = latest.get(run.provider)
        if current is None or _timestamp_utc(run.created_at) > _timestamp_utc(current.created_at):
            latest[run.provider] = run
    return latest


def _stale_interest_provider_keys(latest_runs_by_provider: dict[str, ProfileRun]) -> set[str]:
    return {
        provider
        for provider, run in latest_runs_by_provider.items()
        if provider == "spotify" and run.status != "completed"
    }


def _topic_source_summaries(
    rows: list[UserInterestProfile],
    latest_runs_by_provider: dict[str, ProfileRun] | None = None,
    connected_providers: set[str] | None = None,
) -> list[RecommendationTopicSourceSummary]:
    latest_runs_by_provider = latest_runs_by_provider or {}
    connected_providers = connected_providers or set()
    grouped: dict[str, list[UserInterestProfile]] = {}
    for row in rows:
        if row.muted:
            continue
        source_provider = row.source_provider or "unknown"
        grouped.setdefault(source_provider, []).append(row)

    summaries: list[RecommendationTopicSourceSummary] = []
    for source_provider, source_rows in grouped.items():
        if not source_rows:
            continue
        latest_run = latest_runs_by_provider.get(source_provider)
        health = build_connected_source_health(
            provider=source_provider,
            connected=source_provider in connected_providers or source_provider in {"manual", "feedback"},
            latest_run=latest_run,
            active_topic_count=len(source_rows),
        )
        summaries.append(
            RecommendationTopicSourceSummary(
                sourceProvider=source_provider,
                label=_topic_source_label(source_provider),
                topicCount=len(source_rows),
                averageConfidence=round(sum(row.confidence for row in source_rows) / len(source_rows), 3),
                topTopics=[
                    row.label
                    for row in sorted(source_rows, key=lambda row: (-row.confidence, row.label.lower()))[:4]
                ],
                latestRunStatus=latest_run.status if latest_run else None,
                latestRunAt=_timestamp_utc(latest_run.created_at).isoformat() if latest_run else None,
                connected=health.connected,
                stale=health.stale,
                currentlyInfluencingRanking=health.currentlyInfluencingRanking,
                confidenceState=health.confidenceState,
                healthReason=health.healthReason,
                debugReason=health.debugReason,
            )
        )
    return sorted(summaries, key=lambda item: (-item.topicCount, item.label.lower()))


def _topic_snapshot(rows: list[UserInterestProfile]) -> list[dict]:
    return sorted(
        [
            {
                "topicKey": row.topic_key,
                "confidence": round(row.confidence, 3),
                "sourceProvider": row.source_provider or "unknown",
                "boosted": row.boosted,
                "muted": row.muted,
            }
            for row in rows
        ],
        key=lambda item: item["topicKey"],
    )


def _context_hash(
    *,
    run: RecommendationRun,
    resolution: AnchorResolution,
    constraints: UserConstraint | None,
    topics: list[UserInterestProfile],
    items: list[VenueRecommendationCard],
) -> str:
    active_anchor = resolution.active_anchor
    requested_anchor = resolution.requested_anchor
    payload = {
        "runId": run.id,
        "generatedAt": _timestamp_utc(run.created_at).isoformat(),
        "serviceArea": SERVICE_AREA_NAME,
        "activeAnchor": {
            "label": _anchor_label(active_anchor),
            "source": active_anchor.source if active_anchor else "default",
            "latitude": active_anchor.latitude if active_anchor else None,
            "longitude": active_anchor.longitude if active_anchor else None,
            "zipCode": active_anchor.zip_code if active_anchor else None,
            "neighborhood": active_anchor.neighborhood if active_anchor else None,
        },
        "requestedAnchor": {
            "label": _anchor_label(requested_anchor) if requested_anchor else None,
            "source": requested_anchor.source if requested_anchor else None,
            "withinServiceArea": resolution.requested_within_service_area,
            "usedFallback": resolution.used_fallback_anchor,
        },
        "constraints": _constraints_snapshot(constraints),
        "topics": _topic_snapshot(topics),
        "shortlist": [
            {
                "venueId": item.venueId,
                "eventId": item.eventId,
                "score": round(item.score, 3),
                "scoreBand": item.scoreBand,
            }
            for item in items
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def _driver_summaries(
    items: list[VenueRecommendationCard],
) -> tuple[list[RecommendationDriverSummary], list[RecommendationDriverSummary]]:
    buckets: dict[str, dict] = {}
    for item in items:
        for factor in item.scoreBreakdown:
            bucket = buckets.setdefault(
                factor.key,
                {
                    "key": factor.key,
                    "label": factor.label,
                    "contributionSum": 0.0,
                    "count": 0,
                    "venues": [],
                },
            )
            bucket["contributionSum"] += factor.contribution
            bucket["count"] += 1
            bucket["venues"].append((abs(factor.contribution), item.venueName))

    summaries: list[RecommendationDriverSummary] = []
    for bucket in buckets.values():
        average_contribution = round(bucket["contributionSum"] / max(1, bucket["count"]), 3)
        unique_top_venues: list[str] = []
        for _, venue_name in sorted(bucket["venues"], key=lambda item: item[0], reverse=True):
            if venue_name in unique_top_venues:
                continue
            unique_top_venues.append(venue_name)
            if len(unique_top_venues) == 3:
                break

        summaries.append(
            RecommendationDriverSummary(
                key=bucket["key"],
                label=bucket["label"],
                impactLabel=_impact_label(average_contribution),
                averageContribution=average_contribution,
                venueCount=bucket["count"],
                topVenues=unique_top_venues,
            )
        )

    positive = sorted(
        [summary for summary in summaries if summary.averageContribution > 0.02],
        key=lambda summary: summary.averageContribution,
        reverse=True,
    )
    negative = sorted(
        [summary for summary in summaries if summary.averageContribution < -0.02],
        key=lambda summary: summary.averageContribution,
    )
    return positive[:4], negative[:4]


def _debug_top_drivers(score_breakdown: list[RecommendationScoreBreakdownItem]) -> list[RecommendationScoreBreakdownItem]:
    top_drivers = list(score_breakdown[:3])
    for factor in score_breakdown:
        if factor.key == "supply_trust" and factor not in top_drivers:
            top_drivers.append(factor)
    return top_drivers[:5]


def _feedback_reason_summaries(
    feedback_signals: FeedbackSignals,
    *,
    action: str,
) -> list[RecommendationFeedbackReasonSummary]:
    reason_weights = feedback_signals.saved_reasons if action == "save" else feedback_signals.dismissed_reasons
    reason_counts = (
        feedback_signals.saved_reason_counts if action == "save" else feedback_signals.dismissed_reason_counts
    )
    summaries = [
        RecommendationFeedbackReasonSummary(
            key=key,
            label=feedback_signals.reason_labels.get(key, _feedback_reason_label(key)),
            count=reason_counts.get(key, 0),
            weightedStrength=round(weight, 3),
        )
        for key, weight in reason_weights.items()
        if weight > 0
    ]
    summaries.sort(key=lambda item: (-item.weightedStrength, -item.count, item.label))
    return summaries[:5]


def _confirmed_save_reason_summaries(
    feedback_signals: FeedbackSignals,
) -> list[RecommendationFeedbackReasonSummary]:
    summaries = [
        RecommendationFeedbackReasonSummary(
            key=key,
            label=feedback_signals.reason_labels.get(key, _feedback_reason_label(key)),
            count=feedback_signals.confirmed_saved_reason_counts.get(key, 0),
            weightedStrength=round(weight, 3),
        )
        for key, weight in feedback_signals.confirmed_saved_reasons.items()
        if weight > 0
    ]
    summaries.sort(key=lambda item: (-item.weightedStrength, -item.count, item.label))
    return summaries[:5]


def _debug_summary_sentence(
    positive: list[RecommendationDriverSummary],
    negative: list[RecommendationDriverSummary],
) -> str | None:
    if not positive and not negative:
        return None
    if positive and negative:
        secondary_label = positive[1].label.lower() if len(positive) > 1 else positive[0].label.lower()
        return (
            f"This run is mostly driven by {positive[0].label.lower()} and {secondary_label}, "
            f"with {negative[0].label.lower()} creating the main drag."
        )
    if positive:
        lead = positive[0]
        if len(positive) > 1:
            return f"This run is mostly driven by {lead.label.lower()} and {positive[1].label.lower()}."
        return f"This run is mostly driven by {lead.label.lower()}."
    lead_drag = negative[0]
    return f"This run is mostly being held back by {lead_drag.label.lower()}."


def _comparison_summary_sentence(
    *,
    new_entrants: list[RecommendationRunComparisonItem],
    dropped_venues: list[RecommendationRunComparisonItem],
    movers: list[RecommendationRunComparisonItem],
) -> str | None:
    if not new_entrants and not dropped_venues and not movers:
        return "This run is very similar to the previous shortlist."

    parts: list[str] = []
    if new_entrants:
        lead = new_entrants[0]
        label = f"{lead.venueName} entered the shortlist"
        if len(new_entrants) > 1:
            label += f" alongside {len(new_entrants) - 1} other new venue{'s' if len(new_entrants) > 2 else ''}"
        parts.append(label)
    if movers:
        lead_mover = movers[0]
        direction = "up" if (lead_mover.rankDelta or 0) > 0 else "down"
        parts.append(f"{lead_mover.venueName} moved {direction} the most")
    if dropped_venues:
        lead_drop = dropped_venues[0]
        label = f"{lead_drop.venueName} dropped out"
        if len(dropped_venues) > 1:
            label += f" with {len(dropped_venues) - 1} other exit{'s' if len(dropped_venues) > 2 else ''}"
        parts.append(label)
    return ". ".join(parts) + "."


def _rank_lookup(items: list[VenueRecommendationCard]) -> dict[str, tuple[int, VenueRecommendationCard]]:
    return {
        item.venueId: (index + 1, item)
        for index, item in enumerate(items)
    }


def _movement_cues(
    current_card: VenueRecommendationCard | None,
    previous_card: VenueRecommendationCard | None,
) -> list[RecommendationMovementCue]:
    if current_card is None and previous_card is None:
        return []

    current_factors = {factor.key: factor for factor in current_card.scoreBreakdown} if current_card else {}
    previous_factors = {factor.key: factor for factor in previous_card.scoreBreakdown} if previous_card else {}
    cues: list[RecommendationMovementCue] = []

    for key in set(current_factors) | set(previous_factors):
        current_factor = current_factors.get(key)
        previous_factor = previous_factors.get(key)
        current_contribution = current_factor.contribution if current_factor is not None else 0.0
        previous_contribution = previous_factor.contribution if previous_factor is not None else 0.0
        delta = round(current_contribution - previous_contribution, 3)
        if abs(delta) < 0.03:
            continue

        factor = current_factor or previous_factor
        cues.append(
            RecommendationMovementCue(
                key=key,
                label=factor.label,
                delta=delta,
                direction="positive" if delta >= 0 else "negative",
            )
        )

    cues.sort(key=lambda item: abs(item.delta), reverse=True)
    return cues[:2]


def _movement_source_for_cue(cue: RecommendationMovementCue, detail: str | None) -> str:
    if cue.key == "feedback":
        text = (detail or "").lower()
        if any(term in text for term in ["marked", "real night out", "made it", "night-out", "planner"]):
            return "planner"
        return "feedback"
    if cue.key == "stale_provider_guard":
        return "source_health"
    if cue.key == "profile_fit":
        return "profile"
    return "score"


def _movement_explanations(
    *,
    current_card: VenueRecommendationCard | None,
    previous_card: VenueRecommendationCard | None,
    movement_cues: list[RecommendationMovementCue],
    movement: str,
) -> list[RecommendationMovementExplanation]:
    card = current_card or previous_card
    if card is None:
        return []

    current_factors = {factor.key: factor for factor in current_card.scoreBreakdown} if current_card else {}
    previous_factors = {factor.key: factor for factor in previous_card.scoreBreakdown} if previous_card else {}
    explanations: list[RecommendationMovementExplanation] = []

    for cue in movement_cues:
        factor = current_factors.get(cue.key) or previous_factors.get(cue.key)
        detail = factor.detail if factor else f"{cue.label} changed by {cue.delta:+.3f}."
        explanations.append(
            RecommendationMovementExplanation(
                title=cue.label,
                detail=detail,
                direction=cue.direction,
                source=_movement_source_for_cue(cue, detail),
            )
        )

    provenance = current_card.personalizationProvenance if current_card else previous_card.personalizationProvenance
    for source in provenance:
        if source.influence == "suppressed" and source.detail:
            explanations.append(
                RecommendationMovementExplanation(
                    title=f"{source.label} paused",
                    detail=source.detail,
                    direction="negative",
                    source="source_health",
                )
            )
            break
        if source.sourceProvider in {"spotify", "manual"} and source.influence == "supporting" and source.detail:
            explanations.append(
                RecommendationMovementExplanation(
                    title=f"{source.label} taste",
                    detail=source.detail,
                    direction="positive",
                    source="profile",
                )
            )
            break

    if not explanations:
        score_delta = None
        if current_card is not None and previous_card is not None:
            score_delta = round(current_card.score - previous_card.score, 3)
        direction = "neutral"
        if movement in {"up", "new"} or (score_delta is not None and score_delta > 0):
            direction = "positive"
        elif movement in {"down", "dropped"} or (score_delta is not None and score_delta < 0):
            direction = "negative"
        explanations.append(
            RecommendationMovementExplanation(
                title="Score movement",
                detail=card.scoreSummary or "Ranking changed because the score mix shifted between runs.",
                direction=direction,
                source="score",
            )
        )

    seen: set[tuple[str, str]] = set()
    unique: list[RecommendationMovementExplanation] = []
    for explanation in explanations:
        key = (explanation.source, explanation.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(explanation)
    unique.sort(
        key=lambda explanation: (
            {"source_health": 0, "planner": 1, "feedback": 2, "profile": 3, "score": 4}.get(explanation.source, 5),
            explanation.title,
        )
    )
    return unique[:2]


def _comparison_item(
    *,
    current_rank: int | None,
    previous_rank: int | None,
    current_card: VenueRecommendationCard | None,
    previous_card: VenueRecommendationCard | None,
    movement: str,
) -> RecommendationRunComparisonItem:
    card = current_card or previous_card
    rank_delta = None
    if current_rank is not None and previous_rank is not None:
        rank_delta = previous_rank - current_rank

    current_score = current_card.score if current_card is not None else None
    previous_score = previous_card.score if previous_card is not None else None
    score_delta = None
    if current_score is not None and previous_score is not None:
        score_delta = round(current_score - previous_score, 3)

    movement_cues = _movement_cues(current_card, previous_card)
    return RecommendationRunComparisonItem(
        venueId=card.venueId,
        venueName=card.venueName,
        neighborhood=card.neighborhood,
        currentRank=current_rank,
        previousRank=previous_rank,
        rankDelta=rank_delta,
        currentScore=current_score,
        previousScore=previous_score,
        scoreDelta=score_delta,
        scoreBand=current_card.scoreBand if current_card is not None else previous_card.scoreBand if previous_card is not None else None,
        scoreSummary=current_card.scoreSummary if current_card is not None else previous_card.scoreSummary if previous_card is not None else None,
        movementCues=movement_cues,
        movementExplanation=_movement_explanations(
            current_card=current_card,
            previous_card=previous_card,
            movement_cues=movement_cues,
            movement=movement,
        ),
        movement=movement,
    )


def _compare_shortlists(
    current_items: list[VenueRecommendationCard],
    previous_items: list[VenueRecommendationCard],
) -> tuple[
    list[RecommendationRunComparisonItem],
    list[RecommendationRunComparisonItem],
    list[RecommendationRunComparisonItem],
    list[RecommendationRunComparisonItem],
]:
    current_lookup = _rank_lookup(current_items)
    previous_lookup = _rank_lookup(previous_items)

    new_entrants: list[RecommendationRunComparisonItem] = []
    dropped_venues: list[RecommendationRunComparisonItem] = []
    movers: list[RecommendationRunComparisonItem] = []
    steady_leaders: list[RecommendationRunComparisonItem] = []

    for venue_id, (current_rank, current_card) in current_lookup.items():
        previous = previous_lookup.get(venue_id)
        if previous is None:
            new_entrants.append(
                _comparison_item(
                    current_rank=current_rank,
                    previous_rank=None,
                    current_card=current_card,
                    previous_card=None,
                    movement="new",
                )
            )
            continue

        previous_rank, previous_card = previous
        comparison = _comparison_item(
            current_rank=current_rank,
            previous_rank=previous_rank,
            current_card=current_card,
            previous_card=previous_card,
            movement="steady",
        )
        if comparison.rankDelta and comparison.rankDelta != 0:
            comparison.movement = "up" if comparison.rankDelta > 0 else "down"
            movers.append(comparison)
        elif current_rank <= 3:
            steady_leaders.append(comparison)

    for venue_id, (previous_rank, previous_card) in previous_lookup.items():
        if venue_id in current_lookup:
            continue
        dropped_venues.append(
            _comparison_item(
                current_rank=None,
                previous_rank=previous_rank,
                current_card=None,
                previous_card=previous_card,
                movement="dropped",
            )
        )

    new_entrants.sort(key=lambda item: item.currentRank or 999)
    dropped_venues.sort(key=lambda item: item.previousRank or 999)
    movers.sort(key=lambda item: (-abs(item.rankDelta or 0), item.currentRank or 999))
    steady_leaders.sort(key=lambda item: item.currentRank or 999)
    return new_entrants[:4], dropped_venues[:4], movers[:6], steady_leaders[:4]


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _derive_topic_keys(event: CanonicalEvent, tags: list[str]) -> list[str]:
    text = " ".join(
        filter(
            None,
            [
                _normalize_text(event.title),
                _normalize_text(event.summary),
                _normalize_text(event.category),
                " ".join(_normalize_text(tag) for tag in tags),
            ],
        )
    )
    derived = [
        key
        for key, keywords in TOPIC_KEYWORD_MAP.items()
        if any(keyword in text for keyword in keywords)
    ]
    return derived


def _secondary_events_payload(entries: list[dict]) -> list[dict]:
    payload: list[dict] = []
    for entry in entries[1:3]:
        payload.append(
            {
                "eventId": entry["occurrence"].id,
                "title": entry["event"].title,
                "startsAt": entry["occurrence"].starts_at,
            }
        )
    return payload


def _dominant_topic_key(topic_keys: list[str], profiles_by_key: dict[str, UserInterestProfile]) -> str | None:
    best_key: str | None = None
    best_weight = -1.0
    for key in topic_keys:
        topic = profiles_by_key.get(key)
        if topic is None:
            continue
        weight = _topic_weight(topic)
        if weight > best_weight:
            best_weight = weight
            best_key = key
    return best_key or (topic_keys[0] if topic_keys else None)


def _active_theme_keys(profiles_by_key: dict[str, UserInterestProfile]) -> set[str]:
    return {
        key
        for key, topic in profiles_by_key.items()
        if not topic.muted and topic.confidence >= 0.6
    }


def _selection_mix_score(
    primary: dict,
    *,
    chosen_entries: list[dict],
    preferred_theme_keys: set[str],
) -> float:
    score = primary["score"]
    category = _normalize_text(primary.get("category"))
    topic_keys = set(primary.get("topic_keys", []))
    dominant_topic_key = primary.get("dominant_topic_key")

    chosen_categories = [_normalize_text(entry.get("category")) for entry in chosen_entries]
    chosen_dominant_topics = [entry.get("dominant_topic_key") for entry in chosen_entries]
    covered_theme_keys = {
        key
        for entry in chosen_entries
        for key in entry.get("topic_keys", [])
    }

    if dominant_topic_key and dominant_topic_key in preferred_theme_keys and dominant_topic_key not in covered_theme_keys:
        score += 0.06

    uncovered_broad_topics = (topic_keys & preferred_theme_keys & BROAD_CULTURAL_THEME_KEYS) - covered_theme_keys
    if uncovered_broad_topics:
        score += 0.04

    duplicate_category_count = sum(1 for chosen_category in chosen_categories if category and chosen_category == category)
    duplicate_topic_count = sum(
        1 for chosen_topic in chosen_dominant_topics if dominant_topic_key and chosen_topic == dominant_topic_key
    )

    score -= duplicate_category_count * 0.03
    score -= duplicate_topic_count * 0.05
    return score


def _select_ranked_venues(
    ranked_venues: list[list[dict]],
    profiles_by_key: dict[str, UserInterestProfile],
    *,
    limit: int = 8,
) -> list[list[dict]]:
    if len(ranked_venues) <= limit:
        return ranked_venues

    preferred_theme_keys = _active_theme_keys(profiles_by_key)
    remaining = [entries for entries in ranked_venues if entries]
    chosen: list[list[dict]] = []
    chosen_entries: list[dict] = []

    while remaining and len(chosen) < limit:
        best_index = 0
        best_score = float("-inf")
        for index, entries in enumerate(remaining):
            selection_score = _selection_mix_score(
                entries[0],
                chosen_entries=chosen_entries,
                preferred_theme_keys=preferred_theme_keys,
            )
            if selection_score > best_score:
                best_score = selection_score
                best_index = index

        selected_entries = remaining.pop(best_index)
        chosen.append(selected_entries)
        chosen_entries.append(selected_entries[0])

    return chosen


def _archive_kind(provider: str | None) -> str:
    if not provider:
        return "live"
    if "scheduled" in provider:
        return "scheduled"
    if "preview" in provider:
        return "preview"
    return "snapshot"


def _archive_title(kind: str) -> str:
    if kind == "scheduled":
        return "Weekly digest"
    if kind == "preview":
        return "Preview send"
    if kind == "snapshot":
        return "Saved snapshot"
    return "Current shortlist"


def _display_timezone(user: User) -> str:
    return user.timezone or "America/New_York"


def _deletable_run_ids(
    run_ids: list[str],
    protected_run_ids: set[str],
    *,
    keep_recent_count: int = 0,
) -> list[str]:
    retained_recent_ids = set(run_ids[:keep_recent_count])
    retained_ids = retained_recent_ids | protected_run_ids
    return [run_id for run_id in run_ids if run_id not in retained_ids]


def _run_is_stale(run: RecommendationRun) -> bool:
    return datetime.now(tz=UTC) - _timestamp_utc(run.created_at) >= RECOMMENDATION_MAX_AGE


def _parse_occurrence_start(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _occurrence_is_rankable(occurrence: EventOccurrence, *, now: datetime | None = None) -> bool:
    starts_at = _parse_occurrence_start(occurrence.starts_at)
    if starts_at is None:
        return False
    current_time = now or datetime.now(tz=UTC)
    if starts_at < current_time - OCCURRENCE_LOOKBACK_WINDOW:
        return False
    if starts_at > current_time + OCCURRENCE_LOOKAHEAD_WINDOW:
        return False
    return True


def _run_context_changed(
    run: RecommendationRun,
    anchor: UserAnchorLocation | None,
    constraints: UserConstraint | None,
) -> bool:
    run_created_at = _timestamp_utc(run.created_at)

    if anchor is not None and _timestamp_utc(anchor.created_at) > run_created_at:
        return True

    if constraints is None:
        return False

    constraint_updated_at = constraints.updated_at or constraints.created_at
    return _timestamp_utc(constraint_updated_at) > run_created_at


async def _catalog_changed_since(
    session: AsyncSession,
    run: RecommendationRun,
) -> bool:
    latest_occurrence_update = await session.scalar(
        select(EventOccurrence.updated_at)
        .where(EventOccurrence.is_active.is_(True))
        .order_by(desc(EventOccurrence.updated_at))
        .limit(1)
    )
    if latest_occurrence_update is None:
        return False
    return _timestamp_utc(latest_occurrence_update) > _timestamp_utc(run.created_at)


async def _profile_runs_changed_since(
    session: AsyncSession,
    user_id: str,
    run: RecommendationRun,
) -> bool:
    latest_profile_run_update = await session.scalar(
        select(ProfileRun.created_at)
        .where(ProfileRun.user_id == user_id)
        .order_by(desc(ProfileRun.created_at))
        .limit(1)
    )
    if latest_profile_run_update is None:
        return False
    return _timestamp_utc(latest_profile_run_update) > _timestamp_utc(run.created_at)


async def _replace_user_runs(session: AsyncSession, user_id: str) -> None:
    runs = await _latest_runs(
        session,
        user_id,
        limit=RECOMMENDATION_RUN_HISTORY_LIMIT + 24,
    )
    run_ids = [run.id for run in runs]
    if not run_ids:
        return

    protected_run_ids = set(
        (
            await session.scalars(
                select(DigestDelivery.recommendation_run_id).where(
                    DigestDelivery.recommendation_run_id.in_(run_ids)
                )
            )
        ).all()
    )
    deletable_run_ids = _deletable_run_ids(
        run_ids,
        protected_run_ids,
        keep_recent_count=max(0, RECOMMENDATION_RUN_HISTORY_LIMIT - 1),
    )
    if not deletable_run_ids:
        return

    await session.execute(delete(VenueRecommendation).where(VenueRecommendation.run_id.in_(deletable_run_ids)))
    await session.execute(delete(DigestDelivery).where(DigestDelivery.recommendation_run_id.in_(deletable_run_ids)))
    await session.execute(delete(RecommendationRun).where(RecommendationRun.id.in_(deletable_run_ids)))
    await session.flush()


async def refresh_recommendations_for_user(
    session: AsyncSession,
    user: User,
    *,
    force: bool = False,
    provider: str = "catalog",
    model_name: str = "pulse-deterministic-v1",
) -> RecommendationRun:
    anchor = await _user_anchor(session, user.id)
    constraints = await _user_constraints(session, user.id)
    existing_run = await _latest_run(session, user.id)
    if (
        existing_run is not None
        and not force
        and not _run_is_stale(existing_run)
        and not _run_context_changed(existing_run, anchor, constraints)
        and not await _catalog_changed_since(session, existing_run)
        and not await _profile_runs_changed_since(session, user.id, existing_run)
    ):
        return existing_run

    origin_latitude, origin_longitude = _anchor_coordinates(anchor)
    viewport = _viewport_for_anchor(anchor)
    topic_rows = (
        await session.scalars(select(UserInterestProfile).where(UserInterestProfile.user_id == user.id))
    ).all()
    profiles_by_key = {row.topic_key: row for row in topic_rows}
    profile_runs = list(
        (
            await session.scalars(
                select(ProfileRun)
                .where(ProfileRun.user_id == user.id)
                .order_by(ProfileRun.created_at.desc())
            )
        ).all()
    )
    stale_provider_keys = _stale_interest_provider_keys(_latest_profile_runs_by_provider(profile_runs))
    effective_profiles_by_key = {
        key: topic
        for key, topic in profiles_by_key.items()
        if not _topic_is_from_stale_provider(topic, stale_provider_keys)
    }
    feedback_signals = await _feedback_signals(session, user.id)

    occurrence_rows = (
        await session.scalars(
            select(EventOccurrence)
            .where(EventOccurrence.is_active.is_(True))
            .order_by(EventOccurrence.starts_at.asc())
        )
    ).all()

    venue_entries: dict[str, list[dict]] = {}
    for occurrence in occurrence_rows:
        if not _occurrence_is_rankable(occurrence):
            continue
        venue = await session.get(Venue, occurrence.venue_id)
        event = await session.get(CanonicalEvent, occurrence.event_id)
        if not venue or not event:
            continue
        source = await session.get(EventSource, event.source_id)
        if venue.city not in {"New York City", "New York", "Brooklyn", "Queens", "Bronx", "Staten Island"}:
            continue

        travel = estimate_travel_bands(origin_latitude, origin_longitude, venue.latitude, venue.longitude)
        metadata = occurrence.metadata_json or {}
        topic_keys = metadata.get("topicKeys") or _derive_topic_keys(event, metadata.get("tags", []))
        raw_source_confidence = float(metadata.get("sourceConfidence", 0.75) or 0.75)
        supply_trust = _supply_trust_assessment(occurrence, raw_source_confidence, source)
        source_confidence = supply_trust.effective_confidence
        budget_fit = _budget_fit(constraints, occurrence)
        transit_minutes = _transit_minutes(travel)
        score, matched_topics, muted_topics, score_components = _candidate_score_with_components(
            topic_keys,
            profiles_by_key,
            source_confidence,
            transit_minutes,
            budget_fit,
            category=event.category,
            tags=metadata.get("tags", []),
            stale_provider_keys=stale_provider_keys,
            raw_source_confidence=raw_source_confidence,
            supply_trust_labels=supply_trust.labels,
        )
        feedback_adjustment, feedback_reason = _feedback_adjustment(
            topic_keys=topic_keys,
            profiles_by_key=profiles_by_key,
            venue=venue,
            feedback_signals=feedback_signals,
            transit_minutes=transit_minutes,
            budget_fit=budget_fit,
            source_confidence=source_confidence,
        )
        adjusted_score = _clamp_score(score + feedback_adjustment)
        matched_labels = [topic.label for topic in matched_topics]
        muted_labels = [topic.label for topic in muted_topics]
        score_breakdown = _score_breakdown_items(
            components=score_components,
            matched_labels=matched_labels,
            muted_labels=muted_labels,
            feedback_adjustment=feedback_adjustment,
            feedback_reason=feedback_reason,
        )
        personalization_provenance = _personalization_provenance(
            matched_topics=matched_topics,
            score_breakdown=score_breakdown,
            feedback_adjustment=feedback_adjustment,
        )
        score_summary = _score_summary(score_breakdown)
        entry = {
            "venue": venue,
            "event": event,
            "occurrence": occurrence,
            "travel": travel,
            "score": adjusted_score,
            "score_band": _score_band(adjusted_score),
            "category": event.category,
            "topic_keys": topic_keys,
            "dominant_topic_key": _dominant_topic_key(topic_keys, effective_profiles_by_key),
            "reasons": _reason_items(
                matched_topics=matched_topics,
                muted_topics=muted_topics,
                travel=travel,
                budget_fit=budget_fit,
                venue=venue,
                feedback_reason=feedback_reason,
                source_weight_labels=score_components.source_weight_labels
                if abs(score_components.source_weight_adjustment) >= 0.015
                else None,
            ),
            "score_summary": score_summary,
            "score_breakdown": score_breakdown,
            "personalization_provenance": personalization_provenance,
        }
        venue_entries.setdefault(venue.id, []).append(entry)

    await _replace_user_runs(session, user.id)
    run = RecommendationRun(
        user_id=user.id,
        provider=provider,
        model_name=model_name,
        viewport_json=viewport,
    )
    session.add(run)
    await session.flush()

    ranked_venues = sorted(
        (
            sorted(entries, key=lambda item: item["score"], reverse=True)
            for entries in venue_entries.values()
        ),
        key=lambda entries: entries[0]["score"] if entries else 0.0,
        reverse=True,
    )

    selected_ranked_venues = _select_ranked_venues(ranked_venues, effective_profiles_by_key, limit=8)

    for rank, entries in enumerate(selected_ranked_venues, start=1):
        primary = entries[0]
        session.add(
            VenueRecommendation(
                run_id=run.id,
                venue_id=primary["venue"].id,
                event_occurrence_id=primary["occurrence"].id,
                rank=rank,
                score=primary["score"],
                score_band=primary["score_band"],
                reasons_json=_pack_reason_payload(
                    primary["reasons"],
                    score_summary=primary["score_summary"],
                    score_breakdown=primary["score_breakdown"],
                    personalization_provenance=primary["personalization_provenance"],
                ),
                travel_json=primary["travel"],
                secondary_events_json=_secondary_events_payload(entries),
            )
        )

    await session.commit()
    await session.refresh(run)
    return run


def _empty_response(display_timezone: str = "America/New_York") -> RecommendationsMapResponse:
    return RecommendationsMapResponse(
        viewport=DEFAULT_VIEWPORT,
        pins=[],
        cards={},
        generatedAt="",
        displayTimezone=display_timezone,
        userConstraint={},
        mapContext=MapContext(serviceArea=SERVICE_AREA_NAME),
    )


async def _cards_for_run(
    session: AsyncSession,
    run: RecommendationRun,
) -> tuple[list[MapVenuePin], list[VenueRecommendationCard], dict[str, VenueRecommendationCard]]:
    recommendation_rows = (
        await session.scalars(
            select(VenueRecommendation)
            .where(VenueRecommendation.run_id == run.id)
            .order_by(VenueRecommendation.rank.asc())
        )
    ).all()
    if not recommendation_rows:
        return [], [], {}

    pins: list[MapVenuePin] = []
    items: list[VenueRecommendationCard] = []
    cards: dict[str, VenueRecommendationCard] = {}

    for index, recommendation in enumerate(recommendation_rows):
        venue = await session.get(Venue, recommendation.venue_id)
        occurrence = await session.get(EventOccurrence, recommendation.event_occurrence_id)
        event = await session.get(CanonicalEvent, occurrence.event_id if occurrence else None)
        source = await session.get(EventSource, event.source_id if event else None)
        if not venue or not occurrence or not event or not source:
            continue

        travel = recommendation.travel_json or estimate_travel_bands(
            DEFAULT_VIEWPORT["latitude"],
            DEFAULT_VIEWPORT["longitude"],
            venue.latitude,
            venue.longitude,
        )
        reasons, score_summary, score_breakdown, personalization_provenance = _unpack_reason_payload(
            recommendation.reasons_json
        )

        card = VenueRecommendationCard(
            venueId=venue.id,
            venueName=venue.name,
            neighborhood=venue.neighborhood or "NYC",
            address=venue.address,
            eventTitle=event.title,
            eventId=occurrence.id,
            startsAt=occurrence.starts_at,
            priceLabel=_price_label(occurrence.min_price, occurrence.max_price),
            ticketUrl=occurrence.ticket_url,
            scoreBand=recommendation.score_band,
            score=recommendation.score,
            travel=[TravelEstimate(**item) for item in travel],
            reasons=reasons,
            freshness=_build_freshness(occurrence),
            provenance=_build_provenance(source, occurrence),
            scoreSummary=score_summary,
            scoreBreakdown=score_breakdown,
            personalizationProvenance=personalization_provenance,
            secondaryEvents=recommendation.secondary_events_json or [],
        )
        items.append(card)
        cards[venue.id] = card
        pins.append(
            MapVenuePin(
                venueId=venue.id,
                venueName=venue.name,
                latitude=venue.latitude,
                longitude=venue.longitude,
                scoreBand=recommendation.score_band,
                selected=index == 0,
            )
        )

    return pins, items, cards


def _build_freshness(occurrence: EventOccurrence) -> RecommendationFreshness:
    discovered_at = _iso_or_none(occurrence.created_at)
    last_verified_at = _iso_or_none(occurrence.updated_at)
    freshness_label = _freshness_label(occurrence.updated_at)
    return RecommendationFreshness(
        discoveredAt=discovered_at,
        lastVerifiedAt=last_verified_at,
        freshnessLabel=freshness_label,
    )


def _supply_trust_assessment(
    occurrence: EventOccurrence,
    raw_confidence: float,
    source: EventSource | None = None,
    *,
    now: datetime | None = None,
) -> SupplyTrustAssessment:
    now = now or datetime.now(tz=UTC)
    metadata = occurrence.metadata_json or {}
    confidence_penalty = 0.0
    labels: list[str] = []
    debug_reasons: list[str] = []

    verified_at = occurrence.updated_at
    if verified_at is None:
        confidence_penalty += 0.06
        labels.append("Verification missing")
        debug_reasons.append("missing updated_at")
    else:
        verification_age = now - _timestamp_utc(verified_at)
        if verification_age <= timedelta(days=1):
            labels.append("Recently verified")
            debug_reasons.append("verified within 24h")
        elif verification_age > timedelta(days=7):
            confidence_penalty += 0.22
            labels.append("Stale verification")
            debug_reasons.append("last verified over 7d ago")
        elif verification_age > timedelta(days=3):
            confidence_penalty += 0.16
            labels.append("Stale verification")
            debug_reasons.append("last verified over 3d ago")
        else:
            labels.append("Checked this week")
            debug_reasons.append("verified within 3d")

    if raw_confidence < 0.72:
        confidence_penalty += 0.06
        labels.append("Weak source confidence")
        debug_reasons.append(f"raw source confidence {raw_confidence:.2f}")

    has_source_url = bool(metadata.get("sourceUrl") or metadata.get("url") or (source.base_url if source else None))
    if not occurrence.ticket_url and not has_source_url:
        confidence_penalty += 0.07
        labels.append("Missing ticket/source URL")
        debug_reasons.append("no ticket_url or source URL")

    effective_confidence = max(0.2, min(0.99, raw_confidence - confidence_penalty))
    return SupplyTrustAssessment(
        raw_confidence=round(raw_confidence, 3),
        effective_confidence=round(effective_confidence, 3),
        confidence_adjustment=round(effective_confidence - raw_confidence, 3),
        labels=_dedupe_preserve_order(labels),
        debug_reasons=debug_reasons,
    )


async def _supply_quality_rollups(
    session: AsyncSession,
    run: RecommendationRun,
) -> list[RecommendationSupplyQualityRollup]:
    recommendation_rows = (
        await session.scalars(
            select(VenueRecommendation)
            .where(VenueRecommendation.run_id == run.id)
            .order_by(VenueRecommendation.rank.asc())
        )
    ).all()
    buckets: dict[str, dict] = {}

    for recommendation in recommendation_rows:
        occurrence = await session.get(EventOccurrence, recommendation.event_occurrence_id)
        event = await session.get(CanonicalEvent, occurrence.event_id if occurrence else None)
        source = await session.get(EventSource, event.source_id if event else None)
        if not occurrence or not event or not source:
            continue

        metadata = occurrence.metadata_json or {}
        raw_confidence = float(metadata.get("sourceConfidence", 0.75) or 0.75)
        assessment = _supply_trust_assessment(occurrence, raw_confidence, source)
        source_name = _present_source_name(source.name)
        bucket_key = f"{source.kind}:{source_name}"
        bucket = buckets.setdefault(
            bucket_key,
            {
                "sourceName": source_name,
                "sourceKind": source.kind,
                "recommendationCount": 0,
                "eventIds": set(),
                "staleVerificationCount": 0,
                "weakSourceConfidenceCount": 0,
                "missingTicketUrlCount": 0,
                "missingSourceUrlCount": 0,
                "rawConfidenceSum": 0.0,
                "effectiveConfidenceSum": 0.0,
                "trustReasonCounts": {},
            },
        )
        bucket["recommendationCount"] += 1
        bucket["eventIds"].add(occurrence.id)
        bucket["rawConfidenceSum"] += assessment.raw_confidence
        bucket["effectiveConfidenceSum"] += assessment.effective_confidence

        if "Stale verification" in assessment.labels:
            bucket["staleVerificationCount"] += 1
        if "Weak source confidence" in assessment.labels:
            bucket["weakSourceConfidenceCount"] += 1
        if not occurrence.ticket_url:
            bucket["missingTicketUrlCount"] += 1
        if not (metadata.get("sourceUrl") or metadata.get("url") or source.base_url):
            bucket["missingSourceUrlCount"] += 1

        for label in assessment.labels:
            bucket["trustReasonCounts"][label] = bucket["trustReasonCounts"].get(label, 0) + 1

    rollups: list[RecommendationSupplyQualityRollup] = []
    for bucket in buckets.values():
        count = max(1, bucket["recommendationCount"])
        top_reasons = [
            label
            for label, _ in sorted(
                bucket["trustReasonCounts"].items(),
                key=lambda item: (-item[1], item[0]),
            )[:4]
        ]
        rollups.append(
            RecommendationSupplyQualityRollup(
                sourceName=bucket["sourceName"],
                sourceKind=bucket["sourceKind"],
                recommendationCount=bucket["recommendationCount"],
                eventCount=len(bucket["eventIds"]),
                staleVerificationCount=bucket["staleVerificationCount"],
                weakSourceConfidenceCount=bucket["weakSourceConfidenceCount"],
                missingTicketUrlCount=bucket["missingTicketUrlCount"],
                missingSourceUrlCount=bucket["missingSourceUrlCount"],
                averageRawSourceConfidence=round(bucket["rawConfidenceSum"] / count, 3),
                averageEffectiveSourceConfidence=round(bucket["effectiveConfidenceSum"] / count, 3),
                topTrustReasons=top_reasons,
            )
        )

    rollups.sort(
        key=lambda item: (
            -item.staleVerificationCount,
            -item.weakSourceConfidenceCount,
            -item.missingTicketUrlCount,
            item.sourceName,
        )
    )
    return rollups


def _build_provenance(source: EventSource, occurrence: EventOccurrence) -> RecommendationProvenance:
    metadata = occurrence.metadata_json or {}
    raw_confidence = float(metadata.get("sourceConfidence", 0.75) or 0.75)
    supply_trust = _supply_trust_assessment(occurrence, raw_confidence, source)
    return RecommendationProvenance(
        sourceName=_present_source_name(source.name),
        sourceKind=source.kind,
        sourceConfidence=round(supply_trust.effective_confidence, 2),
        sourceConfidenceLabel=_source_confidence_label(supply_trust.effective_confidence, source.kind),
        sourceBaseUrl=source.base_url,
        hasTicketUrl=bool(occurrence.ticket_url),
        trustReasons=supply_trust.labels,
    )


def _present_source_name(name: str) -> str:
    if name == "ticketmaster":
        return "Ticketmaster"
    if name == "curated_venues":
        return "Curated venue calendars"
    return name.replace("_", " ").title()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _source_confidence_label(confidence: float, source_kind: str) -> str:
    if source_kind == "curated_calendar" and confidence >= 0.8:
        return "High trust"
    if confidence >= 0.9:
        return "High trust"
    if confidence >= 0.78:
        return "Solid signal"
    return "Emerging signal"


def _freshness_label(updated_at: datetime | None) -> str:
    if updated_at is None:
        return "Verification missing"
    age = datetime.now(tz=UTC) - _timestamp_utc(updated_at)
    if age <= timedelta(hours=6):
        return "Verified recently"
    if age <= timedelta(days=1):
        return "Checked today"
    if age <= timedelta(days=3):
        return "Checked this week"
    return "Stale verification"


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _timestamp_utc(value).isoformat()


async def get_map_recommendations(
    session: AsyncSession,
    user: User,
) -> RecommendationsMapResponse:
    display_timezone = _display_timezone(user)
    anchor_resolution = await _user_anchor_resolution(session, user.id)
    run = await refresh_recommendations_for_user(session, user)
    if run is None:
        return _empty_response(display_timezone)

    constraints = await _user_constraints(session, user.id)
    pins, items, cards = await _cards_for_run(session, run)
    if not items:
        return _empty_response(display_timezone)

    topic_rows = (
        await session.scalars(select(UserInterestProfile).where(UserInterestProfile.user_id == user.id))
    ).all()
    context_hash = _context_hash(
        run=run,
        resolution=anchor_resolution,
        constraints=constraints,
        topics=list(topic_rows),
        items=items,
    )
    event_plan = build_event_plan(
        items,
        pins,
        budget_level=constraints.budget_level if constraints else "under_75",
        timezone=display_timezone,
    )
    planner_session = await get_or_create_event_plan_session(
        session,
        user_id=user.id,
        recommendation_run_id=run.id,
        recommendation_context_hash=context_hash,
        planner=event_plan,
        budget_level=constraints.budget_level if constraints else "under_75",
        timezone=display_timezone,
    )
    event_plan = await apply_event_plan_session_state(
        session,
        planner=event_plan,
        planner_session=planner_session,
    )
    await session.commit()

    return RecommendationsMapResponse(
        viewport=run.viewport_json,
        pins=pins,
        cards=cards,
        generatedAt=run.created_at.isoformat(),
        displayTimezone=display_timezone,
        userConstraint={
            "city": constraints.city if constraints else SERVICE_AREA_NAME,
            "neighborhood": constraints.neighborhood if constraints else None,
            "zipCode": constraints.zip_code if constraints else None,
            "radiusMiles": constraints.radius_miles if constraints else 8,
            "budgetLevel": constraints.budget_level if constraints else "under_75",
            "preferredDays": constraints.preferred_days_csv.split(",") if constraints else ["Thursday", "Friday", "Saturday"],
            "socialMode": constraints.social_mode if constraints else "either",
        },
        mapContext=_build_map_context(anchor_resolution),
        tonightPlanner=event_plan,
        eventPlan=event_plan,
    )


async def get_recommendation_debug_summary(
    session: AsyncSession,
    user: User,
) -> RecommendationDebugSummary:
    run = await refresh_recommendations_for_user(session, user)
    if run is None:
        return RecommendationDebugSummary()

    anchor_resolution = await _user_anchor_resolution(session, user.id)
    constraints = await _user_constraints(session, user.id)
    topic_rows = list(
        (
            await session.scalars(
                select(UserInterestProfile)
                .where(UserInterestProfile.user_id == user.id)
                .order_by(UserInterestProfile.confidence.desc(), UserInterestProfile.topic_key.asc())
            )
        ).all()
    )
    profile_runs = list(
        (
            await session.scalars(
                select(ProfileRun)
                .where(ProfileRun.user_id == user.id)
                .order_by(ProfileRun.created_at.desc())
            )
        ).all()
    )
    feedback_signals = await _feedback_signals(session, user.id)
    outcome_attributions = await _outcome_attributions(session, user.id)
    connected_providers = set(
        (
            await session.scalars(select(OAuthConnection.provider).where(OAuthConnection.user_id == user.id))
        ).all()
    )
    _, items, _ = await _cards_for_run(session, run)
    positive_drivers, negative_drivers = _driver_summaries(items)
    supply_quality_rollups = await _supply_quality_rollups(session, run)

    return RecommendationDebugSummary(
        runId=run.id,
        generatedAt=_timestamp_utc(run.created_at).isoformat(),
        rankingModel=run.model_name,
        contextHash=_context_hash(
            run=run,
            resolution=anchor_resolution,
            constraints=constraints,
            topics=topic_rows,
            items=items,
        ),
        shortlistSize=len(items),
        summary=_debug_summary_sentence(positive_drivers, negative_drivers),
        mapContext=_build_map_context(anchor_resolution),
        activeTopics=_topic_labels(topic_rows, muted=False),
        mutedTopics=_topic_labels(topic_rows, muted=True),
        activeTopicSources=_topic_source_summaries(
            topic_rows,
            _latest_profile_runs_by_provider(profile_runs),
            connected_providers,
        ),
        supplyQualityRollups=supply_quality_rollups,
        topSaveReasons=_feedback_reason_summaries(feedback_signals, action="save"),
        topConfirmedSaveReasons=_confirmed_save_reason_summaries(feedback_signals),
        topDismissReasons=_feedback_reason_summaries(feedback_signals, action="dismiss"),
        outcomeAttributions=outcome_attributions,
        topPositiveDrivers=positive_drivers,
        topNegativeDrivers=negative_drivers,
        venues=[
            RecommendationDebugVenue(
                rank=index + 1,
                venueId=item.venueId,
                venueName=item.venueName,
                score=item.score,
                scoreBand=item.scoreBand,
                scoreSummary=item.scoreSummary,
                topDrivers=_debug_top_drivers(item.scoreBreakdown),
            )
            for index, item in enumerate(items)
        ],
    )


async def get_recommendation_run_comparison(
    session: AsyncSession,
    user: User,
) -> RecommendationRunComparison:
    current_run = await refresh_recommendations_for_user(session, user)
    if current_run is None:
        return RecommendationRunComparison()

    recent_runs = await _latest_runs(session, user.id, limit=2)
    if len(recent_runs) < 2:
        return RecommendationRunComparison(
            currentRunId=current_run.id,
            currentGeneratedAt=_timestamp_utc(current_run.created_at).isoformat(),
            shortlistSize=0,
            summary="Pulse needs one more completed run before it can compare ranking changes.",
        )

    current_run = recent_runs[0]
    previous_run = recent_runs[1]
    anchor_resolution = await _user_anchor_resolution(session, user.id)
    constraints = await _user_constraints(session, user.id)
    topic_rows = list(
        (
            await session.scalars(
                select(UserInterestProfile)
                .where(UserInterestProfile.user_id == user.id)
                .order_by(UserInterestProfile.confidence.desc(), UserInterestProfile.topic_key.asc())
            )
        ).all()
    )
    _, current_items, _ = await _cards_for_run(session, current_run)
    _, previous_items, _ = await _cards_for_run(session, previous_run)
    new_entrants, dropped_venues, movers, steady_leaders = _compare_shortlists(current_items, previous_items)

    return RecommendationRunComparison(
        currentRunId=current_run.id,
        previousRunId=previous_run.id,
        currentGeneratedAt=_timestamp_utc(current_run.created_at).isoformat(),
        previousGeneratedAt=_timestamp_utc(previous_run.created_at).isoformat(),
        currentContextHash=_context_hash(
            run=current_run,
            resolution=anchor_resolution,
            constraints=constraints,
            topics=topic_rows,
            items=current_items,
        ),
        previousContextHash=_context_hash(
            run=previous_run,
            resolution=anchor_resolution,
            constraints=constraints,
            topics=topic_rows,
            items=previous_items,
        ),
        summary=_comparison_summary_sentence(
            new_entrants=new_entrants,
            dropped_venues=dropped_venues,
            movers=movers,
        ),
        shortlistSize=len(current_items),
        comparableVenueCount=len(set(_rank_lookup(current_items)).intersection(_rank_lookup(previous_items))),
        newEntrants=new_entrants,
        droppedVenues=dropped_venues,
        movers=movers,
        steadyLeaders=steady_leaders,
    )


async def get_archive(session: AsyncSession, user: User) -> ArchiveResponse:
    display_timezone = _display_timezone(user)
    latest_run = await refresh_recommendations_for_user(session, user)
    if latest_run is None:
        return ArchiveResponse(items=[], history=[], displayTimezone=display_timezone)

    _, items, _ = await _cards_for_run(session, latest_run)

    delivery_rows = (
        await session.scalars(
            select(DigestDelivery)
            .where(
                DigestDelivery.user_id == user.id,
                DigestDelivery.status == "sent",
            )
            .order_by(desc(DigestDelivery.created_at))
        )
    ).all()

    snapshots: list[ArchiveSnapshot] = []
    seen_run_ids: set[str] = set()

    for delivery in delivery_rows:
        if delivery.recommendation_run_id == latest_run.id:
            continue
        if delivery.recommendation_run_id in seen_run_ids:
            continue

        run = await session.get(RecommendationRun, delivery.recommendation_run_id)
        if run is None:
            continue

        _, historical_items, _ = await _cards_for_run(session, run)
        if not historical_items:
            continue

        kind = _archive_kind(delivery.provider)
        snapshots.append(
            ArchiveSnapshot(
                runId=run.id,
                kind=kind,
                title=_archive_title(kind),
                generatedAt=run.created_at.isoformat(),
                deliveredAt=delivery.created_at.isoformat(),
                items=historical_items,
            )
        )
        seen_run_ids.add(run.id)

    return ArchiveResponse(items=items, history=snapshots, displayTimezone=display_timezone)


def _price_label(min_price: float | None, max_price: float | None) -> str:
    if min_price is None and max_price is None:
        return "Price varies"
    if min_price is not None and max_price is not None and min_price == max_price:
        return f"${min_price:.0f}"
    if min_price is None:
        return f"Up to ${max_price:.0f}"
    if max_price is None:
        return f"From ${min_price:.0f}"
    return f"${min_price:.0f}-${max_price:.0f}"

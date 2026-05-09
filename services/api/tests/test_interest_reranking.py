from app.models.events import CanonicalEvent
from app.models.events import EventOccurrence
from app.models.profile import ProfileRun, UserInterestProfile
from app.models.events import Venue
from app.services.recommendations import (
    FeedbackSignals,
    _archive_kind,
    _archive_title,
    _candidate_score,
    _candidate_score_with_components,
    _deletable_run_ids,
    _derive_topic_keys,
    _feedback_adjustment,
    _feedback_reason_summaries,
    _occurrence_is_rankable,
    _parse_occurrence_start,
    _score_band,
    _score_breakdown_items,
    _select_ranked_venues,
    _stale_interest_provider_keys,
    _topic_source_summaries,
)
from datetime import UTC, datetime, timedelta


def test_muted_topic_scores_lower_than_matching_active_topic() -> None:
    profiles_by_key = {
        "underground_dance": UserInterestProfile(
            user_id="user-1",
            topic_key="underground_dance",
            label="Underground dance",
            confidence=0.94,
            boosted=False,
            muted=True,
        ),
        "gallery_nights": UserInterestProfile(
            user_id="user-1",
            topic_key="gallery_nights",
            label="Gallery nights",
            confidence=0.72,
            boosted=False,
            muted=False,
        ),
        "indie_live_music": UserInterestProfile(
            user_id="user-1",
            topic_key="indie_live_music",
            label="Indie live music",
            confidence=0.88,
            boosted=False,
            muted=False,
        ),
    }

    underground_score, _, underground_muted = _candidate_score(
        ["underground_dance"],
        profiles_by_key,
        source_confidence=0.93,
        transit_minutes=28,
        budget_fit=0.92,
    )
    mixed_score, _, mixed_muted = _candidate_score(
        ["underground_dance", "gallery_nights"],
        profiles_by_key,
        source_confidence=0.88,
        transit_minutes=30,
        budget_fit=0.72,
    )
    indie_score, indie_matched, _ = _candidate_score(
        ["indie_live_music"],
        profiles_by_key,
        source_confidence=0.83,
        transit_minutes=22,
        budget_fit=0.92,
    )

    assert underground_score < mixed_score < indie_score
    assert [topic.label for topic in underground_muted] == ["Underground dance"]
    assert [topic.label for topic in mixed_muted] == ["Underground dance"]
    assert [topic.label for topic in indie_matched] == ["Indie live music"]


def test_topic_source_summaries_show_spotify_ranking_influence() -> None:
    rows = [
        UserInterestProfile(
            user_id="user-1",
            topic_key="underground_dance",
            label="Underground dance",
            confidence=0.88,
            source_provider="spotify",
            boosted=False,
            muted=False,
        ),
        UserInterestProfile(
            user_id="user-1",
            topic_key="indie_live_music",
            label="Indie live music",
            confidence=0.74,
            source_provider="spotify",
            boosted=False,
            muted=False,
        ),
        UserInterestProfile(
            user_id="user-1",
            topic_key="gallery_nights",
            label="Gallery nights",
            confidence=0.64,
            source_provider="manual",
            boosted=False,
            muted=False,
        ),
        UserInterestProfile(
            user_id="user-1",
            topic_key="muted_theme",
            label="Muted theme",
            confidence=0.91,
            source_provider="spotify",
            boosted=False,
            muted=True,
        ),
    ]

    failed_run = ProfileRun(
        user_id="user-1",
        provider="spotify",
        model_name="pulse-spotify-provider-v1",
        status="failed",
        summary_json={"message": "Spotify connection expired. Reconnect Spotify and try again."},
    )
    failed_run.created_at = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)

    summaries = _topic_source_summaries(rows, {"spotify": failed_run}, {"spotify"})

    assert summaries[0].sourceProvider == "spotify"
    assert summaries[0].label == "Spotify"
    assert summaries[0].topicCount == 2
    assert summaries[0].averageConfidence == 0.81
    assert summaries[0].topTopics == ["Underground dance", "Indie live music"]
    assert summaries[0].latestRunStatus == "failed"
    assert summaries[0].latestRunAt == "2026-04-27T12:00:00+00:00"
    assert summaries[0].connected is True
    assert summaries[0].stale is True
    assert summaries[0].currentlyInfluencingRanking is False
    assert summaries[0].confidenceState == "degraded"
    assert (
        summaries[0].healthReason
        == "Latest Spotify sync failed: Spotify connection expired. Reconnect Spotify and try again."
    )
    assert "influencing=False" in (summaries[0].debugReason or "")
    assert summaries[1].sourceProvider == "manual"


def test_stale_spotify_interest_is_suppressed_while_manual_stays_active() -> None:
    profiles_by_key = {
        "underground_dance": UserInterestProfile(
            user_id="user-1",
            topic_key="underground_dance",
            label="Underground dance",
            confidence=0.92,
            source_provider="spotify",
            boosted=False,
            muted=False,
        ),
        "gallery_nights": UserInterestProfile(
            user_id="user-1",
            topic_key="gallery_nights",
            label="Gallery nights",
            confidence=0.72,
            source_provider="manual",
            boosted=False,
            muted=False,
        ),
    }

    healthy_spotify_score, healthy_spotify_topics, _ = _candidate_score(
        ["underground_dance"],
        profiles_by_key,
        source_confidence=0.84,
        transit_minutes=28,
        budget_fit=0.9,
    )
    stale_spotify_score, stale_spotify_topics, _ = _candidate_score(
        ["underground_dance"],
        profiles_by_key,
        source_confidence=0.84,
        transit_minutes=28,
        budget_fit=0.9,
        stale_provider_keys={"spotify"},
    )
    stale_manual_score, stale_manual_topics, _ = _candidate_score(
        ["gallery_nights"],
        profiles_by_key,
        source_confidence=0.84,
        transit_minutes=28,
        budget_fit=0.9,
        stale_provider_keys={"spotify"},
    )

    assert healthy_spotify_score > stale_spotify_score
    assert [topic.label for topic in healthy_spotify_topics] == ["Underground dance"]
    assert stale_spotify_topics == []
    assert stale_manual_score > stale_spotify_score
    assert [topic.label for topic in stale_manual_topics] == ["Gallery nights"]


def test_stale_spotify_adjustment_is_exposed_in_score_breakdown() -> None:
    profiles_by_key = {
        "underground_dance": UserInterestProfile(
            user_id="user-1",
            topic_key="underground_dance",
            label="Underground dance",
            confidence=0.92,
            source_provider="spotify",
            boosted=False,
            muted=False,
        )
    }

    _, matched_topics, muted_topics, components = _candidate_score_with_components(
        ["underground_dance"],
        profiles_by_key,
        source_confidence=0.84,
        transit_minutes=28,
        budget_fit=0.9,
        stale_provider_keys={"spotify"},
    )
    breakdown = _score_breakdown_items(
        components=components,
        matched_labels=[topic.label for topic in matched_topics],
        muted_labels=[topic.label for topic in muted_topics],
        feedback_adjustment=0.0,
        feedback_reason=None,
    )
    stale_items = [item for item in breakdown if item["key"] == "stale_provider_guard"]

    assert stale_items
    assert stale_items[0]["direction"] == "negative"
    assert stale_items[0]["contribution"] < 0
    assert "Latest Spotify sync failed" in stale_items[0]["detail"]
    assert "Underground dance" in stale_items[0]["detail"]


def test_manual_taste_stays_stronger_than_bounded_fresh_spotify() -> None:
    manual_profiles = {
        "gallery_nights": UserInterestProfile(
            user_id="user-1",
            topic_key="gallery_nights",
            label="Gallery nights",
            confidence=0.82,
            source_provider="manual",
            boosted=False,
            muted=False,
        )
    }
    spotify_profiles = {
        "gallery_nights": UserInterestProfile(
            user_id="user-1",
            topic_key="gallery_nights",
            label="Gallery nights",
            confidence=0.82,
            source_provider="spotify",
            boosted=False,
            muted=False,
        )
    }

    manual_score, _, _, manual_components = _candidate_score_with_components(
        ["gallery_nights"],
        manual_profiles,
        source_confidence=0.84,
        transit_minutes=24,
        budget_fit=0.9,
        category="gallery",
    )
    spotify_score, _, _, spotify_components = _candidate_score_with_components(
        ["gallery_nights"],
        spotify_profiles,
        source_confidence=0.84,
        transit_minutes=24,
        budget_fit=0.9,
        category="gallery",
    )

    assert manual_score > spotify_score
    assert manual_components.source_weight_adjustment == 0.0
    assert spotify_components.source_weight_adjustment < 0
    assert spotify_components.source_weight_labels == ["Spotify 0.78x"]


def test_source_weight_contribution_is_exposed_in_score_breakdown() -> None:
    profiles_by_key = {
        "underground_dance": UserInterestProfile(
            user_id="user-1",
            topic_key="underground_dance",
            label="Underground dance",
            confidence=0.92,
            source_provider="spotify",
            boosted=False,
            muted=False,
        )
    }

    _, matched_topics, muted_topics, components = _candidate_score_with_components(
        ["underground_dance"],
        profiles_by_key,
        source_confidence=0.84,
        transit_minutes=28,
        budget_fit=0.9,
        category="club",
    )
    breakdown = _score_breakdown_items(
        components=components,
        matched_labels=[topic.label for topic in matched_topics],
        muted_labels=[topic.label for topic in muted_topics],
        feedback_adjustment=0.0,
        feedback_reason=None,
    )
    source_weight_items = [item for item in breakdown if item["key"] == "taste_source_weight"]

    assert source_weight_items
    assert source_weight_items[0]["direction"] == "negative"
    assert source_weight_items[0]["contribution"] < 0
    assert "Spotify 0.78x" in source_weight_items[0]["detail"]


def test_feedback_and_planner_outcomes_can_outweigh_passive_source_weighting() -> None:
    profiles_by_key = {
        "underground_dance": UserInterestProfile(
            user_id="user-1",
            topic_key="underground_dance",
            label="Underground dance",
            confidence=0.92,
            source_provider="spotify",
            boosted=False,
            muted=False,
        )
    }
    venue = Venue(
        id="venue-1",
        name="Public Records",
        neighborhood="Gowanus",
        address="233 Butler St",
        city="Brooklyn",
        state="NY",
        latitude=40.6787,
        longitude=-73.9831,
    )
    feedback_signals = FeedbackSignals(
        saved_venues={"venue-1": 1.0},
        planner_attended_venues={"venue-1": 2.0},
    )

    _, _, _, components = _candidate_score_with_components(
        ["underground_dance"],
        profiles_by_key,
        source_confidence=0.84,
        transit_minutes=24,
        budget_fit=0.9,
    )
    feedback_adjustment, feedback_reason = _feedback_adjustment(
        ["underground_dance"],
        profiles_by_key,
        venue,
        feedback_signals,
        transit_minutes=24,
        budget_fit=0.9,
        source_confidence=0.84,
    )

    assert feedback_adjustment > abs(components.source_weight_adjustment)
    assert feedback_reason is not None
    assert feedback_reason["title"] == "Went before"


def test_stale_interest_provider_keys_only_marks_failed_spotify() -> None:
    spotify_failed = ProfileRun(user_id="user-1", provider="spotify", model_name="spotify", status="failed")
    manual_failed = ProfileRun(user_id="user-1", provider="manual", model_name="manual", status="failed")
    reddit_completed = ProfileRun(user_id="user-1", provider="reddit_export", model_name="reddit", status="completed")

    stale_keys = _stale_interest_provider_keys(
        {
            "spotify": spotify_failed,
            "manual": manual_failed,
            "reddit_export": reddit_completed,
        }
    )

    assert stale_keys == {"spotify"}


def test_score_band_thresholds_match_ranking_copy() -> None:
    assert _score_band(0.84) == "high"
    assert _score_band(0.64) == "medium"
    assert _score_band(0.41) == "low"


def test_topic_keys_can_be_derived_from_event_text() -> None:
    event = CanonicalEvent(
        source_id="source-1",
        source_event_key="event-1",
        title="Warehouse techno installation night",
        category="culture",
        summary="A visual-heavy art opening with late-night DJs.",
    )

    topic_keys = _derive_topic_keys(event, ["brooklyn", "gallery opening"])
    assert "underground_dance" in topic_keys
    assert "gallery_nights" in topic_keys


def test_topic_keys_cover_broader_cultural_themes() -> None:
    event = CanonicalEvent(
        source_id="source-1",
        source_event_key="event-2",
        title="Brooklyn vintage market and design pop-up",
        category="shopping",
        summary="A boutique-heavy collector fair with menswear racks and local design labels.",
    )

    topic_keys = _derive_topic_keys(event, ["popup market", "vintage", "collector"])
    assert "collector_marketplaces" in topic_keys
    assert "style_design_shopping" in topic_keys


def test_feedback_adjustment_boosts_saved_venue_and_topics() -> None:
    profiles_by_key = {
        "indie_live_music": UserInterestProfile(
            user_id="user-1",
            topic_key="indie_live_music",
            label="Indie live music",
            confidence=0.88,
            boosted=False,
            muted=False,
        )
    }
    venue = Venue(
        name="Mercury Lounge",
        neighborhood="Lower East Side",
        address="217 E Houston St, New York, NY",
        city="New York City",
        state="NY",
        latitude=40.7222,
        longitude=-73.9864,
    )
    venue.id = "venue-1"
    signals = FeedbackSignals(
        saved_venues={"venue-1": 1.0},
        saved_topics={"indie_live_music": 0.8},
    )

    adjustment, feedback_reason = _feedback_adjustment(
        ["indie_live_music"],
        profiles_by_key,
        venue,
        signals,
        transit_minutes=22,
        budget_fit=0.92,
        source_confidence=0.86,
    )

    assert adjustment > 0
    assert feedback_reason is not None
    assert feedback_reason["title"] == "Saved before"


def test_feedback_adjustment_penalizes_long_trip_when_too_far_reason_recurs() -> None:
    profiles_by_key = {
        "indie_live_music": UserInterestProfile(
            user_id="user-1",
            topic_key="indie_live_music",
            label="Indie live music",
            confidence=0.88,
            boosted=False,
            muted=False,
        )
    }
    venue = Venue(
        name="Elsewhere",
        neighborhood="Bushwick",
        address="599 Johnson Ave, Brooklyn, NY",
        city="New York City",
        state="NY",
        latitude=40.7065,
        longitude=-73.9235,
    )
    venue.id = "venue-2"
    signals = FeedbackSignals(
        dismissed_reasons={"too_far": 1.4},
        dismissed_reason_counts={"too_far": 2},
        reason_labels={"too_far": "Too far"},
    )

    adjustment, feedback_reason = _feedback_adjustment(
        ["indie_live_music"],
        profiles_by_key,
        venue,
        signals,
        transit_minutes=52,
        budget_fit=0.84,
        source_confidence=0.86,
    )

    assert adjustment < 0
    assert feedback_reason is not None
    assert feedback_reason["title"] == "Distance pattern"


def test_feedback_adjustment_boosts_budget_and_vibe_patterns() -> None:
    profiles_by_key = {
        "gallery_nights": UserInterestProfile(
            user_id="user-1",
            topic_key="gallery_nights",
            label="Gallery nights",
            confidence=0.84,
            boosted=False,
            muted=False,
        )
    }
    venue = Venue(
        name="Public Records",
        neighborhood="Gowanus",
        address="233 Butler St, Brooklyn, NY",
        city="New York City",
        state="NY",
        latitude=40.6799,
        longitude=-73.9839,
    )
    venue.id = "venue-3"
    signals = FeedbackSignals(
        saved_reasons={"good_price": 1.0, "right_vibe": 0.8},
        saved_reason_counts={"good_price": 1, "right_vibe": 1},
        reason_labels={"good_price": "Good price", "right_vibe": "Right vibe"},
    )

    adjustment, feedback_reason = _feedback_adjustment(
        ["gallery_nights"],
        profiles_by_key,
        venue,
        signals,
        transit_minutes=24,
        budget_fit=0.91,
        source_confidence=0.9,
    )

    assert adjustment > 0
    assert feedback_reason is not None
    assert feedback_reason["title"] in {"Budget pattern", "Taste pattern"}


def test_feedback_adjustment_boosts_completed_planner_outcomes() -> None:
    profiles_by_key = {
        "underground_dance": UserInterestProfile(
            user_id="user-1",
            topic_key="underground_dance",
            label="Underground dance",
            confidence=0.94,
            boosted=False,
            muted=False,
        )
    }
    venue = Venue(
        name="Elsewhere",
        neighborhood="Bushwick",
        address="599 Johnson Ave, Brooklyn, NY",
        city="New York City",
        state="NY",
        latitude=40.7063,
        longitude=-73.9232,
    )
    venue.id = "venue-4"
    signals = FeedbackSignals(
        planner_attended_venues={"venue-4": 1.1},
        planner_attended_topics={"underground_dance": 0.95},
    )

    adjustment, feedback_reason = _feedback_adjustment(
        ["underground_dance"],
        profiles_by_key,
        venue,
        signals,
        transit_minutes=26,
        budget_fit=0.9,
        source_confidence=0.88,
    )

    assert adjustment > 0
    assert feedback_reason is not None
    assert feedback_reason["title"] == "Went before"


def test_feedback_reason_summaries_sort_by_weight_and_preserve_labels() -> None:
    signals = FeedbackSignals(
        saved_reasons={"easy_to_get_to": 1.2, "good_price": 0.9},
        saved_reason_counts={"easy_to_get_to": 2, "good_price": 1},
        dismissed_reasons={"too_far": 1.4},
        dismissed_reason_counts={"too_far": 3},
        reason_labels={
            "easy_to_get_to": "Easy to get to",
            "good_price": "Good price",
            "too_far": "Too far",
        },
    )

    save_summaries = _feedback_reason_summaries(signals, action="save")
    dismiss_summaries = _feedback_reason_summaries(signals, action="dismiss")

    assert [item.key for item in save_summaries] == ["easy_to_get_to", "good_price"]
    assert save_summaries[0].label == "Easy to get to"
    assert dismiss_summaries[0].key == "too_far"
    assert dismiss_summaries[0].count == 3


def test_candidate_score_strong_match_beats_generic_event() -> None:
    profiles_by_key = {
        "collector_marketplaces": UserInterestProfile(
            user_id="user-1",
            topic_key="collector_marketplaces",
            label="Collector marketplaces",
            confidence=0.95,
            boosted=False,
            muted=False,
        ),
        "style_design_shopping": UserInterestProfile(
            user_id="user-1",
            topic_key="style_design_shopping",
            label="Style / design shopping",
            confidence=0.82,
            boosted=False,
            muted=False,
        ),
    }

    matched_score, matched_topics, _ = _candidate_score(
        ["collector_marketplaces", "style_design_shopping"],
        profiles_by_key,
        source_confidence=0.76,
        transit_minutes=30,
        budget_fit=0.9,
    )
    generic_score, generic_topics, _ = _candidate_score(
        [],
        profiles_by_key,
        source_confidence=0.92,
        transit_minutes=20,
        budget_fit=0.92,
    )

    assert matched_score > generic_score
    assert [topic.label for topic in matched_topics] == ["Collector marketplaces", "Style / design shopping"]
    assert generic_topics == []


def test_candidate_score_category_affinity_lifts_market_events_for_collector_taste() -> None:
    profiles_by_key = {
        "collector_marketplaces": UserInterestProfile(
            user_id="user-1",
            topic_key="collector_marketplaces",
            label="Collector marketplaces",
            confidence=0.95,
            boosted=False,
            muted=False,
        ),
        "style_design_shopping": UserInterestProfile(
            user_id="user-1",
            topic_key="style_design_shopping",
            label="Style / design shopping",
            confidence=0.82,
            boosted=False,
            muted=False,
        ),
    }

    market_score, _, _ = _candidate_score(
        [],
        profiles_by_key,
        source_confidence=0.78,
        transit_minutes=28,
        budget_fit=0.9,
        category="market",
        tags=["vintage", "design fair"],
    )
    generic_score, _, _ = _candidate_score(
        [],
        profiles_by_key,
        source_confidence=0.9,
        transit_minutes=24,
        budget_fit=0.92,
        category="culture",
        tags=["community"],
    )

    assert market_score > generic_score


def test_candidate_score_category_affinity_lifts_talks_for_intellectual_scene() -> None:
    profiles_by_key = {
        "student_intellectual_scene": UserInterestProfile(
            user_id="user-1",
            topic_key="student_intellectual_scene",
            label="Campus / intellectual scene",
            confidence=0.82,
            boosted=False,
            muted=False,
        ),
        "ambitious_professional_scene": UserInterestProfile(
            user_id="user-1",
            topic_key="ambitious_professional_scene",
            label="Ambitious professional scene",
            confidence=0.7,
            boosted=False,
            muted=False,
        ),
    }

    talk_score, _, _ = _candidate_score(
        [],
        profiles_by_key,
        source_confidence=0.74,
        transit_minutes=34,
        budget_fit=0.86,
        category="talk",
        tags=["book discussion", "lecture"],
    )
    nightlife_score, _, _ = _candidate_score(
        [],
        profiles_by_key,
        source_confidence=0.9,
        transit_minutes=26,
        budget_fit=0.9,
        category="live music",
        tags=["dj set"],
    )

    assert talk_score > nightlife_score


def test_select_ranked_venues_keeps_broader_theme_match_in_top_mix() -> None:
    profiles_by_key = {
        "underground_dance": UserInterestProfile(
            user_id="user-1",
            topic_key="underground_dance",
            label="Underground dance",
            confidence=0.94,
            boosted=False,
            muted=False,
        ),
        "collector_marketplaces": UserInterestProfile(
            user_id="user-1",
            topic_key="collector_marketplaces",
            label="Collector marketplaces",
            confidence=0.95,
            boosted=False,
            muted=False,
        ),
    }

    nightlife_entries = [
        [{"score": 0.92, "category": "live music", "topic_keys": ["underground_dance"], "dominant_topic_key": "underground_dance"}],
        [{"score": 0.9, "category": "live music", "topic_keys": ["underground_dance"], "dominant_topic_key": "underground_dance"}],
        [{"score": 0.88, "category": "live music", "topic_keys": ["underground_dance"], "dominant_topic_key": "underground_dance"}],
    ]
    market_entry = [
        {"score": 0.85, "category": "market", "topic_keys": ["collector_marketplaces"], "dominant_topic_key": "collector_marketplaces"}
    ]

    selected = _select_ranked_venues(
        nightlife_entries + [market_entry],
        profiles_by_key,
        limit=3,
    )

    selected_dominant_topics = [entries[0]["dominant_topic_key"] for entries in selected]
    assert "collector_marketplaces" in selected_dominant_topics


def test_feedback_adjustment_penalizes_dismissed_patterns() -> None:
    profiles_by_key = {
        "underground_dance": UserInterestProfile(
            user_id="user-1",
            topic_key="underground_dance",
            label="Underground dance",
            confidence=0.94,
            boosted=False,
            muted=False,
        )
    }
    venue = Venue(
        name="Elsewhere",
        neighborhood="Bushwick",
        address="599 Johnson Ave, Brooklyn, NY",
        city="New York City",
        state="NY",
        latitude=40.7063,
        longitude=-73.9232,
    )
    venue.id = "venue-2"
    signals = FeedbackSignals(
        dismissed_topics={"underground_dance": 1.1},
        dismissed_neighborhoods={"bushwick": 0.9},
    )

    adjustment, feedback_reason = _feedback_adjustment(
        ["underground_dance"],
        profiles_by_key,
        venue,
        signals,
        transit_minutes=41,
        budget_fit=0.86,
        source_confidence=0.82,
    )

    assert adjustment < 0
    assert feedback_reason is not None
    assert feedback_reason["title"] == "Dismiss pattern"


def test_deletable_run_ids_preserve_digest_backed_history() -> None:
    run_ids = ["run-live", "run-preview", "run-scheduled"]
    protected_run_ids = {"run-preview", "run-scheduled"}

    assert _deletable_run_ids(run_ids, protected_run_ids) == ["run-live"]


def test_archive_kind_and_title_match_delivery_provider() -> None:
    assert _archive_kind(None) == "live"
    assert _archive_title("live") == "Current shortlist"
    assert _archive_kind("resend-preview") == "preview"
    assert _archive_title("preview") == "Preview send"
    assert _archive_kind("resend-scheduled") == "scheduled"
    assert _archive_title("scheduled") == "Weekly digest"


def test_parse_occurrence_start_handles_iso_datetimes() -> None:
    parsed = _parse_occurrence_start("2026-04-28T00:30:00+00:00")

    assert parsed == datetime(2026, 4, 28, 0, 30, tzinfo=UTC)


def test_occurrence_is_rankable_filters_past_and_far_future_events() -> None:
    now = datetime(2026, 4, 23, 16, 0, tzinfo=UTC)

    current_occurrence = EventOccurrence(
        event_id="event-1",
        venue_id="venue-1",
        starts_at="2026-04-23T20:00:00+00:00",
    )
    stale_occurrence = EventOccurrence(
        event_id="event-2",
        venue_id="venue-1",
        starts_at=(now - timedelta(hours=3)).isoformat(),
    )
    far_future_occurrence = EventOccurrence(
        event_id="event-3",
        venue_id="venue-1",
        starts_at=(now + timedelta(days=75)).isoformat(),
    )

    assert _occurrence_is_rankable(current_occurrence, now=now) is True
    assert _occurrence_is_rankable(stale_occurrence, now=now) is False
    assert _occurrence_is_rankable(far_future_occurrence, now=now) is False

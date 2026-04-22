from app.models.profile import UserInterestProfile
from app.services.recommendations import _candidate_score, _score_band


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


def test_score_band_thresholds_match_ranking_copy() -> None:
    assert _score_band(0.84) == "high"
    assert _score_band(0.64) == "medium"
    assert _score_band(0.41) == "low"

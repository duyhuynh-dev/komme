from app.services.ranking import combine_score


def test_combine_score_respects_weighted_cap() -> None:
    score = combine_score(
        fit_score=0.95,
        profile_confidence=0.9,
        event_quality=0.8,
        source_confidence=0.85,
        novelty=0.5,
    )
    assert score == 0.87


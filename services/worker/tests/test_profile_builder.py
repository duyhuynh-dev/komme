import pytest

from app.models.contracts import InterestEvidence
from app.services.profile_builder import build_interest_profile


@pytest.mark.asyncio
async def test_profile_builder_extracts_topics_from_evidence() -> None:
    profile = await build_interest_profile(
        [
            InterestEvidence(
                subreddit="aves",
                activity_type="comment",
                text="Warehouse techno room recs in Brooklyn",
            ),
            InterestEvidence(
                subreddit="indieheads",
                activity_type="saved",
                text="Looking for intimate indie gigs",
            ),
        ]
    )

    keys = {topic.key for topic in profile.topics}
    assert "underground_dance" in keys
    assert "indie_live_music" in keys

from __future__ import annotations

import logging

import inngest

from app.core.config import get_settings
from app.models.contracts import InterestEvidence
from app.services.pipeline import run_recommendation_pipeline
from app.services.supply_sync import run_daily_supply_sync

settings = get_settings()
inngest_client = inngest.Inngest(app_id=settings.inngest_app_id, logger=logging.getLogger("pulse-worker"))


@inngest_client.create_function(
    fn_id="pulse-daily-supply-ingestion",
    trigger=inngest.TriggerCron(cron="TZ=America/New_York 0 4 * * *"),
)
async def daily_supply_ingestion(_: inngest.Context) -> dict[str, str]:
    result = await run_daily_supply_sync()
    return {key: str(value) for key, value in result.items()}


@inngest_client.create_function(
    fn_id="pulse-weekly-recommendations",
    trigger=inngest.TriggerCron(cron="TZ=America/New_York 0 9 * * 2"),
)
async def weekly_recommendations(_: inngest.Context) -> dict:
    evidence = [
        InterestEvidence(subreddit="aves", activity_type="comment", text="Need a darker techno room in Brooklyn"),
        InterestEvidence(subreddit="indieheads", activity_type="saved", text="Small room indie show picks in NYC"),
    ]
    ranked = await run_recommendation_pipeline(evidence)
    return ranked.model_dump(mode="json")


@inngest_client.create_function(
    fn_id="pulse-reddit-profile-sync",
    trigger=inngest.TriggerEvent(event="pulse/reddit.connected"),
)
async def reddit_profile_sync(_: inngest.Context) -> dict:
    evidence = [
        InterestEvidence(subreddit="aves", activity_type="saved", text="Warehouse lineup shortlist"),
        InterestEvidence(subreddit="brooklyn", activity_type="comment", text="Any good art-forward dance spaces?"),
    ]
    ranked = await run_recommendation_pipeline(evidence)
    return {
        "status": "profile_synced",
        "top_venue": ranked.items[0].venue_name if ranked.items else None,
    }

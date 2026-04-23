from app.taste.contracts import NormalizedRedditActivity
from app.taste.providers.base import ActivityProvider


async def fetch_normalized_activity(provider: ActivityProvider, source_key: str) -> NormalizedRedditActivity:
    return await provider.fetch(source_key)

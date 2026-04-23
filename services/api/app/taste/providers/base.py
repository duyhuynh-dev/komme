from typing import Protocol

from app.taste.contracts import NormalizedRedditActivity


class ActivityProvider(Protocol):
    source_name: str

    async def fetch(self, source_key: str) -> NormalizedRedditActivity:
        ...

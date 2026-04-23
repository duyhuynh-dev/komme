from app.taste.contracts import NormalizedRedditActivity


class RedditExportProvider:
    source_name = "reddit_export"

    async def fetch(self, source_key: str) -> NormalizedRedditActivity:
        raise NotImplementedError("Reddit export provider will be implemented after the public username spike.")

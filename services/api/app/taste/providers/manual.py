from app.taste.contracts import NormalizedRedditActivity


class ManualThemeProvider:
    source_name = "manual"

    async def fetch(self, source_key: str) -> NormalizedRedditActivity:
        raise NotImplementedError("Manual theme provider will be implemented after the Reddit feasibility spike.")

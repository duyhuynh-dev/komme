from urllib.parse import urlencode

from app.core.config import get_settings


def build_reddit_authorize_url(state: str) -> str:
    settings = get_settings()
    if not settings.reddit_client_id:
        raise ValueError("Reddit client ID is not configured.")

    query = urlencode(
        {
            "client_id": settings.reddit_client_id,
            "response_type": "code",
            "state": state,
            "redirect_uri": settings.reddit_redirect_uri,
            "duration": "permanent",
            "scope": "identity history mysubreddits",
        }
    )
    return f"https://www.reddit.com/api/v1/authorize?{query}"


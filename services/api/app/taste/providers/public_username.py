from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote

import httpx

from app.core.config import Settings, get_settings
from app.taste.cache import FileActivityCache
from app.taste.contracts import (
    NormalizedRedditActivity,
    RecentComment,
    RecentSubmission,
    SubredditActivitySummary,
)
from app.taste.errors import (
    BlockedByRedditError,
    NoPublicActivityError,
    ProviderUnavailableError,
    RateLimitedError,
    UsernameNotFoundError,
)

SleepFn = Callable[[float], Awaitable[None]]


class PublicUsernameProvider:
    source_name = "public_username"

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
        cache: FileActivityCache | None = None,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self._external_client = client
        self.cache = cache or FileActivityCache(
            Path(self.settings.reddit_public_cache_dir),
            ttl_hours=self.settings.reddit_public_cache_ttl_hours,
        )
        self.sleep = sleep

    async def fetch(self, source_key: str) -> NormalizedRedditActivity:
        username = source_key.strip().lstrip("u/").lstrip("/").split("/")[-1]
        if not username:
            raise UsernameNotFoundError("A Reddit username is required.")

        cached = self.cache.load(self.source_name, username)
        if cached is not None:
            return cached

        activity = await self._fetch_uncached(username)
        self.cache.store(self.source_name, username, activity)
        return activity

    async def _fetch_uncached(self, username: str) -> NormalizedRedditActivity:
        async with self._client_context() as client:
            comments_payload, submissions_payload = await asyncio.gather(
                self._request_listing(client, username, "comments"),
                self._request_listing(client, username, "submitted"),
            )

        comments = [self._parse_comment(child["data"]) for child in comments_payload["data"]["children"]]
        submissions = [self._parse_submission(child["data"]) for child in submissions_payload["data"]["children"]]

        if not comments and not submissions:
            raise NoPublicActivityError(f"u/{username} has no recent public Reddit activity.")

        subreddit_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"comment_count": 0, "submission_count": 0, "total_karma": 0}
        )
        for comment in comments:
            bucket = subreddit_counts[comment.subreddit]
            bucket["comment_count"] += 1
            bucket["total_karma"] += comment.score

        for submission in submissions:
            bucket = subreddit_counts[submission.subreddit]
            bucket["submission_count"] += 1
            bucket["total_karma"] += submission.score

        subreddit_activity = [
            SubredditActivitySummary(subreddit=subreddit, **counts)
            for subreddit, counts in sorted(
                subreddit_counts.items(),
                key=lambda item: (
                    -(item[1]["comment_count"] + item[1]["submission_count"]),
                    -item[1]["total_karma"],
                    item[0].lower(),
                ),
            )
        ]

        return NormalizedRedditActivity(
            source="public_username",
            source_key=username,
            username=username,
            fetched_at=datetime.now(UTC),
            total_comments=len(comments),
            total_submissions=len(submissions),
            subreddit_activity=subreddit_activity,
            recent_comments=comments,
            recent_submissions=submissions,
        )

    async def _request_listing(
        self,
        client: httpx.AsyncClient,
        username: str,
        kind: str,
        attempts: int = 4,
    ) -> dict[str, Any]:
        encoded_username = quote(username, safe="")
        url = f"https://www.reddit.com/user/{encoded_username}/{kind}.json?limit=100&raw_json=1"
        delay_seconds = 1.0

        for attempt in range(1, attempts + 1):
            try:
                response = await client.get(url, headers=self._headers())
            except httpx.TimeoutException as error:
                if attempt == attempts:
                    raise ProviderUnavailableError("Reddit timed out while fetching public activity.") from error
                await self.sleep(delay_seconds)
                delay_seconds *= 2
                continue
            except httpx.HTTPError as error:
                raise ProviderUnavailableError("Unable to reach Reddit public activity endpoints.") from error

            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError as error:
                    raise ProviderUnavailableError("Reddit returned malformed JSON.") from error
                if "data" not in payload or "children" not in payload["data"]:
                    raise ProviderUnavailableError("Reddit returned an unexpected payload shape.")
                return payload

            if response.status_code == 404:
                raise UsernameNotFoundError(f"u/{username} could not be found.")

            if response.status_code == 403:
                raise BlockedByRedditError(
                    "Reddit blocked the public profile request. This lookup path may not be available from this environment."
                )

            if response.status_code == 429:
                retry_after_header = response.headers.get("Retry-After")
                retry_after = float(retry_after_header) if retry_after_header else delay_seconds
                if attempt == attempts:
                    raise RateLimitedError("Reddit rate-limited the public profile request.")
                await self.sleep(retry_after)
                delay_seconds *= 2
                continue

            if 500 <= response.status_code < 600 and attempt < attempts:
                await self.sleep(delay_seconds)
                delay_seconds *= 2
                continue

            raise ProviderUnavailableError(
                f"Reddit returned an unexpected status code ({response.status_code}) for {kind}."
            )

        raise ProviderUnavailableError("Reddit public activity lookup did not complete.")

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.settings.reddit_public_user_agent,
            "Accept": "application/json",
        }

    def _parse_comment(self, data: dict[str, Any]) -> RecentComment:
        permalink = data.get("permalink")
        return RecentComment(
            subreddit=data.get("subreddit") or "unknown",
            body=data.get("body") or "",
            score=int(data.get("score") or 0),
            created_at=_utc_datetime(data.get("created_utc")),
            post_title=data.get("link_title"),
            permalink=f"https://www.reddit.com{permalink}" if permalink else None,
        )

    def _parse_submission(self, data: dict[str, Any]) -> RecentSubmission:
        permalink = data.get("permalink")
        return RecentSubmission(
            subreddit=data.get("subreddit") or "unknown",
            title=data.get("title") or "",
            body=data.get("selftext") or None,
            score=int(data.get("score") or 0),
            created_at=_utc_datetime(data.get("created_utc")),
            permalink=f"https://www.reddit.com{permalink}" if permalink else None,
        )

    def _client_context(self) -> httpx.AsyncClient | "_ManagedAsyncClient":
        if self._external_client is not None:
            return _ManagedAsyncClient(self._external_client)

        return httpx.AsyncClient(timeout=self.settings.reddit_public_timeout_seconds, follow_redirects=True)


class _ManagedAsyncClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self.client

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _utc_datetime(created_utc: Any) -> datetime:
    timestamp = float(created_utc or 0)
    return datetime.fromtimestamp(timestamp, tz=UTC)

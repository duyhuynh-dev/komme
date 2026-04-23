from collections import defaultdict
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.taste.errors import NoPublicActivityError, RateLimitedError, UsernameNotFoundError
from app.taste.providers.public_username import PublicUsernameProvider


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        reddit_public_cache_dir=str(tmp_path / "reddit-cache"),
        reddit_public_cache_ttl_hours=24,
        reddit_public_timeout_seconds=5.0,
        reddit_public_user_agent="PulseTests/0.1 (by /u/tester)",
    )


def _listing(children: list[dict]) -> dict:
    return {"data": {"children": [{"data": child} for child in children]}}


@pytest.mark.asyncio
async def test_public_username_provider_normalizes_comments_and_submissions(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "comments.json" in str(request.url):
            return httpx.Response(
                200,
                json=_listing(
                    [
                        {
                            "subreddit": "aves",
                            "body": "Loved that warehouse techno set.",
                            "score": 12,
                            "created_utc": 1713877200,
                            "link_title": "Best NYC rave venues?",
                            "permalink": "/r/aves/comments/abc123/comment/zzz999/",
                        },
                        {
                            "subreddit": "indieheads",
                            "body": "Mercury Lounge always sounds good.",
                            "score": 4,
                            "created_utc": 1713880800,
                            "link_title": "Best intimate venues",
                            "permalink": "/r/indieheads/comments/def456/comment/yyy888/",
                        },
                    ]
                ),
            )

        return httpx.Response(
            200,
            json=_listing(
                [
                    {
                        "subreddit": "aves",
                        "title": "Looking for a good Bushwick afters",
                        "selftext": "Something warehouse-y but not too expensive.",
                        "score": 9,
                        "created_utc": 1713884400,
                        "permalink": "/r/aves/comments/ghi789/looking_for_a_good_bushwick_afters/",
                    }
                ]
            ),
        )

    provider = PublicUsernameProvider(
        settings=_settings(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    activity = await provider.fetch("ExampleUser")

    assert activity.username == "ExampleUser"
    assert activity.total_comments == 2
    assert activity.total_submissions == 1
    assert [summary.subreddit for summary in activity.subreddit_activity] == ["aves", "indieheads"]
    assert activity.subreddit_activity[0].comment_count == 1
    assert activity.subreddit_activity[0].submission_count == 1
    assert activity.recent_comments[0].post_title == "Best NYC rave venues?"
    assert activity.recent_comments[0].permalink == "https://www.reddit.com/r/aves/comments/abc123/comment/zzz999/"
    assert activity.recent_submissions[0].title == "Looking for a good Bushwick afters"


@pytest.mark.asyncio
async def test_public_username_provider_uses_cache(tmp_path: Path) -> None:
    hit_counter = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        hit_counter["count"] += 1
        if "comments.json" in str(request.url):
            return httpx.Response(
                200,
                json=_listing(
                    [
                        {
                            "subreddit": "aves",
                            "body": "Warehouse all night.",
                            "score": 5,
                            "created_utc": 1713877200,
                            "link_title": "Rave thread",
                            "permalink": "/r/aves/comments/abc123/comment/zzz999/",
                        }
                    ]
                ),
            )
        return httpx.Response(200, json=_listing([]))

    provider = PublicUsernameProvider(
        settings=_settings(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    first = await provider.fetch("cacheme")
    second = await provider.fetch("cacheme")

    assert first.total_comments == second.total_comments == 1
    assert hit_counter["count"] == 2


@pytest.mark.asyncio
async def test_public_username_provider_raises_not_found(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    provider = PublicUsernameProvider(
        settings=_settings(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(UsernameNotFoundError):
        await provider.fetch("missing-user")


@pytest.mark.asyncio
async def test_public_username_provider_raises_no_public_activity(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_listing([]))

    provider = PublicUsernameProvider(
        settings=_settings(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(NoPublicActivityError):
        await provider.fetch("quiet-user")


@pytest.mark.asyncio
async def test_public_username_provider_retries_rate_limit_then_succeeds(tmp_path: Path) -> None:
    counts: dict[str, int] = defaultdict(int)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def handler(request: httpx.Request) -> httpx.Response:
        key = "comments" if "comments.json" in str(request.url) else "submitted"
        counts[key] += 1

        if key == "comments" and counts[key] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})

        if key == "comments":
            return httpx.Response(
                200,
                json=_listing(
                    [
                        {
                            "subreddit": "aves",
                            "body": "Retry worked.",
                            "score": 2,
                            "created_utc": 1713877200,
                            "link_title": "Afters",
                            "permalink": "/r/aves/comments/abc123/comment/zzz999/",
                        }
                    ]
                ),
            )

        return httpx.Response(200, json=_listing([]))

    provider = PublicUsernameProvider(
        settings=_settings(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        sleep=fake_sleep,
    )

    activity = await provider.fetch("retry-user")

    assert activity.total_comments == 1
    assert counts["comments"] == 2
    assert sleeps == [0.0]


@pytest.mark.asyncio
async def test_public_username_provider_raises_after_exhausting_rate_limit(tmp_path: Path) -> None:
    async def fake_sleep(_: float) -> None:
        return None

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"})

    provider = PublicUsernameProvider(
        settings=_settings(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        sleep=fake_sleep,
    )

    with pytest.raises(RateLimitedError):
        await provider.fetch("blocked-user")

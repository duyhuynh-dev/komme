import pytest
from datetime import UTC, datetime

from app.services import digest_sync


@pytest.mark.asyncio
async def test_trigger_scheduled_digest_delivery_posts_to_api_with_shared_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, int | str]:
            return {
                "status": "completed",
                "processedUsers": 2,
                "sent": 1,
                "skipped": 1,
                "failed": 0,
            }

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, headers: dict[str, str], params: dict[str, str] | None = None) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            return FakeResponse()

    class FakeSettings:
        api_base_url = "http://127.0.0.1:8000"
        internal_ingest_secret = "pulse-secret"

    monkeypatch.setattr(digest_sync, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(digest_sync.httpx, "AsyncClient", FakeClient)

    response = await digest_sync.trigger_scheduled_digest_delivery()

    assert captured["url"] == "http://127.0.0.1:8000/v1/internal/digests/send-weekly"
    assert captured["headers"] == {"x-pulse-ingest-secret": "pulse-secret"}
    assert captured["params"] is None
    assert response["sent"] == 1
    assert response["processedUsers"] == 2


@pytest.mark.asyncio
async def test_trigger_scheduled_digest_delivery_forwards_dry_run_and_time_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    scheduled_at = datetime(2026, 4, 21, 13, 5, tzinfo=UTC)

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, int | str | bool | list[str]]:
            return {
                "status": "completed",
                "dryRun": True,
                "wouldSend": 1,
                "recipients": ["duy@example.com"],
            }

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, headers: dict[str, str], params: dict[str, str] | None = None) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            return FakeResponse()

    class FakeSettings:
        api_base_url = "http://127.0.0.1:8000"
        internal_ingest_secret = "pulse-secret"

    monkeypatch.setattr(digest_sync, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(digest_sync.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())

    response = await digest_sync.trigger_scheduled_digest_delivery(
        dry_run=True,
        now_override=scheduled_at,
    )

    assert captured["url"] == "http://127.0.0.1:8000/v1/internal/digests/send-weekly"
    assert captured["headers"] == {"x-pulse-ingest-secret": "pulse-secret"}
    assert captured["params"] == {
        "dry_run": "true",
        "now_override": scheduled_at.isoformat(),
    }
    assert response["dryRun"] is True
    assert response["wouldSend"] == 1

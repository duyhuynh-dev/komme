import pytest

from app.services import worker_sync


@pytest.mark.asyncio
async def test_trigger_worker_supply_sync_posts_to_worker_with_shared_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, int | str]:
            return {
                "candidate_count": 6,
                "accepted": 4,
                "sources_created": 1,
                "venues_created": 2,
                "events_created": 3,
                "occurrences_created": 4,
                "status": "synced",
            }

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, headers: dict[str, str]) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    class FakeSettings:
        worker_base_url = "http://127.0.0.1:8001"
        internal_ingest_secret = "pulse-secret"

    monkeypatch.setattr(worker_sync, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(worker_sync.httpx, "AsyncClient", FakeClient)

    response = await worker_sync.trigger_worker_supply_sync()

    assert captured["url"] == "http://127.0.0.1:8001/v1/supply/sync"
    assert captured["headers"] == {"x-pulse-ingest-secret": "pulse-secret"}
    assert response.candidateCount == 6
    assert response.accepted == 4
    assert response.eventsCreated == 3

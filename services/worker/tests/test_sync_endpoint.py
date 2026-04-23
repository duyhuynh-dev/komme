from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_sync_supply_endpoint_requires_shared_secret(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_INGEST_SECRET", "pulse-secret")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post("/v1/supply/sync")

    assert response.status_code == 401
    get_settings.cache_clear()


def test_sync_supply_endpoint_runs_daily_sync(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_INGEST_SECRET", "pulse-secret")
    get_settings.cache_clear()

    async def fake_run_daily_supply_sync() -> dict[str, int | str]:
        return {"status": "synced", "candidate_count": 5, "accepted": 4}

    monkeypatch.setattr("app.main.run_daily_supply_sync", fake_run_daily_supply_sync)

    with TestClient(app) as client:
        response = client.post(
            "/v1/supply/sync",
            headers={"x-pulse-ingest-secret": "pulse-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "synced", "candidate_count": 5, "accepted": 4}
    get_settings.cache_clear()


def test_run_scheduled_digests_endpoint_requires_shared_secret(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_INGEST_SECRET", "pulse-secret")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post("/v1/digests/run-scheduled")

    assert response.status_code == 401
    get_settings.cache_clear()


def test_run_scheduled_digests_endpoint_forwards_smoke_test_params(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_INGEST_SECRET", "pulse-secret")
    get_settings.cache_clear()
    captured: dict[str, object] = {}

    async def fake_trigger_scheduled_digest_delivery(*, dry_run: bool = False, now_override: datetime | None = None) -> dict:
        captured["dry_run"] = dry_run
        captured["now_override"] = now_override
        return {
            "status": "completed",
            "dryRun": dry_run,
            "wouldSend": 1,
            "recipients": ["duy@example.com"],
        }

    monkeypatch.setattr("app.main.trigger_scheduled_digest_delivery", fake_trigger_scheduled_digest_delivery)

    with TestClient(app) as client:
        response = client.post(
            "/v1/digests/run-scheduled?dry_run=true&now_override=2026-04-21T13:05:00%2B00:00",
            headers={"x-pulse-ingest-secret": "pulse-secret"},
        )

    assert response.status_code == 200
    assert captured["dry_run"] is True
    assert captured["now_override"] == datetime(2026, 4, 21, 13, 5, tzinfo=UTC)
    assert response.json() == {
        "status": "completed",
        "dryRun": True,
        "wouldSend": 1,
        "recipients": ["duy@example.com"],
    }
    get_settings.cache_clear()

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

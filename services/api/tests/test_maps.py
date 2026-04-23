import pytest

from app.api.routes import maps_token


@pytest.mark.asyncio
async def test_maps_token_returns_disabled_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_missing_credentials() -> str:
        raise ValueError("Apple Maps credentials are not configured.")

    monkeypatch.setattr("app.api.routes.build_mapkit_token", raise_missing_credentials)
    response = await maps_token()

    assert response.enabled is False
    assert response.token is None


@pytest.mark.asyncio
async def test_maps_token_returns_enabled_when_token_can_be_built(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.build_mapkit_token", lambda: "signed-token")
    response = await maps_token()

    assert response.enabled is True
    assert response.token == "signed-token"

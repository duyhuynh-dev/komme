from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import taste_spotify_sync
from app.db.base import Base
from app.models.profile import ProfileRun, UserInterestProfile
from app.models.user import OAuthConnection, User
from app.taste.errors import ProviderUnavailableError
from app.taste.profile_contracts import TasteProfile, TasteTheme, ThemeEvidence, ThemeEvidenceSnippet


class SuccessfulSpotifyProvider:
    async def build_profile(self, session, connection) -> TasteProfile:
        return TasteProfile(
            source="spotify",
            source_key="spotify-user-1",
            username="Duy",
            themes=[
                TasteTheme(
                    id="underground_dance",
                    label="Underground dance",
                    confidence=86,
                    confidence_label="Clear",
                    evidence=ThemeEvidence(
                        top_examples=[
                            ThemeEvidenceSnippet(
                                type="spotify_artist",
                                snippet="Top artist: Warehouse Hero",
                            )
                        ],
                        provider_notes=["Built from Spotify listening history."],
                    ),
                )
            ],
        )


class FailingSpotifyProvider:
    async def build_profile(self, session, connection) -> TasteProfile:
        raise ProviderUnavailableError("Spotify connection expired. Reconnect Spotify and try again.")


@pytest.mark.asyncio
async def test_spotify_sync_applies_profile_and_refreshes_recommendations(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    refresh_calls: list[tuple[str, bool, str, str]] = []

    async def fake_refresh(session_arg, user_arg, *, force: bool, provider: str, model_name: str):
        refresh_calls.append((user_arg.id, force, provider, model_name))

    monkeypatch.setattr("app.api.routes.SpotifyProvider", SuccessfulSpotifyProvider)
    monkeypatch.setattr("app.taste.profile_service.refresh_recommendations_for_user", fake_refresh)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="spotify-sync@example.com")
        session.add(user)
        await session.flush()
        session.add(OAuthConnection(user_id=user.id, provider="spotify", access_token_encrypted="token"))
        await session.flush()

        response = await taste_spotify_sync(session=session, identity=SimpleNamespace(user=user))

        profile_runs = list((await session.scalars(select(ProfileRun))).all())
        interest_rows = list((await session.scalars(select(UserInterestProfile))).all())
        assert response.source == "spotify"
        assert len(profile_runs) == 1
        assert profile_runs[0].provider == "spotify"
        assert profile_runs[0].status == "completed"
        assert len(interest_rows) == 1
        assert interest_rows[0].source_provider == "spotify"
        assert refresh_calls == [(user.id, True, "spotify", "pulse-spotify-provider-v1")]

    await engine.dispose()


@pytest.mark.asyncio
async def test_spotify_sync_records_failed_profile_run(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr("app.api.routes.SpotifyProvider", FailingSpotifyProvider)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="spotify-sync-failure@example.com")
        session.add(user)
        await session.flush()
        session.add(OAuthConnection(user_id=user.id, provider="spotify", access_token_encrypted="token"))
        await session.flush()

        with pytest.raises(HTTPException) as error:
            await taste_spotify_sync(session=session, identity=SimpleNamespace(user=user))

        profile_runs = list((await session.scalars(select(ProfileRun))).all())
        assert error.value.status_code == 503
        assert len(profile_runs) == 1
        assert profile_runs[0].provider == "spotify"
        assert profile_runs[0].status == "failed"
        assert profile_runs[0].summary_json == {
            "errorCode": "provider_unavailable",
            "message": "Spotify connection expired. Reconnect Spotify and try again.",
            "retryable": True,
        }

    await engine.dispose()

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.profile import ProfileRun, UserInterestProfile
from app.models.user import OAuthConnection, User
from app.schemas.auth import AuthViewerResponse
from app.services.profile import get_spotify_taste_health


@pytest.mark.asyncio
async def test_spotify_taste_health_marks_failed_provider_as_not_influencing() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="spotify-health@example.com")
        session.add(user)
        await session.flush()
        session.add(OAuthConnection(user_id=user.id, provider="spotify", access_token_encrypted="token"))
        session.add(
            UserInterestProfile(
                user_id=user.id,
                topic_key="underground_dance",
                label="Underground dance",
                confidence=0.92,
                source_provider="spotify",
                source_signals_json=["Top artist: Warehouse Hero"],
                boosted=False,
                muted=False,
            )
        )
        failed_run = ProfileRun(
            user_id=user.id,
            provider="spotify",
            model_name="pulse-spotify-provider-v1",
            status="failed",
            summary_json={"message": "Spotify connection expired. Reconnect Spotify and try again."},
        )
        failed_run.created_at = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)
        session.add(failed_run)
        await session.flush()

        health = await get_spotify_taste_health(session, user)

        assert health.connected is True
        assert health.provider == "spotify"
        assert health.latestRunStatus == "failed"
        assert health.latestRunAt == "2026-04-27T12:00:00+00:00"
        assert health.stale is True
        assert health.currentlyInfluencingRanking is False
        assert health.confidenceState == "degraded"
        assert (
            health.healthReason
            == "Latest Spotify sync failed: Spotify connection expired. Reconnect Spotify and try again."
        )
        assert "active_topic_count=1" in (health.debugReason or "")

    await engine.dispose()


@pytest.mark.asyncio
async def test_spotify_taste_health_marks_completed_provider_as_influencing() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="spotify-active@example.com")
        session.add(user)
        await session.flush()
        session.add(OAuthConnection(user_id=user.id, provider="spotify", access_token_encrypted="token"))
        session.add(
            UserInterestProfile(
                user_id=user.id,
                topic_key="indie_live_music",
                label="Indie live music",
                confidence=0.84,
                source_provider="spotify",
                source_signals_json=["Top artist: Indie Star"],
                boosted=False,
                muted=False,
            )
        )
        completed_run = ProfileRun(
            user_id=user.id,
            provider="spotify",
            model_name="pulse-spotify-provider-v1",
            status="completed",
            summary_json={},
        )
        completed_run.created_at = datetime(2026, 4, 27, 13, 0, tzinfo=UTC)
        session.add(completed_run)
        await session.flush()

        health = await get_spotify_taste_health(session, user)

        assert health.connected is True
        assert health.stale is False
        assert health.currentlyInfluencingRanking is True
        assert health.confidenceState == "healthy"
        assert health.healthReason == "Spotify taste is currently influencing ranking through 1 active themes."
        payload = AuthViewerResponse(
            userId=user.id,
            email=user.email,
            isAuthenticated=True,
            isDemo=False,
            redditConnected=False,
            spotifyConnected=True,
            spotifyTasteHealth=health,
            connectedSources=[health],
        ).model_dump()
        assert payload["connectedSources"][0]["provider"] == "spotify"
        assert payload["connectedSources"][0]["currentlyInfluencingRanking"] is True

    await engine.dispose()


@pytest.mark.asyncio
async def test_spotify_taste_health_handles_unconnected_users() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="no-spotify@example.com")
        session.add(user)
        await session.flush()

        health = await get_spotify_taste_health(session, user)

        assert health.connected is False
        assert health.stale is False
        assert health.currentlyInfluencingRanking is False
        assert health.confidenceState == "disconnected"
        assert health.healthReason == "Spotify is not connected."

    await engine.dispose()


@pytest.mark.asyncio
async def test_spotify_taste_health_marks_connected_without_active_topics_as_not_influencing() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(email="spotify-inactive@example.com")
        session.add(user)
        await session.flush()
        session.add(OAuthConnection(user_id=user.id, provider="spotify", access_token_encrypted="token"))
        completed_run = ProfileRun(
            user_id=user.id,
            provider="spotify",
            model_name="pulse-spotify-provider-v1",
            status="completed",
            summary_json={},
        )
        completed_run.created_at = datetime(2026, 4, 27, 14, 0, tzinfo=UTC)
        session.add(completed_run)
        await session.flush()

        health = await get_spotify_taste_health(session, user)

        assert health.connected is True
        assert health.stale is False
        assert health.currentlyInfluencingRanking is False
        assert health.confidenceState == "inactive"
        assert (
            health.healthReason
            == "Latest Spotify sync completed, but no active Spotify themes are influencing ranking."
        )

    await engine.dispose()

import pytest

from app.models.profile import ProfileRun, UserInterestProfile
from app.models.user import User
from app.taste.errors import InvalidManualSelectionError, ProviderUnavailableError, UnknownThemeError
from app.taste.profile_service import apply_taste_profile, record_taste_profile_failure
from app.taste.providers.manual import ManualThemeProvider


@pytest.mark.asyncio
async def test_manual_provider_builds_emerging_themes_with_evidence() -> None:
    provider = ManualThemeProvider()

    profile = await provider.build_profile(["indie_live_music", "gallery_nights", "indie_live_music"])

    assert profile.source == "manual"
    assert [theme.id for theme in profile.themes] == ["indie_live_music", "gallery_nights"]
    assert all(theme.confidence == 48 for theme in profile.themes)
    assert all(theme.confidence_label == "Emerging" for theme in profile.themes)
    assert profile.themes[0].evidence.provider_notes == ["Selected manually during onboarding."]
    assert profile.themes[0].evidence.top_examples[0].type == "manual"


@pytest.mark.asyncio
async def test_manual_provider_rejects_empty_selection() -> None:
    provider = ManualThemeProvider()

    with pytest.raises(InvalidManualSelectionError):
        await provider.build_profile([])


@pytest.mark.asyncio
async def test_manual_provider_rejects_unknown_theme() -> None:
    provider = ManualThemeProvider()

    with pytest.raises(UnknownThemeError):
        await provider.build_profile(["unknown_theme"])


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.executed: list[object] = []
        self.flushed = False

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def execute(self, statement) -> None:
        self.executed.append(statement)

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
async def test_apply_taste_profile_persists_profile_run_and_interest_rows(monkeypatch) -> None:
    provider = ManualThemeProvider()
    profile = await provider.build_profile(["underground_dance", "late_night_food"])
    session = FakeSession()
    user = User(id="user-1", email="duy@example.com")
    refresh_calls: list[tuple[str, bool, str, str]] = []

    async def fake_refresh(session_arg, user_arg, *, force: bool, provider: str, model_name: str):
        refresh_calls.append((user_arg.id, force, provider, model_name))

    monkeypatch.setattr("app.taste.profile_service.refresh_recommendations_for_user", fake_refresh)

    applied = await apply_taste_profile(session, user, profile)

    assert applied.source == "manual"
    assert session.flushed is True
    interest_rows = [obj for obj in session.added if isinstance(obj, UserInterestProfile)]
    profile_runs = [obj for obj in session.added if isinstance(obj, ProfileRun)]
    assert len(interest_rows) == 2
    assert len(profile_runs) == 1
    assert interest_rows[0].confidence == 0.48
    assert interest_rows[0].source_provider == "manual"
    assert "Selected manually during onboarding." in interest_rows[0].source_signals_json
    assert refresh_calls == [("user-1", True, "manual", "pulse-manual-provider-v1")]


@pytest.mark.asyncio
async def test_record_taste_profile_failure_persists_provider_health() -> None:
    session = FakeSession()
    user = User(id="user-1", email="duy@example.com")
    error = ProviderUnavailableError("Spotify connection expired. Reconnect Spotify and try again.")

    await record_taste_profile_failure(session, user, provider="spotify", error=error)

    profile_runs = [obj for obj in session.added if isinstance(obj, ProfileRun)]
    assert session.flushed is True
    assert len(profile_runs) == 1
    assert profile_runs[0].provider == "spotify"
    assert profile_runs[0].status == "failed"
    assert profile_runs[0].summary_json == {
        "errorCode": "provider_unavailable",
        "message": "Spotify connection expired. Reconnect Spotify and try again.",
        "retryable": True,
    }

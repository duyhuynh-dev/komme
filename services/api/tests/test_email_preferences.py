import pytest

from app.models.user import EmailPreference, User
from app.schemas.profile import EmailPreferencePayload
from app.services.profile import get_email_preferences, update_email_preferences


class FakeSession:
    def __init__(self, preference: EmailPreference | None = None) -> None:
        self.preference = preference
        self.committed = False
        self.flushed = False
        self.added: list[object] = []

    async def scalar(self, _query) -> EmailPreference | None:
        return self.preference

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if isinstance(obj, EmailPreference):
            self.preference = obj

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_get_email_preferences_creates_default_record_when_missing() -> None:
    session = FakeSession()
    user = User(id="user-1", email="duy@example.com", timezone="America/New_York")

    response = await get_email_preferences(session, user)

    assert response.weeklyDigestEnabled is True
    assert response.digestDay == "Tuesday"
    assert response.digestTimeLocal == "09:00"
    assert response.timezone == "America/New_York"
    assert session.preference is not None
    assert session.flushed is True
    assert session.committed is True


@pytest.mark.asyncio
async def test_update_email_preferences_persists_schedule_and_timezone() -> None:
    preference = EmailPreference(user_id="user-1", weekly_digest_enabled=True, digest_day="Tuesday", digest_time_local="09:00")
    session = FakeSession(preference=preference)
    user = User(id="user-1", email="duy@example.com", timezone="America/New_York")

    response = await update_email_preferences(
        session,
        user,
        EmailPreferencePayload(
            weeklyDigestEnabled=False,
            digestDay="Friday",
            digestTimeLocal="18:30",
            timezone="America/Los_Angeles",
        ),
    )

    assert response.weeklyDigestEnabled is False
    assert response.digestDay == "Friday"
    assert response.digestTimeLocal == "18:30"
    assert response.timezone == "America/Los_Angeles"
    assert preference.weekly_digest_enabled is False
    assert preference.digest_day == "Friday"
    assert preference.digest_time_local == "18:30"
    assert user.timezone == "America/Los_Angeles"
    assert session.committed is True

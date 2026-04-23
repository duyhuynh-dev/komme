from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import UserInterestOverride, UserInterestProfile
from app.models.user import EmailPreference, User
from app.schemas.profile import EmailPreferencePayload, EmailPreferenceResponse, InterestTopic
from app.services.recommendations import refresh_recommendations_for_user


async def list_interests(session: AsyncSession, user: User) -> list[InterestTopic]:
    rows = await session.scalars(
        select(UserInterestProfile)
        .where(UserInterestProfile.user_id == user.id)
        .order_by(UserInterestProfile.confidence.desc())
    )
    return [
        InterestTopic(
            id=row.topic_key,
            label=row.label,
            confidence=row.confidence,
            sourceSignals=row.source_signals_json or [],
            boosted=row.boosted,
            muted=row.muted,
        )
        for row in rows
    ]


async def update_interests(
    session: AsyncSession,
    user: User,
    topics: list[InterestTopic],
) -> list[InterestTopic]:
    existing = {
        row.topic_key: row
        for row in (
            await session.scalars(select(UserInterestProfile).where(UserInterestProfile.user_id == user.id))
        )
    }

    for topic in topics:
        row = existing.get(topic.id)
        if row is None:
            row = UserInterestProfile(
                user_id=user.id,
                topic_key=topic.id,
                label=topic.label,
                confidence=topic.confidence,
                source_signals_json=topic.sourceSignals,
                boosted=topic.boosted,
                muted=topic.muted,
            )
            session.add(row)
            continue

        row.label = topic.label
        row.confidence = topic.confidence
        row.source_signals_json = topic.sourceSignals
        row.boosted = topic.boosted
        row.muted = topic.muted

    await session.execute(delete(UserInterestOverride).where(UserInterestOverride.user_id == user.id))
    for topic in topics:
        if topic.muted or topic.boosted:
            session.add(
                UserInterestOverride(
                    user_id=user.id,
                    topic_key=topic.id,
                    action="boost" if topic.boosted else "mute",
                )
            )

    await session.flush()
    await refresh_recommendations_for_user(session, user, force=True)
    return await list_interests(session, user)


def _serialize_email_preference(preference: EmailPreference, user: User) -> EmailPreferenceResponse:
    return EmailPreferenceResponse(
        weeklyDigestEnabled=preference.weekly_digest_enabled,
        digestDay=preference.digest_day,
        digestTimeLocal=preference.digest_time_local,
        timezone=user.timezone or "America/New_York",
    )


async def _ensure_email_preference(session: AsyncSession, user: User) -> tuple[EmailPreference, bool]:
    preference = await session.scalar(select(EmailPreference).where(EmailPreference.user_id == user.id))
    if preference is not None:
        return preference, False

    preference = EmailPreference(
        user_id=user.id,
        weekly_digest_enabled=True,
        digest_day="Tuesday",
        digest_time_local="09:00",
    )
    session.add(preference)
    await session.flush()
    return preference, True


async def get_email_preferences(session: AsyncSession, user: User) -> EmailPreferenceResponse:
    preference, created = await _ensure_email_preference(session, user)
    if created:
        await session.commit()
    return _serialize_email_preference(preference, user)


async def update_email_preferences(
    session: AsyncSession,
    user: User,
    payload: EmailPreferencePayload,
) -> EmailPreferenceResponse:
    preference, _ = await _ensure_email_preference(session, user)
    preference.weekly_digest_enabled = payload.weeklyDigestEnabled
    preference.digest_day = payload.digestDay
    preference.digest_time_local = payload.digestTimeLocal
    if payload.timezone:
        user.timezone = payload.timezone
    await session.commit()
    return _serialize_email_preference(preference, user)

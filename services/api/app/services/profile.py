from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import UserInterestOverride, UserInterestProfile
from app.models.user import User
from app.schemas.profile import InterestTopic
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

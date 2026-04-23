from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import ProfileRun, UserInterestOverride, UserInterestProfile
from app.models.user import User
from app.services.recommendations import refresh_recommendations_for_user
from app.taste.profile_contracts import TasteProfile, TasteTheme


def theme_signal_strings(theme: TasteTheme) -> list[str]:
    signals: list[str] = []

    signals.extend(theme.evidence.provider_notes)
    signals.extend(f"r/{item.key}" for item in theme.evidence.matched_subreddits[:3])
    signals.extend(item.key for item in theme.evidence.matched_keywords[:3])
    signals.extend(example.snippet for example in theme.evidence.top_examples[:2])

    seen: set[str] = set()
    ordered: list[str] = []
    for signal in signals:
        normalized = signal.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered[:6]


async def apply_taste_profile(
    session: AsyncSession,
    user: User,
    profile: TasteProfile,
) -> TasteProfile:
    await session.execute(delete(UserInterestOverride).where(UserInterestOverride.user_id == user.id))
    await session.execute(delete(UserInterestProfile).where(UserInterestProfile.user_id == user.id))

    session.add(
        ProfileRun(
            user_id=user.id,
            provider=profile.source,
            model_name=f"pulse-{profile.source}-provider-v1",
            status="completed",
            summary_json=profile.model_dump(mode="json"),
        )
    )

    for theme in profile.themes:
        session.add(
            UserInterestProfile(
                user_id=user.id,
                topic_key=theme.id,
                label=theme.label,
                confidence=max(0.0, min(1.0, theme.confidence / 100)),
                source_signals_json=theme_signal_strings(theme),
                boosted=False,
                muted=False,
            )
        )

    await session.flush()
    await refresh_recommendations_for_user(
        session,
        user,
        force=True,
        provider=profile.source,
        model_name=f"pulse-{profile.source}-provider-v1",
    )
    return profile

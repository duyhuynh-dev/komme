from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import ProfileRun, UserInterestProfile
from app.models.user import OAuthConnection, User
from app.schemas.auth import ConnectedSourceHealth


def provider_label(provider: str) -> str:
    labels = {
        "spotify": "Spotify",
        "manual": "Manual",
        "reddit": "Reddit",
        "reddit_export": "Reddit export",
        "mock": "Demo seed",
        "feedback": "Recent feedback",
        "unknown": "Unknown",
    }
    return labels.get(provider, provider.replace("_", " ").title())


def build_connected_source_health(
    *,
    provider: str,
    connected: bool,
    latest_run: ProfileRun | None,
    active_topic_count: int,
) -> ConnectedSourceHealth:
    label = provider_label(provider)
    stale = latest_run is not None and latest_run.status != "completed"
    influencing = connected and active_topic_count > 0 and not stale

    if not connected:
        confidence_state = "disconnected"
        user_reason = f"{label} is not connected."
    elif stale:
        confidence_state = "degraded"
        summary = latest_run.summary_json or {}
        message = summary.get("message")
        user_reason = (
            f"Latest {label} sync failed: {message}"
            if isinstance(message, str) and message
            else f"Latest {label} sync failed."
        )
    elif latest_run is None:
        confidence_state = "inactive" if active_topic_count == 0 else "unknown"
        user_reason = (
            f"{label} is connected, but its taste has not been applied to ranking yet."
            if active_topic_count == 0
            else f"{label} taste exists, but Pulse has no recent provider sync status."
        )
    elif latest_run.status == "completed" and active_topic_count > 0:
        confidence_state = "healthy"
        user_reason = f"{label} taste is currently influencing ranking through {active_topic_count} active themes."
    else:
        confidence_state = "inactive"
        user_reason = f"Latest {label} sync completed, but no active {label} themes are influencing ranking."

    status = latest_run.status if latest_run else "none"
    debug_reason = (
        f"{provider}: connected={connected}, latest_run_status={status}, "
        f"active_topic_count={active_topic_count}, stale={stale}, influencing={influencing}."
    )

    return ConnectedSourceHealth(
        provider=provider,
        connected=connected,
        latestRunStatus=latest_run.status if latest_run else None,
        latestRunAt=latest_run.created_at.isoformat() if latest_run else None,
        stale=stale,
        currentlyInfluencingRanking=influencing,
        confidenceState=confidence_state,
        healthReason=user_reason,
        debugReason=debug_reason,
    )


async def get_connected_source_health(
    session: AsyncSession,
    user: User,
    *,
    provider: str,
) -> ConnectedSourceHealth:
    connection = await session.scalar(
        select(OAuthConnection).where(
            OAuthConnection.user_id == user.id,
            OAuthConnection.provider == provider,
        )
    )
    latest_run = await session.scalar(
        select(ProfileRun)
        .where(ProfileRun.user_id == user.id, ProfileRun.provider == provider)
        .order_by(ProfileRun.created_at.desc())
        .limit(1)
    )
    active_topic_count = (
        await session.scalar(
            select(func.count(UserInterestProfile.id))
            .select_from(UserInterestProfile)
            .where(
                UserInterestProfile.user_id == user.id,
                UserInterestProfile.source_provider == provider,
                UserInterestProfile.muted.is_(False),
            )
        )
        or 0
    )

    return build_connected_source_health(
        provider=provider,
        connected=connection is not None,
        latest_run=latest_run,
        active_topic_count=active_topic_count,
    )

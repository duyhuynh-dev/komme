from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user import User


async def get_or_create_user(
    session: AsyncSession,
    email: str | None = None,
) -> User:
    settings = get_settings()
    email = email or settings.default_user_email
    user = await session.scalar(select(User).where(User.email == email))
    if user:
        return user

    user = User(email=email, display_name="Pulse Beta User")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

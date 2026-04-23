from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user import EmailPreference, User


@dataclass
class ResolvedUser:
    user: User
    is_authenticated: bool
    is_demo: bool


async def get_or_create_user(
    session: AsyncSession,
    email: str | None = None,
    display_name: str | None = None,
) -> User:
    settings = get_settings()
    email = email or settings.default_user_email
    user = await session.scalar(select(User).where(User.email == email))
    if user:
        return user

    user = User(email=email, display_name=display_name or "Pulse Beta User")
    session.add(user)
    await session.flush()
    session.add(
        EmailPreference(
            user_id=user.id,
            weekly_digest_enabled=True,
            digest_day="Tuesday",
            digest_time_local="09:00",
        )
    )
    await session.commit()
    await session.refresh(user)
    return user


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return None
    return value


async def fetch_supabase_user(access_token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase server-side auth is not configured.",
        )

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {access_token}",
            },
        )

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase session is invalid or expired.",
        )

    return response.json()


async def resolve_user(
    session: AsyncSession,
    authorization: str | None = None,
    x_pulse_user_email: str | None = None,
) -> ResolvedUser:
    access_token = extract_bearer_token(authorization)
    if access_token:
        auth_user = await fetch_supabase_user(access_token)
        email = auth_user.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Supabase session is missing an email claim.",
            )

        user = await get_or_create_user(
            session,
            email=email,
            display_name=auth_user.get("email") or auth_user.get("phone"),
        )
        return ResolvedUser(user=user, is_authenticated=True, is_demo=False)

    if x_pulse_user_email:
        user = await get_or_create_user(session, email=x_pulse_user_email)
        return ResolvedUser(user=user, is_authenticated=True, is_demo=False)

    user = await get_or_create_user(session)
    return ResolvedUser(user=user, is_authenticated=False, is_demo=True)


async def require_authenticated_user(
    session: AsyncSession,
    authorization: str | None = None,
    x_pulse_user_email: str | None = None,
) -> ResolvedUser:
    resolved = await resolve_user(session, authorization, x_pulse_user_email)
    if resolved.is_authenticated:
        return resolved

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required for this action.",
    )


def build_oauth_state(email: str, secret: str, expires_in_seconds: int = 600) -> str:
    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "sub": email,
            "purpose": "reddit-connect",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )


def parse_oauth_state(state_token: str, secret: str) -> str:
    try:
        payload = jwt.decode(state_token, secret, algorithms=["HS256"])
    except ExpiredSignatureError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state has expired.",
        ) from error
    except InvalidTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state is invalid.",
        ) from error

    if payload.get("purpose") != "reddit-connect" or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state is invalid.",
        )

    return str(payload["sub"])

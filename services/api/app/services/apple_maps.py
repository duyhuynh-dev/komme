from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings


def build_mapkit_token() -> str:
    settings = get_settings()
    if not (
        settings.apple_maps_team_id
        and settings.apple_maps_key_id
        and settings.apple_maps_private_key
    ):
        raise ValueError("Apple Maps credentials are not configured.")

    now = datetime.now(tz=UTC)
    payload = {
        "iss": settings.apple_maps_team_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.apple_maps_web_token_ttl_seconds)).timestamp()),
        "origin": settings.apple_maps_origin,
    }
    headers = {
        "kid": settings.apple_maps_key_id,
        "typ": "JWT",
    }
    private_key = settings.apple_maps_private_key.replace("\\n", "\n")
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)

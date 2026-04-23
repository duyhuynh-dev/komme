from __future__ import annotations

from datetime import datetime

import httpx

from app.core.config import get_settings


async def trigger_scheduled_digest_delivery(
    *,
    dry_run: bool = False,
    now_override: datetime | None = None,
) -> dict:
    settings = get_settings()
    if not settings.api_base_url:
        return {"status": "skipped", "reason": "missing_api_base_url", "sent": 0}

    headers: dict[str, str] = {}
    if settings.internal_ingest_secret:
        headers["x-pulse-ingest-secret"] = settings.internal_ingest_secret
    params: dict[str, str] = {}
    if dry_run:
        params["dry_run"] = "true"
    if now_override is not None:
        params["now_override"] = now_override.isoformat()

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{settings.api_base_url}/v1/internal/digests/send-weekly",
            headers=headers,
            params=params or None,
        )
        response.raise_for_status()
        payload = response.json()

    payload["status"] = payload.get("status", "completed")
    return payload

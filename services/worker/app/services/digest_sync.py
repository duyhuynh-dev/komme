from __future__ import annotations

import httpx

from app.core.config import get_settings


async def trigger_scheduled_digest_delivery() -> dict:
    settings = get_settings()
    if not settings.api_base_url:
        return {"status": "skipped", "reason": "missing_api_base_url", "sent": 0}

    headers: dict[str, str] = {}
    if settings.internal_ingest_secret:
        headers["x-pulse-ingest-secret"] = settings.internal_ingest_secret

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{settings.api_base_url}/v1/internal/digests/send-weekly",
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    payload["status"] = payload.get("status", "completed")
    return payload

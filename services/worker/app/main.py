import logging
import os
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, status
import inngest.fast_api
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.jobs.workflows import daily_supply_ingestion, inngest_client, reddit_profile_sync, weekly_recommendations
from app.core.config import get_settings
from app.services.digest_sync import trigger_scheduled_digest_delivery
from app.services.supply_sync import run_daily_supply_sync

settings = get_settings()
openapi_url = None if settings.env == "production" else "/openapi.json"
docs_url = None if settings.env == "production" else "/docs"
redoc_url = None if settings.env == "production" else "/redoc"
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)
logger = logging.getLogger("pulse-worker")

if settings.env == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)


async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    if settings.env == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.add_middleware(BaseHTTPMiddleware, dispatch=add_security_headers)

if os.getenv("INNGEST_SIGNING_KEY"):
    inngest.fast_api.serve(
        app,
        inngest_client,
        [daily_supply_ingestion, weekly_recommendations, reddit_profile_sync],
    )
else:
    logger.warning("INNGEST_SIGNING_KEY is missing; starting worker without Inngest serve routes.")


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def verify_sync_secret(x_pulse_ingest_secret: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if settings.internal_ingest_secret and x_pulse_ingest_secret != settings.internal_ingest_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ingest secret.")


@app.post("/v1/supply/sync")
async def sync_supply(_: None = Depends(verify_sync_secret)) -> dict:
    return await run_daily_supply_sync()


@app.post("/v1/digests/run-scheduled")
async def run_scheduled_digests(
    dry_run: bool = False,
    now_override: datetime | None = None,
    _: None = Depends(verify_sync_secret),
) -> dict:
    return await trigger_scheduled_digest_delivery(
        dry_run=dry_run,
        now_override=now_override,
    )

import logging
import os

from fastapi import Depends, FastAPI, Header, HTTPException, status
import inngest.fast_api

from app.jobs.workflows import daily_supply_ingestion, inngest_client, reddit_profile_sync, weekly_recommendations
from app.core.config import get_settings
from app.services.supply_sync import run_daily_supply_sync

app = FastAPI(title="Pulse Worker", version="0.1.0")
logger = logging.getLogger("pulse-worker")

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

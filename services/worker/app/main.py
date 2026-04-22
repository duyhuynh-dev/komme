from fastapi import FastAPI
import inngest.fast_api

from app.jobs.workflows import daily_supply_ingestion, inngest_client, reddit_profile_sync, weekly_recommendations

app = FastAPI(title="Pulse Worker", version="0.1.0")
inngest.fast_api.serve(
    app,
    inngest_client,
    [daily_supply_ingestion, weekly_recommendations, reddit_profile_sync],
)


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


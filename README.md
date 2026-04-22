# Pulse MVP

Pulse is a map-first, personalized event discovery MVP for New York City. The product combines:

- `Next.js` for the consumer web experience
- `FastAPI` for APIs and backend integrations
- `Inngest + PydanticAI` for controlled agentic workflows
- `Apple MapKit JS` and `Apple Maps Server API` for the map stack

## Workspace

- `apps/web`: Next.js application
- `services/api`: FastAPI application and Alembic migrations
- `services/worker`: Inngest jobs, AI tasks, and ingestion/ranking logic

## Local setup

1. Install `uv`.
2. If `pnpm` is not already installed, enable it with `corepack`.
3. Copy `.env.example` values into service-specific `.env` files.
4. Install web dependencies from the repo root with `pnpm install`.
5. Install Python dependencies with:

```bash
corepack prepare pnpm@10.10.0 --activate
pnpm install
cd services/api && uv sync
cd ../worker && uv sync
```

## Run locally

```bash
pnpm dev
```

Run the Python services in separate terminals:

```bash
cd services/api && uv run uvicorn app.main:app --reload --port 8000
cd services/worker && uv run python -m app.main
```

## Validation

```bash
pnpm --filter @pulse/web build
cd services/api && .venv/bin/pytest
cd ../worker && .venv/bin/pytest
```

## Notes

- The implementation uses coarse user anchors by default. Exact browser location is session-only.
- Gemini is wrapped behind a provider abstraction to make a later Anthropic migration low-risk.
- Travel time in MVP is heuristic, not route API based.

# Komme

Komme is a map-first NYC event discovery and night-planning app. It turns live event supply into a personal shortlist, explains why each recommendation ranked, and builds a simple 2-3 stop plan users can actually follow.

Live app:

- Landing page: [https://komme.xyz](https://komme.xyz)
- Product app: [https://komme.xyz/app](https://komme.xyz/app)
- API health: [https://api.komme.xyz/healthz](https://api.komme.xyz/healthz)
- Worker health: [https://worker.komme.xyz/healthz](https://worker.komme.xyz/healthz)

## What Komme Does

- Finds real NYC events from venue calendars and ticketing/event APIs.
- Ranks them around location, timing, budget, taste, feedback, and source trust.
- Shows where recommendations came from instead of hiding provenance.
- Lets users steer the map with simple intent, Spotify taste, manual signals, saves, hides, and click behavior.
- Builds a compact planner route with roles like pregame, main event, backup, and late option.
- Keeps ops/debug views for ranking movement, source health, supply trust, feedback attribution, and planner sessions.

Komme is currently scoped to New York City.

## Product Shape

Komme has three user-facing layers:

- **Landing**: explains the product clearly at `/`.
- **Map app**: interactive recommendation map at `/app`.
- **Planner**: turns the current shortlist into a usable night route.

The product intentionally avoids generic list browsing. The goal is to help someone answer: “What should I actually do tonight?”

## Architecture

- `apps/web`: Next.js frontend, MapLibre map, landing page, planner UI, profile/settings surfaces.
- `services/api`: FastAPI app, auth/session handling, recommendation logic, ranking diagnostics, digest endpoints, Alembic migrations.
- `services/worker`: ingestion connectors, scheduled jobs, Inngest workflows, supply sync.
- `deploy/ec2`: production Docker Compose stack for API, worker, and Caddy.
- `docs`: systems notes and deployment guides.

Production currently uses:

- Vercel for the web frontend.
- EC2 + Docker Compose + Caddy for API and worker.
- Supabase Postgres for persistence.
- Inngest Cloud for scheduled/background workflows.
- Resend for email digests.

## Data Sources

Komme supports a mixed supply model:

- Curated NYC venue calendars.
- Ticketmaster Discovery API.
- SeatGeek API.
- Optional NYC Open Data / NYC events feed.

The ingestion layer normalizes candidates before they reach recommendation logic. Every event should preserve source/ticket links when available so users can verify and act.

## Local Setup

Requirements:

- Node.js with Corepack enabled.
- `pnpm`.
- `uv` for Python environments.
- Supabase/Postgres connection if running the full backend locally.

Install dependencies:

```bash
corepack prepare pnpm@10.10.0 --activate
pnpm install

cd services/api
uv sync

cd ../worker
uv sync
```

Copy environment values:

```bash
cp .env.example .env
```

For local development, the key defaults are:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
WORKER_BASE_URL=http://localhost:8001
```

Optional provider keys unlock live integrations:

```env
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
TICKETMASTER_API_KEY=
SEATGEEK_CLIENT_ID=
SEATGEEK_CLIENT_SECRET=
NYC_EVENTS_API_URL=
RESEND_API_KEY=
INNGEST_SIGNING_KEY=
```

Never commit real secrets.

## Run Locally

Run the web app:

```bash
pnpm dev
```

Run the API:

```bash
cd services/api
uv run uvicorn app.main:app --reload --port 8000
```

Run the worker:

```bash
cd services/worker
uv run uvicorn app.main:app --reload --port 8001
```

Useful local URLs:

- Web: [http://localhost:3000](http://localhost:3000)
- App: [http://localhost:3000/app](http://localhost:3000/app)
- API health: [http://localhost:8000/healthz](http://localhost:8000/healthz)
- Worker health: [http://localhost:8001/healthz](http://localhost:8001/healthz)

## Validation

Run focused checks when changing one area. Full checks:

```bash
corepack pnpm --filter @pulse/web build
uv run --project services/api pytest
uv run --project services/worker pytest
```

Common targeted checks:

```bash
uv run --project services/api pytest services/api/tests/test_recommendations.py
uv run --project services/api pytest services/api/tests/test_digest.py
uv run --project services/worker pytest services/worker/tests/test_supply_sync.py
corepack pnpm --filter @pulse/web test:planner
```

The package names still use the original internal `pulse` naming in a few places. Public-facing product copy is Komme.

## Supply Sync

Trigger supply ingestion manually:

```bash
curl -X POST https://api.komme.xyz/v1/supply/sync | jq
```

Expected output includes candidate counts, accepted counts, source counts, and rejected reasons. Example fields:

- `candidateCount`
- `realEventCount`
- `ticketUrlCount`
- `sourceCounts`
- `rejectedCounts`
- `fallbackUsed`
- `status`

If the worker is unavailable, check:

```bash
curl https://worker.komme.xyz/healthz
docker compose --env-file deploy/ec2/.env.ec2 -f deploy/ec2/docker-compose.yml logs --tail=120 worker
```

## Deployment

Web changes deploy through Vercel after pushing to `main`.

Important Vercel production environment variable:

```env
NEXT_PUBLIC_API_URL=https://api.komme.xyz
```

Backend/worker deploy on EC2:

```bash
cd ~/pulse
git pull
docker compose --env-file deploy/ec2/.env.ec2 -f deploy/ec2/docker-compose.yml up --build -d
```

Production domain values on EC2 should include:

```env
API_DOMAIN=api.komme.xyz
API_DOMAIN_ALIASES=pulse-api.duckdns.org
WORKER_DOMAIN=worker.komme.xyz
WORKER_DOMAIN_ALIASES=pulse-worker.duckdns.org
WEB_APP_URL=https://komme.xyz
WEB_ALLOWED_ORIGINS=https://komme.xyz,https://www.komme.xyz,https://pulse-app.duckdns.org
INNGEST_APP_ID=komme-worker
```

Keep old DuckDNS aliases temporarily during migration.

## DNS

Recommended production DNS shape:

- `komme.xyz`: Vercel production frontend.
- `www.komme.xyz`: Vercel frontend alias or redirect.
- `api.komme.xyz`: EC2 API through Caddy.
- `worker.komme.xyz`: EC2 worker through Caddy.

After DNS changes, verify:

```bash
curl https://komme.xyz
curl https://api.komme.xyz/healthz
curl https://worker.komme.xyz/healthz
curl -i -H "Origin: https://komme.xyz" https://api.komme.xyz/v1/auth/me
```

## Inngest

The Inngest serve endpoint is hosted by the EC2 worker, not the Vercel web app:

```text
https://worker.komme.xyz/api/inngest
```

During migration, the old fallback may also work:

```text
https://pulse-worker.duckdns.org/api/inngest
```

Inngest must use the same signing key configured in EC2:

```env
INNGEST_SIGNING_KEY=
```

## Spotify OAuth

For production Spotify login/taste sync, add this redirect URI in the Spotify developer app:

```text
https://api.komme.xyz/v1/spotify/connect/callback
```

Keep the old DuckDNS callback only while migration is still active.

## Repository Notes

- Komme began as Pulse, so some internal names, package names, test fixtures, and compatibility headers still use `pulse`.
- Do not rename internal protocol fields casually; some session and digest compatibility depends on them.
- Current product priority is real event supply, recommendation quality, source trust, personalization, planner usefulness, and clean UX.

## License And Copyright

Copyright © 2026 Duy Huynh.

This repository is an active product codebase. Contact the owner before reusing production-specific deployment, branding, or data-source configuration.

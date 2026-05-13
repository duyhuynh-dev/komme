# Komme EC2 Deployment

This deploy target runs the backend Komme stack on a single EC2 instance with Docker Compose:

- `api` on `https://$API_DOMAIN`
- `worker` on `https://$WORKER_DOMAIN`
- `caddy` handling TLS and reverse proxying

The `web` app is intended to run on `Vercel` with its own custom domain.

The stack assumes you are keeping:

- `Supabase` for auth and Postgres
- `Resend` for email
- `Inngest Cloud` for orchestration

## 1. Prepare the EC2 host

Use an Ubuntu 24.04 or similar Linux host with:

- Docker Engine
- Docker Compose plugin
- ports `80` and `443` open in the security group
- your DNS records pointing to the instance:
  - `$API_DOMAIN`
  - optional `$API_DOMAIN_ALIASES`
  - `$WORKER_DOMAIN`
  - optional `$WORKER_DOMAIN_ALIASES`

## 2. Create the EC2 env file

Copy the example file and fill in real values:

```bash
cp deploy/ec2/.env.ec2.example deploy/ec2/.env.ec2
```

Important production values:

- `DATABASE_URL`
  Usually your Supabase Postgres connection string with `asyncpg`
- `WEB_APP_URL`
- `WEB_ALLOWED_ORIGINS`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `OAUTH_STATE_SECRET`
- `PULSE_SESSION_SECRET`
- `INTERNAL_INGEST_SECRET`
- `RESEND_API_KEY`
- `DIGEST_FROM_EMAIL`
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `TICKETMASTER_API_KEY` if you want live Ticketmaster ingestion
- `SEATGEEK_CLIENT_ID` and optional `SEATGEEK_CLIENT_SECRET` if you want SeatGeek ingestion
- `NYC_EVENTS_API_URL` and optional `NYC_EVENTS_API_KEY` if you want an official NYC events/Open Data feed
- `GEMINI_API_KEY` if you want live AI-backed worker tasks
- `INNGEST_SIGNING_KEY` so the worker exposes the Inngest serve route

Spotify OAuth redirect in production should be:

```text
https://$API_DOMAIN/v1/spotify/connect/callback
```

For Komme production, use:

```text
API_DOMAIN=api.komme.xyz
API_DOMAIN_ALIASES=pulse-api.duckdns.org
WORKER_DOMAIN=worker.komme.xyz
WORKER_DOMAIN_ALIASES=pulse-worker.duckdns.org
WEB_APP_URL=https://komme.xyz
WEB_ALLOWED_ORIGINS=https://komme.xyz,https://www.komme.xyz,https://pulse-app.duckdns.org
```

Keep the DuckDNS aliases only during migration. Once OAuth, Vercel, Inngest, and smoke tests are stable on `komme.xyz`, you can remove the alias values.

## 3. Build and boot the stack

From the repo root:

```bash
docker compose --env-file deploy/ec2/.env.ec2 -f deploy/ec2/docker-compose.yml up --build -d
```

Useful follow-up commands:

```bash
docker compose --env-file deploy/ec2/.env.ec2 -f deploy/ec2/docker-compose.yml ps
docker compose --env-file deploy/ec2/.env.ec2 -f deploy/ec2/docker-compose.yml logs -f api
docker compose --env-file deploy/ec2/.env.ec2 -f deploy/ec2/docker-compose.yml logs -f worker
docker compose --env-file deploy/ec2/.env.ec2 -f deploy/ec2/docker-compose.yml logs -f web
```

The compose stack now includes healthchecks for `web`, `api`, and `worker`, and waits for them before Caddy proxies traffic.

## Security hardening

The EC2 stack terminates TLS with Caddy and applies baseline production hardening:

- automatic HTTP to HTTPS redirects
- Let's Encrypt certificate management
- HSTS on API and worker domains
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- strict referrer policy
- restrictive browser permissions policy
- 10 MB public request body cap at Caddy
- production FastAPI docs/OpenAPI disabled
- trusted host checks for API and worker domains plus local health checks

Keep `API_DOMAIN_ALIASES` and `WORKER_DOMAIN_ALIASES` only while migration/fallback domains are still needed. Removing old aliases later reduces public surface area.

## 4. Health checks

After boot, verify:

```bash
curl https://$API_DOMAIN/healthz
curl https://$WORKER_DOMAIN/healthz
```

Or use the included smoke-test helper:

```bash
bash deploy/ec2/smoke-test.sh deploy/ec2/.env.ec2
```

## 5. Inngest Cloud sync

The Python worker exposes the default Inngest FastAPI serve route at:

```text
https://$WORKER_DOMAIN/api/inngest
```

In Inngest Cloud:

- point your app sync / serve URL at `https://$WORKER_DOMAIN/api/inngest`
- make sure the signing key in Inngest matches `INNGEST_SIGNING_KEY`

## 6. Vercel frontend

Create a Vercel project from this repo using:

- Framework: `Next.js`
- Root directory: `apps/web`

Recommended production custom domain:

```text
https://komme.xyz
```

Recommended Vercel environment variables:

```text
NEXT_PUBLIC_API_URL=https://$API_DOMAIN
NEXT_PUBLIC_SUPABASE_URL=<your supabase url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your supabase anon key>
```

In DNS:

- point `komme.xyz` at Vercel using the records Vercel provides
- point `www.komme.xyz` at Vercel using the records Vercel provides
- point `api.komme.xyz` at your EC2 elastic/public IP
- point `worker.komme.xyz` at your EC2 elastic/public IP
- optionally keep `pulse-api.duckdns.org` and `pulse-worker.duckdns.org` pointed at EC2 during migration

In Vercel, set:

```text
NEXT_PUBLIC_API_URL=https://api.komme.xyz
```

In Spotify developer settings, add the exact redirect URI:

```text
https://api.komme.xyz/v1/spotify/connect/callback
```

In Inngest Cloud, use:

```text
https://worker.komme.xyz/api/inngest
```

## 7. Smoke tests

### Supply sync

```bash
curl -X POST "https://$WORKER_DOMAIN/v1/supply/sync" \
  -H "x-pulse-ingest-secret: $INTERNAL_INGEST_SECRET"
```

### Scheduled digest dry run

```bash
curl -X POST "https://$WORKER_DOMAIN/v1/digests/run-scheduled?dry_run=true&now_override=2026-04-21T13:05:00%2B00:00" \
  -H "x-pulse-ingest-secret: $INTERNAL_INGEST_SECRET"
```

### Scheduled digest real send

Remove `dry_run=true` once:

- `RESEND_API_KEY` is valid
- `DIGEST_FROM_EMAIL` uses a verified sender
- at least one signed-in user has digest preferences enabled

## 7. Updating the stack

Pull new code, then rebuild:

```bash
git pull
docker compose --env-file deploy/ec2/.env.ec2 -f deploy/ec2/docker-compose.yml up --build -d
```

## Notes

- `web` is hosted on `Vercel` in this setup.
- The `api` talks to the `worker` over the internal Docker network with `http://worker:8001`.
- The `worker` talks back to the `api` internally with `http://api:8000`.
- Caddy terminates TLS automatically for `api` and `worker` once those domains resolve to the EC2 instance.

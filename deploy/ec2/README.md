# Pulse EC2 Deployment

This deploy target runs the backend Pulse stack on a single EC2 instance with Docker Compose:

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
  - `$WORKER_DOMAIN`

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

Your frontend origin in production should be the Vercel custom domain, for example:

```text
WEB_APP_URL=https://pulse-app.duckdns.org
WEB_ALLOWED_ORIGINS=https://pulse-app.duckdns.org
```

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
https://pulse-app.duckdns.org
```

Recommended Vercel environment variables:

```text
NEXT_PUBLIC_API_URL=https://$API_DOMAIN
NEXT_PUBLIC_SUPABASE_URL=<your supabase url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your supabase anon key>
```

In DuckDNS:

- point `pulse-app.duckdns.org` at `76.76.21.21` for Vercel
- point `pulse-api.duckdns.org` at your EC2 public or elastic IP
- point `pulse-worker.duckdns.org` at your EC2 public or elastic IP

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

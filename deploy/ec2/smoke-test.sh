#!/usr/bin/env bash

set -euo pipefail

ENV_FILE="${1:-deploy/ec2/.env.ec2}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${APP_DOMAIN:?APP_DOMAIN is required}"
: "${API_DOMAIN:?API_DOMAIN is required}"
: "${WORKER_DOMAIN:?WORKER_DOMAIN is required}"

echo "Checking API health..."
curl --fail --silent --show-error "https://${API_DOMAIN}/healthz"
echo

echo "Checking worker health..."
curl --fail --silent --show-error "https://${WORKER_DOMAIN}/healthz"
echo

echo "Checking web root..."
curl --fail --silent --show-error --head "https://${APP_DOMAIN}"
echo

if [[ -n "${INTERNAL_INGEST_SECRET:-}" ]]; then
  echo "Checking scheduled digest dry run..."
  curl --fail --silent --show-error -X POST \
    "https://${WORKER_DOMAIN}/v1/digests/run-scheduled?dry_run=true&now_override=2026-04-21T13:05:00%2B00:00" \
    -H "x-pulse-ingest-secret: ${INTERNAL_INGEST_SECRET}"
  echo
fi

echo "Smoke test complete."

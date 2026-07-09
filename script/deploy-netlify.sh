#!/usr/bin/env bash
# Builds the client and deploys dist/public straight to Netlify — no manual
# drag-and-drop needed. Requires NETLIFY_AUTH_TOKEN and NETLIFY_SITE_ID to be
# set as Replit Secrets (Tools -> Secrets).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${NETLIFY_AUTH_TOKEN:-}" ]; then
  echo "Missing NETLIFY_AUTH_TOKEN secret. Add it in Replit Secrets, then re-run." >&2
  exit 1
fi
if [ -z "${NETLIFY_SITE_ID:-}" ]; then
  echo "Missing NETLIFY_SITE_ID secret. Add it in Replit Secrets, then re-run." >&2
  exit 1
fi

echo "Building client..."
npm run build:client

echo "Deploying dist/public to Netlify (site: $NETLIFY_SITE_ID)..."
# NETLIFY_AUTH_TOKEN is picked up from the environment by netlify-cli itself —
# never pass it as a --auth CLI argument, since that leaks it into process
# listings/shell history/logs.
export NETLIFY_AUTH_TOKEN
npx --yes netlify-cli deploy \
  --dir=dist/public \
  --site="$NETLIFY_SITE_ID" \
  --prod \
  --message="Deploy from Replit $(date -u +%Y-%m-%dT%H:%M:%SZ)"

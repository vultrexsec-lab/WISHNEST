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
npx --yes netlify-cli deploy \
  --dir=dist/public \
  --site="$NETLIFY_SITE_ID" \
  --auth="$NETLIFY_AUTH_TOKEN" \
  --prod \
  --message="Deploy from Replit $(date -u +%Y-%m-%dT%H:%M:%SZ)"

#!/usr/bin/env bash
# Backend startup wrapper — avoids shell quoting issues with secret values
set -e
cd "$(dirname "$0")"
# --timeout-keep-alive raised well past the default 5s: on Render the first
# request after an idle spin-down can take a while to get a full response
# while the instance cold-starts, and a short keep-alive timeout risked the
# server dropping that connection out from under the client mid-boot.
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --timeout-keep-alive 120

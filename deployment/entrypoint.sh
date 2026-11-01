#!/bin/sh
# Apply database migrations and create the initial owner once, then start the API.
set -eu

python -m server.manage init

# Only the reverse proxy can reach this container, so trust its X-Forwarded-* headers.
exec uvicorn server.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WEWIN_WORKERS:-2}" \
    --proxy-headers \
    --forwarded-allow-ips '*' \
    --no-server-header

#!/bin/bash
# Tres Comas container entrypoint: apply Alembic migrations, then start Uvicorn.
#
# Migrations run on every start. `alembic upgrade head` is a no-op when the
# schema is current, and a failed migration stops the container before it serves
# any request.
#
# --workers 1 is an invariant, not a tuning knob: the price/FX poller (T7) is an
# in-process APScheduler job, and a second worker would run a second scheduler.
#
# --proxy-headers + --forwarded-allow-ips="*": Caddy sends X-Forwarded-Proto:
# https. Without these flags, Starlette builds the /mcp trailing-slash redirect
# from uvicorn's own (http) view of the request and downgrades it to http://.
# OAuth-aware clients such as the claude.ai connector refuse to follow that
# redirect. This was learned in Anton. "*" is safe because the only traffic that
# reaches the container comes from Caddy over loopback (the port is published as
# 127.0.0.1:8001 only), never from external clients directly.
set -euo pipefail

mkdir -p /data
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips="*"

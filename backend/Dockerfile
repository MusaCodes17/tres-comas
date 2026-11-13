# Tres Comas backend: Python 3.11 + sqlite3 CLI.
#
# Unlike Anton, there is no Playwright/Chromium (no scraping here) and no
# Litestream (encrypted off-box backups are a spec requirement not yet built; they are not part of T1).
#
# One Uvicorn worker is required: the price/FX poller (T7) is an in-process
# APScheduler job, so a second worker would run its own copy of the scheduler
# and double every poll. See AGENTS.md §4.6 and entrypoint.sh.
FROM python:3.11-slim-bookworm

# sqlite3 CLI is for read-only inspection of /data/tres_comas.db on the host.
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend source (app/, alembic/, alembic.ini, ...).
COPY . .

# Make entrypoint executable after COPY (it is stored as plain text in the repo).
RUN chmod +x /app/entrypoint.sh

# Timezone: "last trading day" and *_date fields are America/Toronto calendar
# dates (AGENTS.md §5). Setting TZ at the OS level stops anything from silently
# reading the container's UTC clock.
ENV TZ=America/Toronto

EXPOSE 8000

# entrypoint.sh runs migrations, then execs uvicorn (one worker).
CMD ["/app/entrypoint.sh"]

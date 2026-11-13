# Tres Comas — Session Changelog

**Status / current focus:** see `docs/project_state.md`. This file is the append-only session log: newest entry at the top, dated title, `[ADDED]/[CHANGED]/[REMOVED]/[BLOCKED]/[VERIFIED]`, what / why / how verified.

---

## T1: repo scaffold, CI and push-to-main deploy — 2026-11-13

Branch `claude/nice-darwin-p5e56r`. Ran via `/orchestrate`: four workers in parallel, each diff reviewed before acceptance (one was sent back for a wrong comment). Musa confirmed the plan, the domain `trescomas.musasouled.com` and deploying with a GitHub Action over SSH.

**[ADDED]**
- `backend/`: FastAPI app with a public `GET /health`, SQLAlchemy engine/session/`Base`, empty Alembic (batch mode), `run.py` (dev, port 8001), pytest with a temp DB set in `conftest.py`, `.env.example`, Dockerfile (python:3.11-slim-bookworm) and `entrypoint.sh` (migrate, then one Uvicorn worker with proxy headers).
- `frontend/`: Vite + React 18 + Tailwind + React Query PWA skeleton with a manifest, service worker and a backend-health status line. Dev port 5174.
- `docker-compose.yml` (service `tres-comas`, `127.0.0.1:8001`, data volume, optional root `.env`), `deploy/Caddyfile` site block, `deploy/.env.production.example` (key names only).
- `.github/workflows/ci.yml`: backend pytest, hook unittests, vite build, and a `deploy` job on push to `main`.
- `docs/architecture.md` §10: deployment and the one-time box setup.

**[BLOCKED]** Encrypted off-box backups are not built yet. They're required before real data goes in.

**[VERIFIED]** Backend 2 passed (Python 3.13 locally; CI runs 3.11). Hook tests 16 passed. `vite build` is clean and emits `manifest.webmanifest` and `sw.js`. `docker compose config` is valid. actionlint is clean. The entrypoint's commands (`alembic upgrade head`, then Uvicorn with the same flags) served `{"status":"ok"}` on 8001. **Not verified:** `docker build`, because this sandbox cannot resolve the Debian mirrors so the `apt-get` step could not run; and the deploy job end to end, because there are no box secrets yet. The first deploy is the first real image build.

**Note:** the guard's `.env` read rule also fires on shell text that merely names a `.env` path (seen when writing these docs through a heredoc). It is harmless, and file-tool edits are unaffected.

---

## Project spine: spec, docs, guardrails and skills — 2026-11-13

Branch `claude/nice-darwin-p5e56r`. The repo was empty. This session committed the v1 spec and set up the working structure, following Anton's conventions. **No build-plan task was executed**: there is no application code, Compose file or CI yet.

**[ADDED]**
- `docs/v1_spec.md` — the v1 spec as written by Musa.
- `AGENTS.md` (+ `CLAUDE.md` → `@AGENTS.md`), `README.md`, `.gitignore` (blocks `.env*`, `*.db`, and real broker exports: `*.csv` outside `backend/tests/fixtures/`).
- `docs/`: `invariants.md` (INV-1–9 with planned owner and guard), `design_decisions.md` (C-1–5, D-1–14, pending P-1–P-5), `architecture.md`, `roadmap.md` (F1–F5, T1–T11 with invariants per task, R2–R5, parked), `project_state.md`, `handover_template.md`.
- `.claude/hooks/pre_guard.py` + `test_pre_guard.py`, wired in `.claude/settings.json`: denies agent edits to secrets and DB files, broker/aggregator hosts in code (INV-1/5) and real exports in the repo; asks before floats on money paths (INV-9), raw HTTP outside `connections/` (INV-7), auth/MCP-scope edits, applied-migration edits, `alembic downgrade`, and pushes to `main` (which deploys).
- `.claude/skills/`: `ledger-write-path`, `add-broker-importer`, `add-outbound-connection`, `look-through-exposure`, `add-database-model`, `add-mcp-tool`, `write-tests`, `invariant-review`, `session-wrapup`.
- `.claude/commands/`: `status`, `next`.

**[CHANGED]** From Anton: skills use the `.claude/skills/<name>/SKILL.md` format so Claude Code discovers them, rather than flat reference files.

**[BLOCKED]** P-2 (market-data provider) is still open; resolved by the D-14 spike before T7.

**[VERIFIED]** Hook tests: `python3 -m unittest discover -s .claude/hooks -p 'test_*.py'` — 16 passed. No app suite yet.

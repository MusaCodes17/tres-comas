# Tres Comas — Session Changelog

**Status / current focus:** see `docs/project_state.md`. This file is the append-only session log: newest entry at the top, dated title, `[ADDED]/[CHANGED]/[REMOVED]/[BLOCKED]/[VERIFIED]`, what / why / how verified.

---

## T6: connection registry and outbound log — 2026-11-13

Branch `claude/nice-darwin-p5e56r`. Ran via `/orchestrate` in three parts: T6a (sonnet/high) built the registry and `call()`, T6b (haiku/medium) the REST API, and T6c (haiku/medium) the Connections screen. Every diff was reviewed.

T6a was sent back once because of a fault in my brief. It asked for a broker-host blocklist in code, which the guard hook rightly denies. The worker stopped instead of working around the hook. The blocklist was dropped and INV-1 stays enforced by the kind allowlist, the DB CHECK and the hook (debt note added). T5 was deferred because it needs the real export's header row; Musa decided its dedup key (P-3 → D-29).

**[ADDED]**
- `app/connections/`:
  - `errors.py`;
  - `registry.py` (validated create, always disabled; `set_enabled`; `public_view` with `secret_configured` and no value; `recent_log`);
  - `client.call`: the single outbound path. It checks enabled, kind, URL and param scope before sending, applies the secret from env at call time, and logs every call made, then commits it (D-26, D-27);
  - `providers/` (empty until T7).
- Migration `0003`: `boc_valet` seeded disabled (D-28).
- `/api/connections`: list, create, PATCH enabled, `/{id}/log`. Request bodies forbid extra fields and the `enabled` field must be a strict bool.
- PWA Connections screen: an on/off toggle (confirms before switching on), the secret key name with a configured badge, and the log of each call's time, endpoint, tickers and result.
- Decisions D-26 to D-29; P-3 retired.

**[CHANGED]**
- `requirements.txt`: `httpx` is now a runtime dependency (comment only).
- `test_schema.py::test_connections_default_disabled` filters by name, because the seeded row now exists.

**[VERIFIED]**
- Backend suite: 287 passed (was 215), with no network in any test. New invariant tests:
  - `test_inv1_no_broker_connection_kinds`;
  - `test_inv3_registry_never_returns_secret_values`, `test_inv3_secret_never_logged_header` / `_query_param`, `test_inv3_connections_api_never_returns_secret`;
  - `test_inv4_market_data_payload_is_tickers_only`;
  - `test_inv7_disabled_connection_makes_no_call`, `test_inv7_every_call_logged`, `test_inv7_new_connection_disabled`.
- Hook tests: 16 passed.
- `alembic check` is clean after 0003.
- `vite build` is clean.
- Playwright smoke test at 390×844: `boc_valet` shows Disabled, switching it on confirms and then shows Enabled, and the log shows "No calls yet".

**Note:** a T6b worker made one stray tool call that tried to interrupt a session with a made-up ID. It was denied and nothing changed.

---

## T4: auth, accounts and the manual-entry PWA — 2026-11-13

Branch `claude/nice-darwin-p5e56r`. Ran via `/orchestrate` as three workers in sequence: T4a (sonnet/high) did auth and sessions, T4b (sonnet/medium) the REST API, T4c (sonnet/medium) the PWA screens. Each diff was reviewed and accepted first time. Musa decided P-5: a password with server-side sessions, 30 days sliding, and no account delete.

**[ADDED]**
- Auth (D-23, D-24):
  - `app/services/auth.py`: scrypt verify against `TRES_COMAS_PASSWORD_HASH`, sessions stored as a sha256 of the token, sliding expiry, and the login throttle.
  - `app/routers/auth.py`: login, logout, logout-all, me.
  - `app/routers/deps.py`: app-wide `require_session` (default deny) and `service_errors`.
  - Migration `0002` (`auth_sessions`) and `backend/hash_password.py`.
- API (D-25): `app/schemas/` (extra fields forbidden, decimals as strings, `dec_str`), `services/accounts.py`, `services/securities.py`, and routers for accounts, securities, transactions (create, void, replace) and positions. There is no DELETE route.
- PWA:
  - Login, Accounts and AccountDetail pages.
  - Positions, transaction form and list, and security form.
  - `lib/format.js`: string-only rounding.
  - A global 401 handler that sends you back to Login.
- Env examples gain `TRES_COMAS_PASSWORD_HASH` and `TRES_COMAS_COOKIE_SECURE` (names only), replacing the old plain-password and session-secret placeholders.
- Decisions D-23 to D-25; P-5 retired. MCP tokens are left to T11.

**[CHANGED]** `test_schema.py::test_upgrade_creates_the_ten_tables` now expects `auth_sessions` as well.

**[VERIFIED]**
- Backend suite 215 passed (was 166), including:
  - `test_auth_default_deny_every_route`, which sweeps every route;
  - `test_f1_manual_entry_via_api_nine_positions`;
  - the invariant tests `test_inv2_no_position_write_endpoint`, `test_inv3_password_hash_never_returned`, `test_inv6_api_cannot_set_source_or_proposal`, `test_inv8_api_rejects_account_number` and `test_inv9_api_rejects_json_numbers`.
- Hook tests 16 passed, and `alembic check` is clean after 0002.
- `vite build` is clean, and `formatDecimal` passed seven edge cases.
- A Playwright smoke test at 390×844 against the real backend covered a wrong password, login, creating an account, adding a security and a buy, the position showing 10.5000, and logout. **Not exercised in a browser:** void, correct, the oversell message and session expiry. All four are covered by backend tests.

---

## T3: ledger write path and position derivation — 2026-11-13

Branch `claude/nice-darwin-p5e56r`. Ran via `/orchestrate`: T3a (sonnet/high) wrote position derivation and T3b (sonnet/high) the ledger writer. Both diffs were reviewed and accepted first time, and an invariant review was run on the task. Musa decided P-4 (weighted average cost), that oversells are refused at write time, and that positions cover securities only in v1.

**[ADDED]**
- `app/services/positions.py`: `Position`, pure `derive()`, `get_positions`, `get_position`. Exact Decimal arithmetic at precision 34 with no rounding; proportional cost removal on sells; splits scale quantity only (D-19).
- `app/services/ledger.py`: `record_transaction`, `void_transaction`, `void_and_replace`. Per-type validation, float/bool/NaN refused, currency must match the security, source/batch/proposal pairing, and the never-negative replay before any write (D-20). Flushes and never commits.
- `tests/conftest.py`: a `session` fixture on a freshly migrated temp DB. Also `tests/test_positions.py` and `tests/test_ledger.py`, including the F1 nine-position check on synthetic quantities.
- Decisions D-19 to D-22; P-4 retired.

**[VERIFIED]** Backend suite 166 passed (was 34); hook tests 16 passed. New invariant tests: `test_inv2_positions_rebuild_from_transactions`, `test_inv2_ledger_is_sole_transaction_writer`, `test_inv9_ledger_rejects_float` / `_bool` / `_non_finite`. Invariant review: INV-2 and INV-9 pass. INV-6 holds because `source="proposal"` needs a real proposal row and only app code calls the ledger. The rest are not touched.

---

## T2: schema and migrations for the ten tables — 2026-11-13

Branch `claude/nice-darwin-p5e56r`. Ran via `/orchestrate`: T2a (haiku/medium) built the decimal type, T2b (sonnet/medium) the models, migration and tests, and a haiku/low worker fixed comments. Every diff was reviewed, and an invariant review was run on the whole task. Musa decided the three open choices: exact-text decimals, append-only enforced in the database, and connections off by default.

**[ADDED]**
- `app/models/types.py`: `DecimalText`, exact plain-notation TEXT. Refuses float, bool, NaN and infinity (D-15).
- `app/models/models.py`: the ten models. Plural table names (D-18), CHECK-constrained enums and ISO currency codes, RESTRICT foreign keys, no account-number column.
- `alembic/versions/0001_initial_schema.py`: all ten tables plus the append-only triggers on `transactions` (D-16). The downgrade drops the triggers, then the tables.
- `app/database.py`: `PRAGMA foreign_keys=ON` on every SQLite connection.
- `alembic/env.py`: imports the models; an explicit `cfg.attributes["url"]` overrides `DATABASE_URL` (for tests).
- Decisions D-15 to D-18; P-1 retired. A debt note: Alembic can't detect drift in CHECK constraints or triggers.

**[VERIFIED]** Backend suite 34 passed (was 2): 16 type tests and 16 schema tests, including every INV-2, INV-8 and INV-9 test now listed in `docs/invariants.md`. `alembic upgrade head` then `alembic check` reports "No new upgrade operations detected". Invariant review: INV-2, 8 and 9 pass; the other six are not touched.

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

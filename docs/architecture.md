# Tres Comas — Architecture Reference

**Last updated:** 2026-11-13. **Status:** planned. Nothing below is built yet; sections are marked with the build-plan task that creates them. When a task ships, update the section it makes true.

---

## 1. High-Level Architecture

One service on the Hetzner box owns the ledger and every connection. The broker sits outside with **no link**; Musa is the only path between them.

```
   Broker app (Wealthsimple)                     Anthropic cloud
   ─ trades happen here ─                        Claude (web/mobile)
            │                                          │
     Musa: manual entry / CSV upload            public HTTPS /mcp
     (activity statement, holdings report)      token: read | read+propose
            │                                          │  (inbound, registry row)
            ▼                                          ▼
  ┌───────────────────────── Tres Comas (Docker Compose, beside Anton) ─────────────────────────┐
  │  PWA (own login) ── routers ── services ──────────────── SQLite ledger                       │
  │                                 ├ ledger.record_transaction  (sole writer, INV-2)            │
  │                                 ├ positions / exposure / reconcile (derived)                 │
  │                                 └ proposals (inbox; confirm in app only, INV-6)              │
  │  importers/ (per-broker adapters, parse only)                                                │
  │  scheduler ── connections/ (registry check → call → outbound_log)                            │
  └─────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                        │ outbound: tickers / dates only (INV-4, INV-7)
                       ┌────────────────┴─────────────────┐
                 Price + ETF holdings provider       Bank of Canada Valet (FX)
                 (chosen by D-14 spike)              no key (D-13)
```

Two connections go out and one comes in, each through the registry. No LLM sits between the app and its data; the backend polls providers on a schedule.

## 2. Technology Stack (D-6, mirrors Anton)

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, SQLite, Alembic (batch mode), APScheduler (one in-process scheduler), `mcp[cli]` FastMCP.
- **Frontend:** React 18 + Vite + Tailwind + React Query, JSX, PWA (D-10).
- **Deploy:** Docker Compose service beside Anton, Caddy for TLS, production `.env` as source of truth for config and secrets, push-to-main deploy (T1), encrypted off-box backups.

## 3. Folder Structure

See `AGENTS.md` §3. Created in T1.

## 4. Data Model (T2)

Ten tables. The ledger is `account`, `security`, `transaction`; the rest is market data, imports or control.

| Table | Holds | Key fields |
| --- | --- | --- |
| `account` | One row per real-world account | nickname, type (tfsa, rrsp, non_registered, cash), base currency, broker label, last reconciled date. **No account number** (INV-8). |
| `security` | Anything that can be held | ticker, exchange, currency, kind (stock, etf, cash). Identity = ticker + exchange. |
| `transaction` | Every ledger event, append-only | account, security, type, quantity, price, amount, currency, trade date, source (manual, import, proposal), import batch, voided flag / replaces id. |
| `price` | Daily close per security | security, date, close, currency, provider |
| `fx_rate` | Daily rate per currency pair | pair, date, rate, provider |
| `etf_constituent` | What each ETF holds | ETF, underlying security, weight, as-of date |
| `import_batch` | One row per uploaded file | account, broker adapter, file hash, row counts, status |
| `proposal` | Changes suggested by an external client | payload, origin, status (pending, confirmed, dismissed) |
| `connection` | Registry of integrations | name, kind, direction, scope, secret env key name, enabled, created, last used |
| `outbound_log` | One row per outbound call | connection, timestamp, endpoint, tickers sent |

**Transaction types:** buy, sell, dividend, deposit, withdrawal, fee, split, transfer_in, transfer_out.

**Derived, never stored as truth:** positions (quantity and average cost per account × security), market value, gain/loss, exposure. A cache is allowed only if rebuildable from transactions alone.

**Corrections:** new transactions or a voided-and-replaced pair; history stays auditable.

**Money storage:** see `design_decisions.md` D-15 (decimal as TEXT on SQLite).

**As built (T2, migration `0001`, `backend/app/models/models.py`):** table names are plural (`accounts`, `securities`, `transactions`, `prices`, `fx_rates`, `etf_constituents`, `import_batches`, `proposals`, `connections`, `outbound_logs`; D-18). Extra columns beyond the spec's key fields:
- `securities`: `name` and `sector` (for F4).
- `transactions`: `split_ratio`, `natural_key` (unique; P-3), `proposal_id`, `voided_at`, `replaces_id`, `note`.
- `outbound_logs`: `succeeded`.

Enums and currency codes are CHECK constraints, and `fx_rates.pair` must match `AAA_BBB`. Foreign keys are enforced (`PRAGMA foreign_keys=ON`) and all use `RESTRICT`. `transactions` is append-only by trigger (D-16). `connections.enabled` defaults to false (D-17).

**Auth (T4, migration `0002`):** `auth_sessions` holds one row per login: `token_hash` (sha256, unique), `last_seen_at`, `expires_at`, `revoked_at`, `user_agent`. The raw token exists only in the cookie (D-23).

## 5. Services Layer

| Service | Job | Task |
| --- | --- | --- |
| `ledger` | Validate and record transactions; void and replace. Sole writer; refuses changes that would go negative (D-20). Built: `record_transaction`, `void_transaction`, `void_and_replace`. | T3 |
| `auth` | Password verify (scrypt hash from env), server-side sessions with 30-day sliding expiry, login throttle (D-23, D-24). | T4 |
| `accounts`, `securities` | Create, list, edit; duplicates and unknown ids refused; no delete (D-25). Tickers and exchanges uppercased. | T4 |
| `positions` | Derive quantity, total cost, average cost and realised gain per account × security from non-voided transactions, in (trade_date, id) order (D-19). Built: `derive`, `get_positions`, `get_position`. | T3 |
| `importers.*` | Parse a broker file into normalized rows; never write. `wealthsimple` first. | T5, T10 |
| `connections` | Registry CRUD, enabled/scope checks, outbound HTTP, `outbound_log`. | T6 |
| `market_data` | Scheduled price + FX poll through `connections`. | T7 |
| `exposure` | Two-level look-through by company, sector, currency; top-N + "other". | T8 |
| `portfolio` | Totals per account and overall in CAD with rate + date. | T9 |
| `reconcile` | Diff a holdings report against derived positions; set last reconciled date on a clean report. | T10 |
| `proposals` | Create (from MCP), list, confirm (→ ledger), dismiss. | T11 |

## 6. Request Flows

- **Manual entry (F1):** PWA form → `POST /api/accounts/{id}/transactions` → `ledger.record_transaction(source="manual")` → positions re-derived on read (`GET /api/accounts/{id}/positions`). Corrections: `POST /api/transactions/{id}/void` and `/replace`. Request bodies forbid unknown fields and take decimals as strings only.
- **CSV import (F2):** upload → `import_batch` by file hash (duplicate file = no-op) → adapter parses → dedup on natural key (P-3) → `ledger.record_transaction(source="import")` per new row, one DB transaction per batch.
- **Price/FX poll (F3):** scheduler → for each held security, `connections.call("prices", tickers=[...])`; `connections.call("boc_valet", series=["FXUSDCAD"])` → `price`, `fx_rate` rows.
- **Look-through (F4):** positions × latest price × FX → per-ETF `etf_constituent` (level 1) → constituents that are themselves ETFs unpacked again (level 2) → aggregated per underlying.
- **Reconciliation (F5):** upload holdings report → parse → diff per security (quantity to 4 dp) → mismatches listed; clean → `account.last_reconciled_date`.
- **Propose/confirm (T11):** Claude → `propose_transactions` → `proposal` rows (pending) → inbox → Musa confirms in app → ledger. MCP can never reach the confirm path.

## 7. AI Layer (T11)

- **MCP endpoint** at public HTTPS `/mcp` (C-4), app-issued tokens with scope `read` or `read+propose` — there is no write scope. Tools: `get_portfolio`, `get_position`, `get_exposure`, `get_reconciliation_status`, `list_proposals` (read), `propose_transactions` (read+propose). Brief by default, `detail=True` for full records, lists paged.
- **In-app decision support** (D-4) uses Musa's Anthropic key from `.env`; payloads may include tickers, weights and amounts, never nicknames or broker labels (D-9). Its connection is a registry row of kind `llm`.

## 8. Authentication & Security Posture

- Auth on every route, including read-only ones; own login, separate from Anton (D-10). **As built (T4, D-23/D-24):** an app-level `require_session` dependency denies every route except `/health` and `/api/auth/login`; `tc_session` cookie is HttpOnly, Secure, SameSite=Strict; sessions are revocable rows; 5 failed logins per 15 minutes → 429; docs/OpenAPI routes are off.
- Secrets only in production `.env`; the registry stores env key **names** (INV-3).
- Outbound rules by kind:

| Kind | May send | Never sends |
| --- | --- | --- |
| market_data | Tickers, date ranges | Quantities, values, account names |
| news | Tickers, company names | Quantities, values, account names |
| llm | Tickers, weights, dollar amounts | Account nicknames, broker labels |

- Inbound MCP tokens revocable from the registry, last use shown.
- Encrypted off-box backups; `outbound_log` viewable in-app so any call can be checked against INV-4.

## 9. External Integrations

| Integration | Kind | Direction | Secret | Status |
| --- | --- | --- | --- | --- |
| Price + ETF holdings provider | market_data | outbound | `.env` key (TBD) | Pending D-14 spike (P-2) |
| Bank of Canada Valet | market_data (FX) | outbound | none | Decided (D-13) |
| Anthropic API | llm | outbound | `ANTHROPIC_API_KEY` | Decided (D-4), not in v1 build plan |
| Claude MCP client | mcp_client | inbound | app-issued token | T11 |

## 10. Deployment (T1)

**Pipeline** (`.github/workflows/ci.yml`): every PR and push to `main` runs three gates: backend pytest (Python 3.11), guard-hook unittests, `vite build`. On a push to `main` with all three green, the `deploy` job (GitHub environment `production`) copies the tested `frontend/dist` to `/var/www/tres-comas/` with rsync. It then SSHes in, moves `/opt/tres-comas` to the exact commit, runs `docker compose up -d --build` and polls `http://127.0.0.1:8001/health` for about 60 s. Until the deploy secrets exist, the job logs a warning and skips, so `main` stays green.

**Secrets (GitHub):** `HETZNER_HOST`, `HETZNER_USER`, `HETZNER_SSH_KEY` (a deploy-only key) and `HETZNER_KNOWN_HOSTS` (pinned `ssh-keyscan` output; host keys are never accepted on first use). They reach steps only through `env:`.

**Runtime:** Compose service `tres-comas`, container port 8000 published on `127.0.0.1:8001` only (Anton holds 8000). SQLite lives at `/data/tres_comas.db`, mapped to `$TRES_COMAS_DATA_DIR` (default `~/tres-comas-data`). `entrypoint.sh` runs `alembic upgrade head`, then one Uvicorn worker with proxy headers. Caddy terminates TLS for `trescomas.musasouled.com`: `/api`, `/mcp` and `/health` go to the backend, and everything else is the SPA.

**One-time box setup (manual, Musa):**
1. DNS: an `A`/`AAAA` record for `trescomas.musasouled.com` pointing at the box.
2. A deploy user that can run `docker compose` without sudo and can write to `/opt/tres-comas` and `/var/www/tres-comas`, with the deploy public key in its `authorized_keys`.
3. Clone the repo to `/opt/tres-comas`. A private repo needs a read-only deploy key on the box.
4. Copy `deploy/.env.production.example` to `/opt/tres-comas/.env` and fill in the values by hand (INV-3). Generate `TRES_COMAS_PASSWORD_HASH` with `python hash_password.py` in `backend/` (on any machine with Python 3.11); without it, login answers 503. Create `~/tres-comas-data` and `/var/www/tres-comas`.
5. Append `deploy/Caddyfile` to `/etc/caddy/Caddyfile` beside Anton's block and reload Caddy.
6. Add the four GitHub secrets. The next push to `main` deploys.

**Not yet built:** encrypted off-box backups (spec §Protecting the data at rest). They're needed before real data goes in.

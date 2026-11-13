# AGENTS.md — Tres Comas Development Guide

**Reference docs** (`docs/`): `v1_spec.md` (the source of truth for v1 scope), `invariants.md` (the nine rules, with owning code and guards), `design_decisions.md` (constraints C-*, decisions D-*, pending P-*), `architecture.md`, `roadmap.md` (features, build plan T1–T11, releases R2–R5), `project_state.md` (what's true now), `changelog.md` (session history; append an entry at the top after every working session), `handover_template.md`. This file is the *stable* guide; the changelog is the *running* history.

**Status:** building v1. T1–T4 and T6 done (scaffold, schema, ledger and positions, auth and manual-entry PWA, connection registry); T5 waits on the export header and the D-14 spike is parked; see `docs/project_state.md` for what is true now.

---

## 1. Project Overview

Tres Comas is a **single-user, self-hosted investment ledger**. Every investment account (first the Wealthsimple TFSA, then the RRSP) is recorded by hand or by CSV import, and the app shows **true exposure** across accounts once ETFs are unpacked. It is part of **Son of Anton**, the umbrella for Musa's AI tools; it runs as its own service beside Anton on the Hetzner box.

It has **no connection to any broker** (INV-1). Trades happen in the broker app and are recorded here afterwards. Musa is the only path between the broker and the ledger.

Planned stack (D-6, follows Anton): FastAPI + SQLAlchemy 2 + SQLite + Alembic; React 18 + Vite + Tailwind + React Query (JSX) as a PWA with its own login (D-10); `mcp[cli]` FastMCP for the Claude surface; Docker Compose on Hetzner, push-to-main deploy.

---

## 2. Coding Philosophy

1. **Transactions are the truth.** Positions, market value, gain/loss and exposure are derived. A cache is allowed only if it can be rebuilt from transactions alone (INV-2).
2. **One sanctioned write path.** Every transaction is born through one ledger service function (planned: `services/ledger.record_transaction`). Manual entry, CSV import and confirmed proposals all call it. Add parameters, never a parallel path.
3. **Nothing leaves without a registry row.** Every outbound call goes through the connection registry and is logged (INV-7). If you are about to `import requests` outside the registry client, stop.
4. **Tickers out, never money out — to market data.** Market-data and news calls send tickers (and dates / company names) only (INV-4). LLM analysis may see weights and amounts, never account nicknames or broker labels (D-9).
5. **The human confirms.** External clients, Claude included, only create proposals. A proposal becomes a transaction only when Musa confirms it in the app (INV-6).
6. **Decimal or nothing.** Money and quantities are `Decimal` with an explicit currency, end to end. A `float` anywhere on a money path is a bug (INV-9).
7. **Nothing built ahead of felt need** (D-5). The schema is multi-account; the features are investment-only.

---

## 3. Folder Conventions (planned — created in T1)

```
backend/app/
  main.py            app assembly only
  database.py        engine/session/get_db — no logic
  models/            ORM models; schemas/ Pydantic at the API boundary only
  routers/           one file per resource; HTTP concerns only
  services/          the only home for domain rules
    ledger.py        THE write path for transactions (INV-2)
    positions.py     derivation from transactions (T3)
    exposure.py      look-through (T8)
    reconcile.py     holdings-report diff (T10)
    proposals.py     create / confirm / dismiss (T11)
  importers/         one adapter per broker behind one interface (D-7)
    base.py          the interface
    wealthsimple.py  activity statement + holdings report
  connections/       registry client: the ONLY module that makes outbound HTTP (INV-7)
    providers/       one file per provider (prices, FX, ETF holdings)
  mcp_server/        thin adapters; read + propose tools only (INV-6)
backend/alembic/     migrations — every schema change gets one
backend/tests/       pytest; fixtures are synthetic, never real exports
frontend/src/        pages/, components/, hooks/useApi.js, services/api.js, lib/
deploy/              Compose, Caddy, backup scripts; .env.production.example only
.claude/skills/      project skills (auto-discovered, SKILL.md per folder)
.claude/hooks/       guardrail hooks wired in .claude/settings.json
.claude/commands/    /status, /next
```

Placement: business logic → `services/` (never a router, MCP tool, importer or React component). Parsing → `importers/`, which returns parsed rows and never writes. Outbound HTTP → `connections/`. A spike report sits in `docs/spikes/` while in flight; when decided, its lasting findings move into `design_decisions.md` and the file is deleted.

---

## 4. Architecture Principles

1. **Thin adapters.** Routers, MCP tools and importers translate transport ↔ service calls.
2. **REST/MCP parity on reads.** A read is one service function, exposed by a REST endpoint and (in T11) an MCP tool. Writes have no MCP twin — only `propose_transactions`.
3. **Derived at read time, server-side.** Totals in CAD (D-11) with the FX rate and its date returned alongside, never recomputed in the client.
4. **Registry as choke point.** Providers are called through `connections/` which checks the row is enabled, checks the payload against the row's scope, and writes `outbound_log`.
5. **Graceful degradation.** A disabled or unconfigured connection returns "not configured"; the ledger and positions still work offline.
6. **Single process, one scheduler.** The price/FX poller (T7) is a job on one in-process APScheduler; `--workers 1`.

---

## 5. Coding Standards

**Python**
- Python 3.11+; type hints on service signatures; session first, then keyword-only args.
- `Decimal` for every quantity, price, amount and rate. Construct from `str`, never from `float` (`Decimal("1.25")`, not `Decimal(1.25)`). Parse CSV numbers as strings straight into `Decimal`.
- Every money value travels with its currency (ISO 4217 string). No bare amounts across a function boundary.
- Units/currency in names where ambiguous: `amount_cad`, `price_native`, `fx_usd_cad`. `*_at` = timestamp, `*_date` = calendar date (America/Toronto).
- Docstrings: module states job and rationale; functions state who owns the commit and `Raises:`. Name the invariants a module upholds in its docstring.

**JavaScript/React**
- JSX, no TypeScript; React Query for server state; Tailwind tokens; works at ~380 px.
- Money arrives as **strings** from the API and is formatted, never parsed into `Number` for arithmetic.

**Both:** small diffs; task-prefixed commits (`t3: position derivation`), one per build-plan task, suite green.

---

## 6. Preferred Patterns and Known Traps

**Patterns**
- **Idempotent import:** `import_batch` keyed by file hash; each row gets a stable natural key (date, type, security, quantity, amount, broker row reference if any). Re-uploading a file or an overlapping range adds zero rows (F2).
- **Corrections:** void-and-replace pair or a new adjusting transaction. Never `UPDATE` or `DELETE` a transaction row.
- **Proposal protocol:** client proposes → app shows one line per row in the inbox → Musa confirms → `ledger.record_transaction(source="proposal")` → proposal marked confirmed. No confidence exception.
- **Outbound call:** `connections.call(name, endpoint, tickers=[...])` — the registry builds the request; callers never assemble URLs with portfolio data.

**Known traps (do not rediscover these)**
- **SQLite has no decimal type.** SQLAlchemy `Numeric` on SQLite round-trips through float affinity and loses precision. Store decimals as TEXT through a `Decimal` TypeDecorator (or integer minor units) — see `design_decisions.md` D-15. Never `Float`.
- **Funds of funds.** VGRO, XEQT and XGRO hold other ETFs; look-through is two levels and weights multiply. v1 may cap to top holdings and show the rest as "other" — the remainder must still sum to 100%.
- **Ticker identity.** `MDA.TO` vs `MDA`, `GOOG` vs `GOOGL`: a security is ticker **plus exchange**. Never match on ticker alone.
- **FX direction.** Bank of Canada Valet series are quoted as CAD per unit of foreign currency (`FXUSDCAD`). Name pairs `base_quote` and test the direction.
- **Weekends and holidays.** "Last trading day" differs between TSX and NYSE; FX has no weekend rates. Use the latest rate on or before the date and show its date.
- **Real exports are private.** Wealthsimple CSVs contain real financial data. They never go in the repo — tests use synthetic fixtures with made-up quantities. `.gitignore` blocks `*.csv` outside `backend/tests/fixtures/`.

---

## 7. Error Handling

- Services raise `LookupError` (missing entity) or `ValueError` (bad input/state); routers map to 404/400; upstream provider failures → 502.
- Importers never half-import: a batch is one DB transaction; unparseable rows are reported per row with the line number, and the batch status says so.
- MCP tools return `{"success": false, "error": "..."}` and never raise raw.
- Absence ≠ error: a missing price returns `null` with a reason, never a zero.

---

## 8. Logging

- Module loggers; outcomes INFO, degradations WARNING, failures ERROR with context (connection name, ticker, batch id).
- **Never log** secrets, quantities, amounts or account nicknames at INFO or above. `outbound_log` records tickers sent, nothing else from the portfolio.
- No `print` in request paths.

---

## 9. Database Conventions

- Every schema change = an Alembic migration (`render_as_batch=True`). Applied migrations are history: write a new one.
- `transaction` is **append-only**: no `UPDATE` of economic fields, no `DELETE`. Voids are flags plus a replacement row.
- Positions are not a table. If a cache is ever added, it has a rebuild function and a test proving rebuild == cache.
- `account` holds a nickname and a broker label, never a real account number (INV-8).
- Enums are small closed sets of lowercase strings (transaction types per spec: buy, sell, dividend, deposit, withdrawal, fee, split, transfer_in, transfer_out).

---

## 10. Testing Expectations

- pytest in `backend/tests/`; test the rules: buys, sells, splits, voids, fractional shares to four decimals, dedup, FX on/before date, two-level look-through sums.
- Each v1 feature's acceptance check (spec §v1 features) becomes at least one named test.
- Invariant tests are named `test_inv<N>_*` so `docs/invariants.md` can map them.
- CI (set up in T1) is the gate; tests never depend on a local `.env` or the network — providers are faked.
- The guardrail hook has its own tests: `python3 -m unittest discover -s .claude/hooks -p 'test_*.py'`.

---

## 11. Working Rules (from the spec, carried over from Anton)

- One build-plan task per subagent and per commit, run through `/orchestrate`. Small tasks → cheap model; Complex (T3, T8) → bigger model. The orchestrator reviews every diff against `docs/v1_spec.md` and `docs/invariants.md`.
- Briefs are written from the source files, not from a handover summary, and **name the invariants the task touches**.
- **Confirm with Musa before anything destructive or auth-related** (the guard hook asks on these).
- A change that breaks an invariant needs a recorded decision in `design_decisions.md` first.
- Reversing a decision: move it to Superseded in the same session and name the successor.
- Don't build roadmap or parked items early (spec §Roadmap). Reopening broker connectivity means revisiting D-1.

---

## 12. Documentation Standards

- Every session ends with a changelog entry at the top of `docs/changelog.md`: dated title, `[ADDED]/[CHANGED]/[REMOVED]/[BLOCKED]/[VERIFIED]`, what/why/how verified.
- `docs/project_state.md` refreshed when a task ships or a blocker changes.
- New MCP tools: the docstring is the LLM-facing contract (args, scope, side effects, that writes are proposals).

---

## Session Checklist

1. Suite green (count noted) and hook tests green.
2. Migration for any schema change.
3. Invariants touched are named in the commit body; `docs/invariants.md` guard column updated if a test now covers one.
4. Changelog entry; `project_state.md` refreshed; decisions recorded.
5. One commit per task, task-prefixed.

---

## 13. Invariants (one-liners — canonical text, owners and guards in `docs/invariants.md`)

- **INV-1** No broker credentials, no broker or aggregator API calls.
- **INV-2** Transactions are the source of truth; positions are derived, never edited.
- **INV-3** Secrets live only in the production `.env` (never committed); no client, Claude included, receives one.
- **INV-4** Market-data calls send tickers only.
- **INV-5** The app never places a trade.
- **INV-6** External clients cannot write to the ledger; they create proposals Musa confirms in the app.
- **INV-7** Every outbound integration is a registry row, can be switched off, and every call is logged.
- **INV-8** No real account numbers; accounts carry nicknames.
- **INV-9** Money and quantities are decimals with an explicit currency, never floats.

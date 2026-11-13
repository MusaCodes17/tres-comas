# Tres Comas — Project State

**Snapshot:** 2026-11-13. This is the perishable "what's true now" file. Refresh §2, §4 and §5 whenever a task ships or a blocker changes.

## 1. One-line state

T1–T4 and T6 done: scaffold, CI and deploy, schema, ledger and positions, F1 manual entry in the API and PWA, and the connection registry with its logged outbound choke point. T5 (Wealthsimple import) waits on the export header. The D-14 provider spike is parked: desk research done (`docs/spikes/price_provider.md`), live probe of EODHD and FMP to be run by Musa locally.

## 2. Status

| Area | State |
| --- | --- |
| Spec | `docs/v1_spec.md`, dated 13 Nov 2026 |
| Docs spine | Done (AGENTS.md, invariants, decisions, architecture, roadmap, changelog, handover template) |
| Guardrails | `.claude/hooks/pre_guard.py` wired in `.claude/settings.json`, with unit tests |
| Skills | Project skills in `.claude/skills/` |
| Code / CI / deploy | Skeletons, CI and deploy job (T1). Deploy skips until the box is set up and secrets are added (architecture §10) |
| Schema | Ten tables, migration `0001`, append-only triggers (T2) |
| Services | `ledger` (sole writer) and `positions` (derivation) (T3); `auth`, `accounts`, `securities` (T4) |
| API + PWA | Login, accounts, securities, transactions (add, void, correct), positions; every route default-deny (T4). Connections screen: switch on/off, outbound log (T6) |
| Registry | `app/connections/` is the only outbound HTTP; `boc_valet` seeded disabled (T6) |
| Test suite | Backend 287 passed; hook tests 16 passed; `vite build` clean |

## 3. Shipped

- 2026-11-13 — Spec committed; docs spine and guardrails.
- 2026-11-13 — T1 scaffold, CI and deploy job.
- 2026-11-13 — T2 schema (D-15 to D-18).
- 2026-11-13 — T3 ledger write path and position derivation (D-19 to D-22).
- 2026-11-13 — T4 auth, accounts and manual-entry PWA (D-23 to D-25).
- 2026-11-13 — T6 connection registry and outbound log (D-26 to D-28); P-3 decided as D-29.

## 4. Open questions and blockers

- **Docker image build unverified**: the build sandbox could not reach the Debian mirrors. The first deploy is the first real build.
- **Backups**: encrypted off-box backups are not built yet. Needed before real data goes in.
- **P-2 Market-data provider**: still open in the spec. Musa wants Canadian-market providers considered first. Desk research done; EODHD and FMP shortlisted. Live probe parked until Musa runs it locally (EODHD's key goes in the query string, which the cloud credential store can't inject). Blocks T7.
- **T5 needs the Wealthsimple activity export's header row** (column names only) plus a described buy, sell and dividend row with changed numbers, and whether USD trades show USD or CAD amounts (D-22).
- **Login on the box**: `TRES_COMAS_PASSWORD_HASH` must be added to the production `.env` (architecture §10 step 4) or login answers 503.
- **T5 check (D-22)**: confirm what currency Wealthsimple reports for USD-stock trades in the TFSA before importing.

## 5. Next priorities

1. **T5 Wealthsimple activity import** (Medium; dedup decided as D-29) as soon as Musa shares the header row.
2. **D-14 provider spike, phase 2** (parked): build the probe script, then Musa runs it locally against EODHD and FMP and P-2 is decided; then T7 prices and FX.
3. Musa: one-time box setup and GitHub deploy secrets (architecture §10); encrypted off-box backups before real data goes in.

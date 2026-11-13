# Tres Comas — Project State

**Snapshot:** 2026-11-13. This is the perishable "what's true now" file. Refresh §2, §4 and §5 whenever a task ships or a blocker changes.

## 1. One-line state

T1–T3 done: scaffold, CI and deploy job, the ten-table schema, and the ledger write path with derived positions. No API routes beyond `/health` yet; T4 (auth, accounts, manual form) is next.

## 2. Status

| Area | State |
| --- | --- |
| Spec | `docs/v1_spec.md`, dated 13 Nov 2026 |
| Docs spine | Done (AGENTS.md, invariants, decisions, architecture, roadmap, changelog, handover template) |
| Guardrails | `.claude/hooks/pre_guard.py` wired in `.claude/settings.json`, with unit tests |
| Skills | Project skills in `.claude/skills/` |
| Code / CI / deploy | Skeletons, CI and deploy job (T1). Deploy skips until the box is set up and secrets are added (architecture §10) |
| Schema | Ten tables, migration `0001`, append-only triggers (T2) |
| Services | `ledger` (sole writer) and `positions` (derivation) (T3) |
| Test suite | Backend 166 passed; hook tests 16 passed |

## 3. Shipped

- 2026-11-13 — Spec committed; docs spine and guardrails.
- 2026-11-13 — T1 scaffold, CI and deploy job.
- 2026-11-13 — T2 schema (D-15 to D-18).
- 2026-11-13 — T3 ledger write path and position derivation (D-19 to D-22).

## 4. Open questions and blockers

- **Docker image build unverified**: the build sandbox could not reach the Debian mirrors. The first deploy is the first real build.
- **Backups**: encrypted off-box backups are not built yet. Needed before real data goes in.
- **P-2 Market-data provider**: still open in the spec. Musa wants Canadian-market providers considered first. Resolved by the D-14 spike before T7; does not block T4–T6.
- **P-3, P-5**: proposals in `design_decisions.md` §C, each decided inside its task. P-5 (auth) needs Musa's confirmation.
- **T5 check (D-22)**: confirm what currency Wealthsimple reports for USD-stock trades in the TFSA before importing.

## 5. Next priorities

1. **T4 auth, accounts and manual form** (Medium; confirm P-5 auth with Musa). T5 (importer) and T6 (registry) are also unblocked; T6 is independent of both.
2. Musa: one-time box setup and GitHub deploy secrets (architecture §10); encrypted off-box backups before real data goes in.

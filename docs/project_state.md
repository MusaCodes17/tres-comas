# Tres Comas — Project State

**Snapshot:** 2026-11-13. This is the perishable "what's true now" file. Refresh §2, §4 and §5 whenever a task ships or a blocker changes.

## 1. One-line state

T1 and T2 done: scaffold, CI and deploy job, plus the ten-table schema with exact decimals and append-only transactions. No services yet; T3 (position derivation) is next.

## 2. Status

| Area | State |
| --- | --- |
| Spec | `docs/v1_spec.md`, dated 13 Nov 2026 |
| Docs spine | Done (AGENTS.md, invariants, decisions, architecture, roadmap, changelog, handover template) |
| Guardrails | `.claude/hooks/pre_guard.py` wired in `.claude/settings.json`, with unit tests |
| Skills | Project skills in `.claude/skills/` |
| Code / CI / deploy | Skeletons, CI and deploy job (T1). Deploy skips until the box is set up and secrets are added (architecture §10) |
| Schema | Ten tables, migration `0001`, append-only triggers (T2) |
| Test suite | Backend 34 passed; hook tests 16 passed |

## 3. Shipped

- 2026-11-13 — Spec committed; docs spine and guardrails.
- 2026-11-13 — T1 scaffold, CI and deploy job.
- 2026-11-13 — T2 schema (D-15 to D-18).

## 4. Open questions and blockers

- **Docker image build unverified**: the build sandbox could not reach the Debian mirrors. The first deploy is the first real build.
- **Backups**: encrypted off-box backups are not built yet. Needed before real data goes in.
- **P-2 Market-data provider**: still open in the spec. Musa wants Canadian-market providers considered first. Resolved by the D-14 spike before T7; does not block T2–T6.
- **P-3, P-4, P-5**: proposals in `design_decisions.md` §C, each decided inside its task. P-5 (auth) needs Musa's confirmation.

## 5. Next priorities

1. **T3 position derivation** (Complex, so a bigger model; decide P-4, average cost). T6 (registry and outbound log) is independent and could run alongside.
2. Musa: one-time box setup and GitHub deploy secrets (architecture §10); encrypted off-box backups before real data goes in.

# Tres Comas — Project State

**Snapshot:** 2026-11-13. This is the perishable "what's true now" file. Refresh §2, §4 and §5 whenever a task ships or a blocker changes.

## 1. One-line state

Pre-build. The v1 spec, docs spine and agent guardrails are in the repo; no application code exists.

## 2. Status

| Area | State |
| --- | --- |
| Spec | `docs/v1_spec.md`, dated 13 Nov 2026 |
| Docs spine | Done (AGENTS.md, invariants, decisions, architecture, roadmap, changelog, handover template) |
| Guardrails | `.claude/hooks/pre_guard.py` wired in `.claude/settings.json`, with unit tests |
| Skills | Project skills in `.claude/skills/` |
| Code / CI / deploy | Not started (T1) |
| Test suite | Hook tests only; app suite starts in T1 |

## 3. Shipped

- 2026-11-13 — Spec committed; docs spine and guardrails (T1 docs portion).

## 4. Open questions and blockers

- **P-2 Market-data provider** — still open in the spec. Musa wants Canadian-market providers considered first. Resolved by the D-14 spike before T7; does not block T1–T6.
- **P-1, P-3, P-4, P-5** — proposals in `design_decisions.md` §C, each decided inside its task. P-5 (auth) needs Musa's confirmation.

## 5. Next priorities

1. **T1 scaffold** when Musa says go: backend/frontend skeleton, Docker Compose, pytest, CI, push-to-main deploy to Hetzner. Confirm deploy target details with Musa (auth-related / outward-facing).
2. T2 schema, deciding P-1 (decimal storage).
3. T3 position derivation (Complex — bigger model).

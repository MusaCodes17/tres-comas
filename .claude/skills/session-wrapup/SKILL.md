---
name: session-wrapup
description: Use at the end of every working session, or when asked to wrap up. Runs the AGENTS.md Session Checklist so the changelog, project state, roadmap and decisions stay true.
---

# Session wrap-up

## Steps
1. **Suite green:** app tests (once T1 exists: `cd backend && python -m pytest -q`) and hook tests (`python3 -m unittest discover -s .claude/hooks -p 'test_*.py'`). Note both counts.
2. **Invariant review** (`invariant-review` skill) on the session's diff.
3. **Migration** exists for any schema change.
4. **Changelog** entry at the top of `docs/changelog.md`: dated title, branch, `[ADDED]/[CHANGED]/[REMOVED]/[BLOCKED]/[VERIFIED]`, what / why / how verified (counts, acceptance checks passed, manual ~380 px pass for UI).
5. **`docs/project_state.md`:** snapshot date, §2 status, §3 shipped, §4 blockers, §5 next priorities.
6. **`docs/roadmap.md`:** task status and commit.
7. **`docs/design_decisions.md`:** any P-* decided becomes a D-*; reversals go to Superseded naming the successor.
8. **`docs/invariants.md`:** guard column updated for any new `test_inv*`.
9. **Commit:** one per task, `t<N>:` prefix, invariants touched named in the body. Doc edits ride with the code they describe.
10. If work continues next session, fill `docs/handover_template.md` into the changelog entry or a task note.

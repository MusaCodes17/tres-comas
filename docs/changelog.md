# Tres Comas — Session Changelog

**Status / current focus:** see `docs/project_state.md`. This file is the append-only session log: newest entry at the top, dated title, `[ADDED]/[CHANGED]/[REMOVED]/[BLOCKED]/[VERIFIED]`, what / why / how verified.

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

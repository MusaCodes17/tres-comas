Pick up the next build-plan task.

1. Read `AGENTS.md`, `docs/project_state.md` §5 and the task's row in `docs/roadmap.md` §2. State the task in one sentence, with its dependencies and the invariants it touches.
2. Check every dependency is marked done. If not, stop and say which.
3. Check any pending decision (P-*) the task needs in `docs/design_decisions.md` §C. If it needs Musa (P-2 provider, P-5 auth), ask before writing code.
4. Load the matching skill from `.claude/skills/` (ledger → `ledger-write-path`, import/reconcile → `add-broker-importer`, providers/registry → `add-outbound-connection`, look-through/views → `look-through-exposure`, schema → `add-database-model`, MCP → `add-mcp-tool`).
5. Write the brief from the source files and the spec (not from a handover), naming the invariants. Confirm the plan with Musa before starting, then run it through `/orchestrate`: Small → cheap model, Complex (T3, T8) → bigger model.
6. Review the diff with `invariant-review`, then finish with `session-wrapup`.

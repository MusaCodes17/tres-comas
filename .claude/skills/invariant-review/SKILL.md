---
name: invariant-review
description: Use before committing any build-plan task, when reviewing a subagent's diff in /orchestrate, or when asked to check a change against the spec. Walks the diff through the nine invariants and the outbound privacy rules and reports pass/fail per rule.
---

# Invariant review

The orchestrator reviews every diff against the spec. This is that review, made repeatable.

## Steps
1. `git diff` (or the subagent's diff) and the task's row in `docs/roadmap.md` §2 — which invariants does it claim to touch? Check those first, then all nine.
2. For each, answer with evidence (file:line) — pass, fail, or not touched:
   - **INV-1** Any new host, SDK or import that reaches a broker or aggregator? Any credential field for one?
   - **INV-2** Any write to `transaction` outside `services/ledger`? Any UPDATE/DELETE of a transaction? Any stored position?
   - **INV-3** Any secret value in code, tests, fixtures, logs, API responses or MCP payloads? Did `.env*.example` gain a key name for each new secret?
   - **INV-4** Does any market-data or news call carry anything other than tickers / dates / company names?
   - **INV-5** Any order-placement concept at all?
   - **INV-6** Can any MCP tool or external route create, void or confirm a transaction?
   - **INV-7** Is every outbound call made through `connections.call`, with a registry row, an enabled check and an `outbound_log` row?
   - **INV-8** Any column, parser field or log line carrying an account number?
   - **INV-9** Any `float`, `Float`, `REAL`, JS `Number` arithmetic or `Decimal(<float>)` on money, quantity, rate or weight?
3. Outbound kinds: LLM payloads exclude nicknames and broker labels (D-9).
4. Scope: nothing from roadmap R2–R5 or Parked slipped in (spec §Roadmap).
5. Working rules: one task, one commit, suite green; auth/destructive changes were confirmed with Musa.
6. Report a short table: rule → pass/fail/not touched → evidence. Any fail blocks the commit unless a decision in `design_decisions.md` already covers it.

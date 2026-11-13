---
name: write-tests
description: Use when writing or reviewing pytest tests for Tres Comas — ledger rules, imports, providers, exposure, reconciliation or invariant guards. Tests rules not plumbing, uses synthetic data only and never touches the network.
---

# Write tests

## Required context
- `AGENTS.md` §10.
- `docs/invariants.md` (test naming and which invariants still say "planned").
- The spec acceptance check for the feature in hand (`docs/v1_spec.md` §v1 features).

## Rules
1. **Test the rule, name the boundary:** selling exactly the held quantity leaves 0 (not an error); selling 0.0001 more raises; FX on a Saturday uses Friday's rate and says so.
2. **Acceptance checks are tests.** Each of F1–F5 has a test whose name cites it (`test_f2_second_upload_adds_zero_rows`).
3. **Invariant tests** are named `test_inv<N>_<what>`; when one lands, update the Guard column in `docs/invariants.md`.
4. **Decimal assertions** compare `Decimal` to `Decimal("…")`, never `pytest.approx`.
5. **Synthetic data only.** Fixtures in `backend/tests/fixtures/` copy real headers and quirks with invented numbers. Never a real export, real nickname-to-number mapping or real balance.
6. **No network.** Providers are faked at the `connections` transport; a test that would reach the internet is a bug. No dependency on `.env` or test order (import-time env in `conftest.py`).
7. In-memory or temp-file SQLite per test; migrations applied, not `create_all`, for schema tests.

## Hook tests
`python3 -m unittest discover -s .claude/hooks -p 'test_*.py'` — add a case whenever a guard rule changes.

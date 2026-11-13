---
name: add-database-model
description: Use for any schema change — the ten v1 tables (T2) or later columns and tables. Covers Alembic migrations on SQLite, Decimal storage, append-only rules and the no-account-number rule.
---

# Add or change a database model

**Invariants:** INV-2, INV-8, INV-9. **Decisions:** D-5 (multi-account schema), D-11 (pair-keyed FX), P-1.

## Required context
- `AGENTS.md` §9 (Database Conventions) and the SQLite decimal trap in §6.
- `docs/architecture.md` §4 (the ten tables).

## Workflow
1. Model docstring states the **domain meaning** and the invariants it upholds.
2. Money / quantity / rate / weight columns use the project `DecimalText` TypeDecorator (P-1) — never `Float`, never bare `Numeric` on SQLite. Each money column has a sibling currency column or a documented fixed currency.
3. `account` has nickname, type, base currency, broker label, last reconciled date — **no account number** (INV-8).
4. `transaction` gets `voided_at` and `replaces_id` for corrections; no cascade deletes from `account` or `security` into it.
5. Uniques that carry idempotency: `import_batch.file_hash`; transaction natural key (P-3); `price(security_id, date, provider)`; `fx_rate(pair, date, provider)`; `etf_constituent(etf_id, underlying_id, as_of_date)`; `security(ticker, exchange)`.
6. Server-side stamps (`created_at`) via `server_default`; never client-supplied.
7. `alembic revision --autogenerate`, prune SQLite noise, check `render_as_batch=True`, and write a working `downgrade` for additive changes. Applied migrations are history (the guard asks).
8. Update `docs/architecture.md` §4 if a table or key field changes.

## Checklist
- [ ] Migration applies and downgrades cleanly on a fresh DB
- [ ] No `Float`; Decimal round-trip test to ≥ 8 dp
- [ ] No derived value stored as truth
- [ ] Architecture §4 updated

---
name: ledger-write-path
description: Use when adding or changing anything that creates, voids or corrects a transaction, adds a transaction type, or changes how positions are derived (T3, T4, and any confirm path from imports or proposals). Keeps one sanctioned writer and positions derived from transactions only.
---

# Ledger write path

**Invariants:** INV-2 (transactions are truth, positions derived), INV-9 (Decimal + currency), INV-6 (only the app confirms).

## Required context
- `AGENTS.md` §2, §6 (corrections, known traps), §9.
- `docs/v1_spec.md` §Data model (transaction types, derived values, corrections).
- `docs/design_decisions.md` P-1 (decimal storage), P-4 (average cost).

## Rules
1. **One writer.** Every transaction is born in `services/ledger.record_transaction(session, *, account_id, security_id, type, quantity, price, amount, currency, trade_date, source, import_batch_id=None)`. Manual entry (`source="manual"`), import (`"import"`) and confirmed proposals (`"proposal"`) all call it. Add a keyword argument; never write `Transaction(...)` anywhere else.
2. **Append-only.** No `UPDATE` of economic fields, no `DELETE`. A correction is `ledger.void_and_replace(old_id, **new_fields)`: sets `voided_at` on the old row and records a new row whose `replaces_id` points back. An adjustment is a new transaction.
3. **No position writes.** There is no positions table and no endpoint that sets a quantity. If a cache is added, it has `rebuild_positions()` and a test asserting rebuild equals cache.
4. **Decimal in, Decimal out.** Validate `quantity`, `price`, `amount` as `Decimal` constructed from strings; reject `float` with `TypeError`. Currency is required and ISO 4217.
5. **Type semantics** (state them in the docstring; test each):
   - buy: +quantity, cost += amount (incl. fees if the broker nets them).
   - sell: −quantity at average cost; realised gain = proceeds − avg_cost × qty. Selling more than held raises `ValueError`.
   - split: quantity × ratio, average cost ÷ ratio, total cost unchanged.
   - dividend, fee, deposit, withdrawal: cash only, no share change.
   - transfer_in / transfer_out: quantity moves with its cost basis.
   - Voided rows are ignored by derivation.
6. **Ordering.** Derive in `(trade_date, id)` order so same-day buys and sells are deterministic.
7. **Who commits.** `record_transaction` flushes; the caller (router, import batch, proposal confirm) owns the commit so an import batch is atomic.

## Tests (write-tests skill)
- F1 acceptance: the nine TFSA positions to four decimals.
- Fractional shares (e.g. 0.3127 VGRO) round-trip exactly.
- Void-and-replace leaves one effective row and full history.
- `test_inv2_positions_rebuild_from_transactions`, `test_inv9_rejects_float`.

## Common mistakes
- A second write path "just for imports".
- `Decimal(0.1)` from a float literal.
- Treating a sell of an unknown security as zero instead of an error.
- Editing a transaction in place to "fix a typo".

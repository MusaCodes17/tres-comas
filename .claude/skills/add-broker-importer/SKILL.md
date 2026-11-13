---
name: add-broker-importer
description: Use when building or changing a broker file adapter — the Wealthsimple activity statement (T5), the holdings report for reconciliation (T10), or a new broker later. Covers the adapter interface, dedup, privacy of real exports and account-number stripping.
---

# Add a broker importer

**Invariants:** INV-1 (files only, never a broker API), INV-2 (rows go through the ledger), INV-8 (no account numbers), INV-9 (Decimal). **Decisions:** D-2, D-7, C-1, P-3.

## Required context
- `AGENTS.md` §6 (idempotent import, real exports are private, ticker identity).
- `docs/architecture.md` §6 (CSV import and reconciliation flows).
- The `ledger-write-path` skill.

## The interface (D-7)
```python
class BrokerAdapter(Protocol):
    name: str                       # "wealthsimple"
    def sniff(self, header: list[str]) -> Literal["activity", "holdings"] | None: ...
    def parse_activity(self, rows: Iterable[dict[str, str]]) -> list[ParsedTransaction]: ...
    def parse_holdings(self, rows: Iterable[dict[str, str]]) -> list[ParsedHolding]: ...
```
Adapters **parse only**: no session, no DB, no network. They return dataclasses with `Decimal` fields, currency, ticker + exchange, a stable `natural_key`, and the source line number. Adding a broker = one new file in `importers/` registered in `importers/__init__.py`. The ledger never changes for a new broker.

## Workflow
1. Read the real export's **header row only** with Musa (or have Musa describe it). Never paste, commit or log real rows.
2. Build a **synthetic fixture** in `backend/tests/fixtures/<broker>/` that copies the header and quirks (date formats, sign conventions, currency columns, blank lines, footer rows) with invented quantities and amounts. The guard hook blocks CSVs anywhere else in the repo.
3. Map each row type to a transaction type; unknown types are reported, not guessed.
4. **Drop account-number columns** at parse time (INV-8); map the export's account to an `account` by nickname chosen at upload.
5. **Dedup (F2):** `import_batch.file_hash` makes a repeat file a no-op; each row's `natural_key` (P-3) makes overlapping date ranges add zero rows. Re-parsing never mutates existing transactions.
6. The import service wraps the whole batch in one DB transaction and calls `ledger.record_transaction(source="import", import_batch_id=...)` per new row. Batch status + row counts (parsed, new, duplicate, rejected) are stored.
7. Holdings reports (T10) feed `services/reconcile.diff(account, holdings)`: per-security quantity diff to 4 dp; clean → `last_reconciled_date`.

## Tests
- Same file twice → second import adds 0 rows.
- Overlapping range → only new rows added.
- Full synthetic history reproduces the manually entered positions (F2 acceptance).
- `test_inv8_importer_strips_account_numbers`.
- Deliberately wrong holdings quantity is flagged (F5 acceptance).

## Common mistakes
- Parsing amounts with `float()` or locale-dependent formatting (`"1,234.50"`).
- Matching securities on ticker alone (`MDA` vs `MDA.TO`).
- A "helpful" adapter that logs rows at INFO.

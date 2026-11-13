# Tres Comas — Invariants

**Last updated:** 2026-11-13. Source: `v1_spec.md` §Invariants.

These nine rules hold in every release. A change that breaks one needs a recorded decision in `design_decisions.md` **first**. Before changing code on an invariant's path, read its row and run its tests.

Columns: **Owner** is the code that upholds the rule (planned paths until built). **Guard** is what catches a break: a test, the pre-tool hook (`.claude/hooks/pre_guard.py`), CI, or "review only".

| ID | Rule | Owner (planned) | Guard |
| --- | --- | --- | --- |
| INV-1 | The app never holds broker credentials and never calls a broker or account-aggregator API. | `connections/` is the only outbound HTTP module; no provider of kind `broker` or `aggregator` exists. | Hook denies broker/aggregator hosts in code (`BROKER_HOST_RE`). Planned: `test_inv1_no_broker_connection_kinds`. |
| INV-2 | Transactions are the source of truth. Positions are always derived and never edited directly. | `services/ledger.py` (sole writer), `services/positions.py` (derivation). | Planned: `test_inv2_positions_rebuild_from_transactions`, `test_inv2_no_position_write_endpoint`. |
| INV-3 | Every secret lives app-side in the production `.env`, which is never committed. No client, Claude included, receives a secret. | `deploy/.env.production.example` (names only); registry stores `.env` key **names**. | Hook denies agent edits to any `.env*` except examples; `.gitignore`. Planned: `test_inv3_registry_never_returns_secret_values`. |
| INV-4 | Market-data calls send tickers only: never quantities, values, account names or cost basis. | `connections/client.py` scope check per kind. | Planned: `test_inv4_market_data_payload_is_tickers_only`; `outbound_log` viewable in-app. |
| INV-5 | The app never places a trade. It records trades made elsewhere. | No order/trade-placement code path exists. | Hook denies broker hosts; review. |
| INV-6 | External clients cannot write to the ledger. They can only create proposals that Musa confirms inside the app. | `mcp_server/` imports `services/proposals.create` only; confirm is a session-authenticated UI route. | Planned: `test_inv6_mcp_has_no_write_tools`, `test_inv6_token_scopes_exclude_write`. |
| INV-7 | Every outbound integration is a row in the connection registry, can be switched off there, and every call it makes is logged. | `connections/client.py`. | Planned: `test_inv7_disabled_connection_makes_no_call`, `test_inv7_every_call_logged`. Hook asks on raw HTTP imports outside `connections/`. |
| INV-8 | No real account numbers are stored. Accounts carry nicknames. | `account` model (no number column); importers drop account-number columns. | Planned: `test_inv8_importer_strips_account_numbers`. |
| INV-9 | Money and quantities are stored as decimals with an explicit currency, never as floats. | Decimal TypeDecorator (P-1); Pydantic schemas emit strings. | Hook asks on `Float`/`float(` in `backend/app/models` and `services`. Planned: `test_inv9_*` round-trip to 4+ dp. |

**Naming:** invariant tests are named `test_inv<N>_<what>` so this table can be checked with `grep -r "def test_inv" backend/tests`.

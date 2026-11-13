---
name: add-mcp-tool
description: Use when building the MCP endpoint, its tokens, the proposal inbox, or any MCP tool (T11). Claude may read and propose; it can never write the ledger.
---

# Add an MCP tool

**Invariants:** INV-6 (proposals only; Musa confirms in the app), INV-3 (no secret leaves), INV-7 (the MCP client is an inbound registry row), D-9 (no nicknames/broker labels in LLM-facing payloads where avoidable). **Constraint:** C-4 (public HTTPS).

## Required context
- `docs/v1_spec.md` §Claude surface (tool table, propose-and-confirm steps).
- `docs/architecture.md` §7.
- Anton's MCP conventions (thin adapters, `{"success": ...}` envelope, docstring is the contract).

## Rules
1. **Thin adapter over an existing service.** Read tools call the same functions as REST (`portfolio`, `positions`, `exposure`, `reconcile`, `proposals.list`).
2. **No write tools.** The only mutating tool is `propose_transactions`, which calls `services.proposals.create` and returns proposal ids. The guard hook denies importing `services.ledger` or `record_transaction` under `mcp_server/`.
3. **Scopes:** tokens are `read` or `read+propose`; there is no write scope. Check scope per tool; revoked or unknown token → 401. Record last use on the registry row.
4. **Payloads:** brief by default, `detail=True` for the full record, lists paged. Money as strings with currency; totals in CAD with the FX rate and date.
5. **Docstring for the model:** what it returns, args, paging, and for `propose_transactions` that nothing is recorded until Musa confirms in the app inbox.
6. Errors return `{"success": false, "error": "..."}`; never raise raw.
7. Auth on the endpoint is auth-related work — confirm design with Musa before building (guard asks on token/auth files).

## Tests
- `test_inv6_mcp_has_no_write_tools` (enumerate registered tools; only `propose_transactions` mutates, and only `proposal` rows).
- `test_inv6_token_scopes_exclude_write`; `read` token cannot call `propose_transactions`.
- Confirming a proposal is only reachable from a session-authenticated UI route.

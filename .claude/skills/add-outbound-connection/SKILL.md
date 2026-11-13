---
name: add-outbound-connection
description: Use whenever code will call anything outside the app — a price, FX, ETF-holdings, news or LLM provider — or when building the connection registry, outbound log or poller (T6, T7, T8, the D-14 provider spike). Enforces registry rows, scope checks, logging and tickers-only payloads.
---

# Add an outbound connection

**Invariants:** INV-1 (never a broker/aggregator), INV-3 (secrets in `.env`, registry stores key names), INV-4 (tickers only to market data), INV-7 (registry row, switchable, every call logged). **Decisions:** D-3, D-8, D-9, D-13, D-14.

## Required context
- `docs/architecture.md` §8 (outbound rules by kind) and §9 (integrations).
- `docs/v1_spec.md` §Connection registry and outbound privacy.

## Rules
1. **Allowed kinds only:** `market_data`, `news`, `llm` outbound; `mcp_client` inbound. Never `broker` or `aggregator` — the guard hook denies their hosts.
2. **All HTTP lives in `backend/app/connections/`.** Providers are `connections/providers/<name>.py`. Anywhere else, importing `requests`/`httpx` prompts the guard.
3. **The client is the choke point.** `connections.call(session, name, endpoint, *, tickers=(), params={})`:
   - loads the registry row; disabled → raises `ConnectionDisabled` and makes **no** call;
   - validates params against the kind's allowlist (market_data: tickers, date ranges, series ids; news: tickers, company names; llm: tickers, weights, amounts — never nicknames or broker labels);
   - reads the secret from `os.environ[row.secret_env_key]` at call time; never returns or logs it;
   - writes one `outbound_log` row (connection, timestamp, endpoint, tickers sent) whether the call succeeds or fails;
   - updates `last_used_at`.
4. **Callers pass tickers, not positions.** A poller computes the held-ticker set first and passes only that list.
5. **Graceful degradation.** Missing key or disabled row → "not configured" in the UI; prices fall back to the last known close with its date.
6. **Seed rows by migration or setup command,** never implicitly on first call.
7. **New secret:** add the key **name** to `deploy/.env.production.example` and the registry row; Musa adds the value on the box.

## Provider notes
- **Bank of Canada Valet (D-13):** `https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json` (and `FXZARCAD` later). No key. Rate is CAD per 1 USD. No weekend observations — use latest on or before.
- **Price/ETF provider (P-2):** chosen by the D-14 spike. The spike tests AAPL, GOOG, MDA.TO, NOK, NVDA, RKLB, VGRO, XEQT, XGRO plus VGRO/XEQT/XGRO holdings at two levels, records coverage, latency, price and terms in `docs/spikes/price_provider.md`, sends tickers only, and uses a temporary registry row.

## Tests
- `test_inv7_disabled_connection_makes_no_call` and `test_inv7_every_call_logged` with a faked transport.
- `test_inv4_market_data_payload_is_tickers_only`: a payload with a quantity or account nickname raises before sending.
- `test_inv3_registry_never_returns_secret_values`.
- No test touches the network.

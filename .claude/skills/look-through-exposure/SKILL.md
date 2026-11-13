---
name: look-through-exposure
description: Use when building or changing ETF constituent loading, two-level look-through, exposure by company/sector/currency, or the portfolio totals views (T8, T9, and R2 policy rules later). Covers funds-of-funds math, the "other" remainder and CAD conversion.
---

# Look-through exposure

**Invariants:** INV-2 (exposure is derived), INV-4 (constituent fetch sends the ETF ticker only), INV-9 (Decimal weights and values). **Decisions:** D-8, D-11, spec look-through note.

## Required context
- `docs/v1_spec.md` §v1 features F4 and the look-through note.
- `docs/architecture.md` §6 (look-through flow).
- `add-outbound-connection` skill for the constituent loader.

## Model
- `etf_constituent(etf_security_id, underlying_security_id, weight, as_of_date)`; weight is a `Decimal` fraction (0–1). Load from the provider endpoint; issuer files uploaded by hand are the fallback (D-8), parsed into the same table.
- VGRO, XEQT and XGRO are **funds of funds**: level 1 is the wrapper's underlying ETFs (e.g. a US total-market ETF), level 2 is their holdings.

## Algorithm
1. Positions (derived) × latest close × FX to CAD → market value per account × security, with each rate's date.
2. For each held ETF: `exposure[u] += value × w1(u)`. If `u` is itself an ETF with constituents, unpack once more: `exposure[v] += value × w1(u) × w2(v)`. Stop at two levels.
3. v1 may cap each fund to its top-N holdings; the unallocated weight becomes an explicit `"other (<fund>)"` bucket so every fund still sums to 100% of its value.
4. Direct holdings add at weight 1. Aggregate across all accounts.
5. Group by company (security identity = ticker + exchange; map cross-listings deliberately, not by ticker string), by sector, and by currency of the underlying.
6. Return the **split** per source: NVDA = direct + via VGRO + via XEQT + via XGRO (F4 acceptance), plus constituent as-of dates.

## Tests
- Two-level product: 1000 CAD of a wrapper holding 50% of an ETF that holds 6% NVDA → 30 CAD NVDA.
- Capped fund: shown holdings + "other" = fund value exactly (Decimal, no rounding drift).
- F4 acceptance on synthetic constituents for the nine TFSA tickers.
- Missing constituents → the ETF shows as itself with a "not unpacked" flag, never silently dropped.

## Common mistakes
- Float weights that sum to 0.9999999.
- Converting to CAD after aggregation across currencies.
- Unpacking more than two levels or recursing into cycles.
- Storing exposure as a table (it is derived).

# D-14 spike: price and ETF-holdings provider (P-2)

**Status:** Parked (2026-11-13). Phase 1 (desk research) done. Phase 2 (live probe) chosen for **EODHD and FMP** only, and parked until Musa can run it locally (see "Phase 2: how it will run").
**Date checked:** 2026-11-13. Prices change; re-check the live page before paying.

**Method and limits.** Desk research by web search. Fetching the providers' own pages (eodhd.com, twelvedata.com, financialmodelingprep.com, alphavantage.co) was blocked in the research environment (hosts not on the network allowlist), so every claim below comes from search-result summaries of the official pages or from third-party pages, and is labelled. Anything not seen on an official page is marked **unconfirmed**. Phase 2 and a manual read of each pricing page must settle these before any money is spent.

## Requirements (restated)

1. Daily close for AAPL, GOOG, NOK, NVDA, RKLB (US) and MDA, VGRO, XEQT, XGRO (TSX). Note the TSX ticker convention.
2. Holdings for VGRO, XEQT, XGRO (funds of funds) and for their underlying ETFs (e.g. VUN, VCN, XUS, ITOT): two-level look-through. Record full list vs top N, and weights.
3. Requests carry tickers, dates and an API key only (INV-4). Anything needing portfolio upload, account linking or brokerage login is disqualified (INV-1, D-3).
4. Retail or personal pricing: cheapest tier covering 1 and 2, free-tier limits, personal non-display terms, any ban on self-hosting or caching.
5. FX is solved by Bank of Canada Valet (D-13); only note whether the provider also has FX.

Excluded up front: unofficial scrapers (Yahoo Finance and the like, including wrappers around it). Reason: no licence, terms forbid automated access or redistribution, endpoints change without notice, and a registry row (INV-7) should name a provider with an agreement we can point to.

## Canadian sources

### TMX Group (TMX Datalinx / TMX Info Services)

- **Retail API:** none found. TMX sells market data to vendors and professionals under contract. A price list and a "Non-Professional Data Fee Cap (TSX Level 1)" exist for real-time data, but figures were not visible; no self-serve API key product found. Sources: https://tmxinfoservices.com/market-data/pricing-and-contract-documents ; https://tmxinfoservices.com/market-data/market-data-overview
- **Historical:** an online historical-data query tool shows a minimum charge of C$163.53/month (page undated, may be stale), single end user, no redistribution. Source: https://tmxinfoservices.com/corporate-reference-data/historical-data/tmx-historical-market-data-online-custom-queries . A web query tool is not an API and is outside our model.
- **Cloud API:** a "TMX Data Feed Cloud API Solution" exists (TSX, TSXV, MX futures); price unconfirmed, sales contact only. Source: https://tmxinfoservices.com/market-data/market-data-overview
- **ETF holdings:** none seen. Issuer files cover that (see fallback).
- **Verdict:** no retail-priced API. Not shortlisted. Confirmed only as "not found"; a quote request to Datalinx sales would be needed to be certain.

### QuoteMedia (Calgary)

- **TSX convention:** `:CA` suffix (e.g. `XEQT:CA`), per a search summary of QuoteMedia's symbol help. Source: https://client.quotemedia.com/qmc/quotetools/symbolHelp/SymbolHelp_US_Version_Default.html (unconfirmed for our nine tickers).
- **Retail:** "Quotestream Connect for Developers" is a self-service package for non-professional developers building personal, non-commercial apps: delayed streaming on 500 symbols plus delayed and end-of-day snap APIs; 10-year EOD history is an add-on. A QuoteMedia Developer Agreement must be requested from QuoteMedia first. Source: https://support.quotemedia.com/support/solutions/articles/13000091019-quotestream-connect-for-developers
- **Price:** not published; **unconfirmed**. Third-party figures ($17.95/mo on NexusFi, a $99.99 EODHD plan) are not tied to this product. Source for custom-quote model: https://datarade.ai/data-providers/quotemedia/profile
- **Holdings for ETFs:** not seen in the developer package; **unconfirmed**.
- **Auth/host:** API docs are behind a login; **unconfirmed**. Agreement-gated onboarding is also the opposite of a key-in-`.env` flow.
- **Verdict:** the only Canadian vendor with a personal-developer package, but price, holdings and auth are all unknown. Worth one email, not a live probe.

**Answer to "does a Canadian retail-priced API exist?"** Not one with published pricing and self-serve signup. QuoteMedia has a personal developer package behind an agreement and an unpublished price; TMX sells by contract. This agrees with D-14's note.

## Global providers

### EODHD (EOD Historical Data)

- **TSX convention:** `.TO` (e.g. `XEQT.TO`); US as `.US` (`AAPL.US`). Source: per-ticker pages such as https://eodhd.com/financial-summary/XIU.TO and https://eodhd.com/financial-summary/HEQT.TO (Canadian ETFs are listed).
- **Coverage of the nine:** claimed. US names and TSX listings (including Canadian ETFs like XIU.TO, HEQT.TO) appear on the site; the specific nine are **unconfirmed** until probed. https://eodhd.com/exchange/TO
- **ETF holdings:** the Fundamentals feed has an ETF template with `Top_10_Holdings` (code, exchange, `Assets_%` weight) and a `Holdings` section where available, plus `Holdings_Count`. Needs the Fundamentals package or higher. Sources: https://eodhd.com/financial-academy/financial-faq/fundamentals-glossary-etf ; https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds . Whether `Holdings` is full or only top 10 for VGRO/XEQT/XGRO and whether fund-of-fund constituents resolve to the underlying ETFs: **unconfirmed; the main phase 2 question**.
- **Cheapest qualifying tier:** Fundamentals, listed at $59.99/mo (monthly) per search summary of https://eodhd.com/pricing . EOD-only plan is $19.99/mo (annual about $199), which covers requirement 1 only. Promo pages show lower prices; the live page governs.
- **Free tier:** $0, 20 API calls/day, 1 year of EOD history. Credit costs: EOD 1, fundamentals 10, bulk 100+. https://eodhd.com/pricing
- **Terms (personal):** personal plans are for non-commercial use by one person; local storage of downloaded data is allowed; redistribution is not; no public dashboard or bot others can access. No separate licence needed for personal plans. Sources: https://eodhd.com/help/storage ; https://eodhd.com/help/personal-use ; https://eodhd.com/financial-apis/terms-conditions . A single-user self-hosted ledger fits. Full T&C text not read.
- **Auth:** query parameter `api_token` (from EODHD docs convention; **unconfirmed in this research**; verify). Fundamentals v1.1 path `/api/v1.1/fundamentals/{SYMBOL}`; EOD at `/api/eod/{SYMBOL}`.
- **Host:** `eodhd.com` (API under `/api/`).
- **FX:** yes (forex EOD). Not needed.

### Twelve Data

- **TSX convention:** **unconfirmed.** Plain symbol plus an exchange or MIC (`XTSE`) parameter is likely; no page seen confirming TSX is offered. https://twelvedata.com/docs/llms/reference-data.md
- **Coverage:** free Basic plan is US markets only; international markets come in with Grow/Pro/Ultra. Whether TSX is in Grow or higher: **unconfirmed**. https://twelvedata.com/pricing.md
- **ETF holdings:** `/etfs/world/composition` returns sector weights, country allocation, asset allocation and top holdings; **Ultra plan only**, 200 credits per request. Source: https://twelvedata.com/docs/llms/etfs/etf-composition.md . Ultra is $999/mo per a March 2026 update (earlier summaries show $329-$999; sources disagree). https://twelvedata.com/news/march-2026-updates
- **Cheapest qualifying tier:** Ultra, roughly $329-$999/mo. Far outside a personal budget.
- **Free tier:** Basic $0, 8 credits/min, 800/day, US only. https://support.twelvedata.com/en/articles/5615854-credits
- **Terms:** not read; **unconfirmed**.
- **Auth:** query param `apikey` or header `Authorization: apikey <key>` (**unconfirmed in this research**). **Host:** `api.twelvedata.com`.
- **FX:** yes.
- **Verdict:** holdings requirement fails on price. Possibly usable for prices only if Grow includes TSX.

### Financial Modeling Prep (FMP)

- **TSX convention:** `.TO` (**unconfirmed**; a TSX quotes endpoint exists but is marked legacy). https://site.financialmodelingprep.com/developer/docs/tsx-prices-api
- **Coverage:** Starter is US exchanges only; Premium extends to US, UK and Canada (seen for ETF symbol search and the actively-trading list; likely general). https://site.financialmodelingprep.com/developer/docs/pricing
- **ETF holdings:** `stable/etf/holdings?symbol=...` returns holdings by symbol. Plan entitlement, depth, weights and Canadian-ETF coverage: **unconfirmed**. https://site.financialmodelingprep.com/insights/enterprise/etf-and-mutual-fund-data-apis-for-holdings-and-performance
- **Cheapest qualifying tier:** Premium, about $59/mo (annual billing) per a third-party comparison; Starter about $22; Ultimate about $149. Official page figures **unconfirmed**. https://multiples.vc/compare/fmp-api-alternatives
- **Free tier:** "Basic", 250 calls/day, EOD data. https://site.financialmodelingprep.com/pricing-plans
- **Terms:** individual plans vs commercial plans exist (`planType=commercial`); personal-use wording **unconfirmed**.
- **Auth:** query param `apikey`. **Host:** `financialmodelingprep.com` (`/stable/...`).
- **FX:** yes.

### Alpha Vantage

- **TSX convention:** `.TO` per a 2017 third-party report; `.TRT` was the convention in older docs; both **unconfirmed** today. https://lists.gnucash.org/pipermail/gnucash-user/2017-November/072853.html
- **Coverage:** no confirmation TSX is covered; premium page speaks of US real-time and delayed data. https://alphavantage.co/premium
- **ETF holdings:** `ETF_PROFILE` returns holdings and sector allocation; all examples are US ETFs. Canadian ETF support **unconfirmed** and probably absent. https://glama.ai/mcp/servers/berlinbra/alpha-vantage-mcp/tools/get-etf-profile (third-party wrapper)
- **Cheapest tier:** premium from $49.99/mo (75 req/min); free tier 25 requests/day. https://qveris.ai/guides/alpha-vantage-pricing-alternative (third party)
- **Terms:** not read; **unconfirmed**.
- **Auth:** query param `apikey`. **Host:** `www.alphavantage.co` (`/query`).
- **FX:** yes.
- **Verdict:** TSX and ETF-holdings coverage both unproven. Lowest priority.

### Added candidate: Finnhub

- **TSX:** a dedicated "TSX & TSX Venture" end-of-day product at $49.99/month, billed quarterly, personal-use licence, 150 calls/min, 30+ years of daily OHLC. https://www.finnhub.io/tsx-end-of-day-level-1-data
- **ETF holdings:** separate ETF product at $500/mo or $1,000/mo, US coverage; global ETFs need advanced or enterprise plans. https://www.finnhub.io/pricing-etf-indices
- **Verdict:** useful as a prices-only option for TSX; holdings are out of budget and out of region. Ticker convention (likely `.TO`), auth (`token` param or `X-Finnhub-Token` header) and host (`finnhub.io`) **unconfirmed**. Not shortlisted for holdings.

## Comparison

| Provider | TSX convention | TSX prices | FoF holdings | Cheapest qualifying | Free tier | Personal / caching | Auth | Retail? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TMX Datalinx | n/a | contract | none seen | none retail (C$163.53/mo min, historical tool) | none | single end user, no redistribution | n/a | No |
| QuoteMedia | `:CA` | claimed | unconfirmed | unpublished | none seen | personal developer package | agreement, unconfirmed | Unclear |
| EODHD | `.TO` | claimed, TSX ETFs listed | `Top_10_Holdings` + `Holdings` (depth unconfirmed) | $59.99/mo Fundamentals (prices-only $19.99) | 20 calls/day, 1y | personal OK, storage OK, no redistribution | `api_token` query (unconfirmed) | Yes |
| Twelve Data | unconfirmed | unconfirmed | top holdings, Ultra only | roughly $329-$999/mo | 800/day, US only | unconfirmed | `apikey` query or header | Prices only |
| FMP | `.TO` unconfirmed | Premium tier | unconfirmed | about $59/mo Premium | 250/day | unconfirmed | `apikey` query | Yes |
| Alpha Vantage | unconfirmed | unconfirmed | US only seen | $49.99/mo | 25/day | unconfirmed | `apikey` query | Prices only |
| Finnhub | unconfirmed | TSX EOD product | $500+/mo, US | $49.99/mo (prices only) | unconfirmed for TSX | personal use | token (unconfirmed) | Prices only |

## Recommendation: live-test in phase 2

1. **EODHD** (Fundamentals tier, about $60/mo, or a one-month purchase; the free tier covers the price probe on 20 calls/day). Only candidate with Canadian ETF coverage, a holdings structure with weights, personal-use terms that allow storing data, and retail pricing. The question is whether `Holdings` is full for VGRO/XEQT/XGRO and resolves underlying ETFs.
2. **Financial Modeling Prep** (Premium tier, or free Basic for the price probe). Has an ETF holdings endpoint and Canada in Premium; entitlement and Canadian-ETF depth are the unknowns. Cheap to test.
3. **Twelve Data free tier or Finnhub TSX plan** (prices only). Twelve Data's free tier is enough to check whether TSX tickers resolve at all; Finnhub is the fallback prices source if EODHD and FMP disappoint. Choose Twelve Data first (no cost).

Not shortlisted: TMX (no retail API), QuoteMedia (send one email asking for developer price and ETF holdings; no probe unless answered), Alpha Vantage (coverage unproven).

**Holdings fallback (D-8).** If no provider returns usable fund-of-fund holdings (VGRO, XEQT, XGRO to underlying ETFs, and those to securities, weights summing to 100% with "other" remainder), use issuer files uploaded by hand: Vanguard Canada and BlackRock iShares Canada publish holdings files per fund. Prices alone would then come from the cheapest provider that passes the price probe. Issuer file URLs and formats are not researched yet.

## Phase 2: how it will run (decided 2026-11-13)

- **Providers:** EODHD and Financial Modeling Prep (Musa's pick). Twelve Data and Finnhub are not probed unless both disappoint.
- **Where:** on Musa's own machine, not in a cloud session. EODHD takes its key only as `?api_token=` in the query string (confirmed on eodhd.com's EOD API page), and the cloud session's credential store can inject keys only as headers. Musa sets `EODHD_API_KEY` and `FMP_API_KEY` in a local shell, runs the probe, and pastes back the coverage table. Keys never enter the repo, the chat or a cloud container (INV-3).
- **Still to build when unparked:** a small probe script that seeds two disabled registry rows in a throwaway SQLite file, enables them, sends requests only through `connections.call()` (query-param auth is already supported), and prints a coverage table with no key values. It can be built and tested with a faked transport before Musa's run.
- **Cloud environment:** a personal `tres-comas` environment now allows `eodhd.com` and `financialmodelingprep.com`, so public docs pages can be read from cloud sessions. No secrets are stored on it.

## Phase 2 plan (detail)

- Temporary registry row per provider, kind `market_data`, created **disabled**; Musa enables it for the probe and removes it after. Key name goes in `deploy/.env.production.example`; value only on the box (INV-3).
- Through `connections.call()` only (INV-7): the nine tickers (provider's TSX convention), then holdings requests for VGRO, XEQT, XGRO and their underlying ETFs (VUN, VCN, XUS, ITOT and whatever the first level returns). Payload: tickers, dates, key only (INV-4). Registry must support the provider's auth style (query param or header).
- Record per provider: coverage per ticker (found or not), latest close and date versus the broker/issuer page, latency, holdings depth (full or top N), weights present, weights sum, two-level resolution, rate-limit headers, errors.
- Output: fill this file with results, record the decision in `docs/design_decisions.md` (resolves P-2), then delete or archive the spike per AGENTS.md section 3.

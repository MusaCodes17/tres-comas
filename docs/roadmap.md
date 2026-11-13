# Tres Comas — Roadmap

**Last updated:** 2026-11-13. Source: `v1_spec.md`. **Maintenance:** when a task ships, set its status here, add the commit, and move it into `project_state.md` §3.

**Naming:** build-plan tasks are `T1`–`T11`, commit prefix `t<N>:` (e.g. `t3: position derivation`). Releases after v1 are `R2`–`R5`, prefix `r<N>:`. Spikes are `spike:`.

---

## 1. v1 Features

Each feature is done when its acceptance check passes as a named test (or recorded manual check).

| ID | Feature | Acceptance check | Tasks |
| --- | --- | --- | --- |
| F1 | Accounts and manual entry — create an account, add/void/correct transactions from a phone-friendly form. | The nine TFSA positions held on 13 Nov 2026 (AAPL, GOOG, MDA.TO, NOK, NVDA, RKLB, VGRO, XEQT, XGRO) can be entered and show the same share counts to four decimals. | T3, T4 |
| F2 | Wealthsimple CSV import — activity statement rows become transactions; no duplicates on re-upload or overlap. | Full TFSA history reproduces the manual positions. Second upload of the same file adds zero rows. | T5 |
| F3 | Daily prices and FX — scheduled poll for every held ticker and USD/CAD. | Every held security has a close for the last trading day. Value shown in CAD with rate and date visible. | T6, T7 |
| F4 | Look-through exposure — per company, sector, currency, ETFs unpacked. | NVDA shows direct + via VGRO, XEQT, XGRO as one number with the split visible. | T8, T9 |
| F5 | Reconciliation — diff a holdings report against derived positions. | A deliberately wrong quantity is flagged; a clean report sets last reconciled date. | T10 |

## 2. Build Plan

Eleven tasks, each one subagent and one commit, run through `/orchestrate`. T1 and T2 done; T3 next (T6 is also unblocked).

| Task | What | Size | Depends on | Invariants touched | Status |
| --- | --- | --- | --- | --- | --- |
| T1 | Repo scaffold, Docker Compose, test runner, CI, push-to-main deploy; docs spine (done early, 2026-11-13) | Small | — | INV-3 | Done 2026-11-13 (box setup pending) |
| T2 | Schema and migrations for the ten tables (decided D-15–D-18) | Small | T1 | INV-2, INV-8, INV-9 | Done 2026-11-13 |
| T3 | Position derivation, tests for buys, sells, splits, voids, fractional shares (decide P-4) | Complex | T2 | INV-2, INV-9 | Not started |
| T4 | Auth, account CRUD, manual transaction form (F1) (confirm P-5 with Musa) | Medium | T3 | INV-2, INV-3, INV-8 | Not started |
| T5 | Importer interface + Wealthsimple activity adapter with dedup (F2) (decide P-3) | Medium | T3 | INV-1, INV-2, INV-8, INV-9 | Not started |
| T6 | Connection registry and outbound log | Small | T2 | INV-3, INV-4, INV-7 | Not started |
| — | **Spike (D-14):** 2–3 price providers vs nine tickers + three funds of funds (decide P-2) | Small | T6 | INV-4 | Not started |
| T7 | Price and FX poller on a schedule, through the registry (F3) | Medium | T6, spike | INV-4, INV-7, INV-9 | Not started |
| T8 | ETF constituent loader and two-level look-through (F4) | Complex | T7 | INV-4, INV-9 | Not started |
| T9 | Exposure and portfolio views | Medium | T8 | INV-2, INV-9 | Not started |
| T10 | Holdings-report parser and reconciliation diff (F5) | Medium | T5 | INV-2, INV-8 | Not started |
| T11 | MCP endpoint, tokens and the proposal inbox | Medium | T9 | INV-3, INV-6, INV-7 | Not started |

## 3. Releases after v1

Each started only when the need is felt in real use.

1. **R2 — Policy rules.** A written cap on any single company including look-through, and on total single-stock share. Exposure view flags breaches in bands (like Anton's 600/700/800 km thresholds).
2. **R3 — Event inbox.** Earnings dates, large moves and news for held securities, each with a short summary to confirm or dismiss.
3. **R4 — Decision journal.** A thesis per position and its sell trigger, written in advance; every buy and sell logged with its reason and reviewed later.
4. **R5 — Scheduled briefs.** Weekly portfolio review and a brief before each holding's earnings.

Also planned without a release number: **RRSP account** (D-12) right after the TFSA works end to end; **ZAR accounts** (D-11) later.

## 4. Parked

- Backtesting, signal generation and valuation models.
- Chequing, budgeting and net-worth views (schema ready, nothing built).
- Tax-lot tracking, until a taxable account is added.
- Push notifications, until R3 shows they are needed.
- Any broker API, including Wealthsimple's planned AI access. Reopening this means revisiting D-1.

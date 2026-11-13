# Tres Comas — Design Decisions

**Last updated:** 2026-11-13. Constraints and decisions D-1–D-14 were made on 13 Nov 2026 and come from `v1_spec.md`. Pending items (P-*) need Musa's call or a spike before the task that depends on them.

Lifecycle: a new decision gets the next D-number. Reversing one moves it to **Superseded** in the same session, naming its successor. Invariants live in `invariants.md`; breaking one requires a decision here first.

---

## A. Constraints (outside facts that shape the design)

| ID | Constraint |
| --- | --- |
| C-1 | Wealthsimple exports are manual and web-only: a holdings report (CSV) and a custom activity statement (CSV), both under Documents. |
| C-2 | The first account is a TFSA. Gains are not taxed, so tax-lot features have no use there. |
| C-3 | Holdings are in CAD and USD, so every total needs an FX rate and a base currency. |
| C-4 | Claude's mobile and web connectors call from Anthropic's cloud, so an MCP endpoint must be public HTTPS. |
| C-5 | Single user. No roles, sharing or multi-tenant concerns. |

## B. Decisions

| ID | Decision | Why |
| --- | --- | --- |
| D-1 | No broker connectivity of any kind. | Broker-agnostic, and no real account credentials to expose. |
| D-2 | Data enters by manual entry or CSV upload. | Trades are infrequent, and a ledger owned by the app outlives any broker. |
| D-3 | Outbound connections are market-data and news providers only, never account aggregators. | They need tickers, not account data. |
| D-4 | Decision support runs inside the app with Musa's own Anthropic API key. The MCP endpoint is a second surface, not a dependency. | The app stays self-contained. |
| D-5 | The schema is multi-account from day one. Only investment accounts are built in v1. | Grows into an all-accounts tracker without a migration; nothing built ahead of need. |
| D-6 | Separate repo and service on the Hetzner box, following Anton's stack and docs conventions. | Known deployment path and working habits. |
| D-7 | Importers are per-broker adapters behind one interface. Wealthsimple is the first. | Adding a broker means adding a parser, not changing the ledger. |
| D-8 | ETF holdings come from a provider endpoint, with issuer files uploaded by hand as the fallback. | The call sends only the ETF's ticker (inside INV-4). Coverage of Canadian funds of funds must be proven first (D-14). |
| D-9 | LLM analysis may see both portfolio weights and dollar amounts. Account nicknames and broker labels are never sent. | Musa's call; amounts make the analysis more useful. |
| D-10 | The UI is a PWA like Anton, with its own login. | Financial data stays behind a separate credential. |
| D-11 | CAD is the base currency for every total. ZAR accounts may be added later. | `fx_rate` is keyed by currency pair, so ZAR needs no schema change. |
| D-12 | The RRSP is the second account after the TFSA. | Musa's priority. |
| D-13 | FX rates come from the Bank of Canada Valet API: official daily rates, no key, USD and ZAR against CAD. | A Canadian public source, and one less secret to hold. |
| D-14 | Before T7, a short spike tests two or three price providers against the nine held tickers and the three funds of funds, then one is chosen. | No retail-priced Canadian stock-price provider was found; TSX coverage and ETF holdings must be checked on real tickers. |

**Naming.** The project and repo are Tres Comas. "Son of Anton" is the umbrella for all of Musa's AI tools; each tool takes a name from the same show.

## C. Pending (P-*) — proposed, not yet decided

| ID | Question | Proposal | Needed by |
| --- | --- | --- | --- |
| P-1 | How are decimals stored in SQLite (INV-9)? SQLite has no decimal type and SQLAlchemy `Numeric` loses precision there. | A `Decimal` TypeDecorator stored as canonical TEXT; arithmetic only in Python `Decimal`. Pydantic emits strings. | T2 |
| P-2 | Which market-data provider for prices (TSX + US)? Musa asked to look at providers within the Canadian market first. | Run the D-14 spike: shortlist 2–3, test all nine tickers + VGRO/XEQT/XGRO holdings, record results in `docs/spikes/price_provider.md`, then decide. | T7 |
| P-3 | Natural key for Wealthsimple activity-row dedup. | Hash of (account, trade date, type, security, quantity, net amount, currency) plus the file hash on `import_batch`; confirm against a real export's columns during T5. | T5 |
| P-4 | Average-cost method for derived positions. | Weighted average cost per account and security in native currency; sells reduce quantity at average cost; splits scale quantity and cost per share. Tax lots parked (C-2). | T3 |
| P-5 | Auth mechanism for the PWA's own login (D-10). | Mirror Anton: single-user password + session cookie, default-deny middleware, named bearer tokens for MCP with `read` / `read+propose` scope. Confirm with Musa (auth-related). | T4 |

## D. Superseded

None yet.

## E. Debt list

None yet.

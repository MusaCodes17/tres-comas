# Tres Comas: v1 Spec

Nov 13, 2026 · @Musa Souled

## Purpose and scope

v1 is a self-hosted ledger of every investment account, entered by hand or by CSV, that shows true exposure across accounts. It has no connection to any broker.

**In scope for v1**

- Accounts, transactions and derived positions for investment accounts (first: the Wealthsimple TFSA).
- Manual entry and a Wealthsimple CSV importer.
- Daily prices and FX from one market-data provider.
- Look-through exposure: what is owned in total once ETFs are unpacked.
- Reconciliation of the ledger against a broker holdings report.

**Out of scope for v1**

- Any broker login, API or account aggregator.
- Trade execution. Buys and sells happen in the broker app and are recorded here afterwards.
- Price prediction, signals and backtesting.
- Chequing, budgeting and non-investment accounts. The schema allows them; nothing is built for them yet.

## Invariants

These nine rules hold in every release. A change that breaks one needs a recorded decision first.

| ID | Rule |
| --- | --- |
| INV-1 | The app never holds broker credentials and never calls a broker or account-aggregator API. |
| INV-2 | Transactions are the source of truth. Positions are always derived and never edited directly. |
| INV-3 | Every secret lives app-side in the production `.env`, which is never committed. No client, Claude included, receives a secret. |
| INV-4 | Market-data calls send tickers only: never quantities, values, account names or cost basis. |
| INV-5 | The app never places a trade. It records trades made elsewhere. |
| INV-6 | External clients cannot write to the ledger. They can only create proposals that Musa confirms inside the app. |
| INV-7 | Every outbound integration is a row in the connection registry, can be switched off there, and every call it makes is logged. |
| INV-8 | No real account numbers are stored. Accounts carry nicknames. |
| INV-9 | Money and quantities are stored as decimals with an explicit currency, never as floats. |

## Constraints and decisions

Five outside constraints shape the design, and seven decisions were made on 13 Nov 2026.

**Constraints**

| ID | Constraint |
| --- | --- |
| C-1 | Wealthsimple exports are manual and web-only: a holdings report (CSV) and a custom activity statement (CSV), both under Documents. [Wealthsimple Help](https://help.wealthsimple.com/hc/en-ca/articles/35654428540571) |
| C-2 | The first account is a TFSA. Gains are not taxed, so tax-lot features have no use there. |
| C-3 | Holdings are in CAD and USD, so every total needs an FX rate and a base currency. |
| C-4 | Claude's mobile and web connectors call from Anthropic's cloud, so an MCP endpoint must be public HTTPS. |
| C-5 | Single user. No roles, sharing or multi-tenant concerns. |

**Decisions**

| ID | Decision | Why |
| --- | --- | --- |
| D-1 | No broker connectivity of any kind. | Broker-agnostic, and no real account credentials to expose. |
| D-2 | Data enters by manual entry or CSV upload. | Trades are infrequent, and a ledger owned by the app outlives any broker. |
| D-3 | Outbound connections are market-data and news providers only, never account aggregators. | They need tickers, not account data. |
| D-4 | Decision support runs inside the app with Musa's own Anthropic API key. The MCP endpoint is a second surface, not a dependency. | The app stays self-contained. |
| D-5 | The schema is multi-account from day one. Only investment accounts are built in v1. | The tool can grow into an all-accounts tracker without a migration, and nothing is built ahead of felt need. |
| D-6 | Separate repo and service on the Hetzner box, following Anton's stack and docs conventions. | Known deployment path and working habits. |
| D-7 | Importers are per-broker adapters behind one interface. Wealthsimple is the first. | Adding a broker means adding a parser, not changing the ledger. |

**Decisions from the answered open questions**

| ID | Decision | Why |
| --- | --- | --- |
| D-8 | ETF holdings come from a provider endpoint, with issuer files uploaded by hand as the fallback. | The call sends only the ETF's ticker, so it stays inside INV-4. Coverage of Canadian funds of funds has to be proven first. |
| D-9 | LLM analysis may see both portfolio weights and dollar amounts. Account nicknames and broker labels are still never sent. | Musa's call; amounts make the analysis more useful. |
| D-10 | The UI is a PWA like Anton, with its own login. | Financial data stays behind a separate credential. |
| D-11 | CAD is the base currency for every total. ZAR accounts may be added later. | The `fx_rate` table is keyed by currency pair, so ZAR needs no schema change. |
| D-12 | The RRSP is the second account after the TFSA. | Musa's priority. |
| D-13 | FX rates come from the Bank of Canada's [Valet API](https://www.bankofcanada.ca/valet/docs): official daily rates, no key, and it publishes both USD and ZAR against CAD. | A Canadian public source, and one less secret to hold. |
| D-14 | Before T7, a short spike tests two or three price providers against the nine held tickers and the three funds of funds, then one is chosen. | No retail-priced Canadian stock-price provider was found, so TSX coverage and ETF holdings must be checked on real tickers. |

**Naming.** The project and repo are called Tres Comas. "Son of Anton" is the umbrella name for all of Musa's AI tools, and each tool takes a name from the same show.

## Architecture

One service on the Hetzner box owns the ledger and every connection, and the broker sits outside it with no link.

&#91;embedded content: architecture · one app, three connections, no broker link\]

Musa is the only path between the broker and the app. Two connections go out and one comes in, each through the registry.

- **Deployment:** its own Docker Compose service beside Anton, with the production `.env` as the source of truth for config and secrets.
- **Primary surface:** a phone-friendly web UI for entry, upload, exposure and the proposal inbox.
- **Second surface:** a public HTTPS MCP endpoint for Claude, read and propose only.
- **Data path:** the backend polls providers on a schedule. No LLM sits between the app and its data.

## Data model

Ten tables: the ledger is `account`, `security` and `transaction`, and everything else is market data, imports or control.

| Table | Holds | Key fields |
| --- | --- | --- |
| `account` | One row per real-world account | nickname, type (TFSA, RRSP, non-registered, cash), base currency, broker label, last reconciled date |
| `security` | Anything that can be held | ticker, exchange, currency, kind (stock, ETF, cash) |
| `transaction` | Every ledger event, append-only | account, security, type, quantity, price, amount, currency, trade date, source (manual, import, proposal), import batch |
| `price` | Daily close per security | security, date, close, currency, provider |
| `fx_rate` | Daily rate per currency pair | pair, date, rate, provider |
| `etf_constituent` | What each ETF holds, for look-through | ETF, underlying security, weight, as-of date |
| `import_batch` | One row per uploaded file | account, broker adapter, file hash, row counts, status |
| `proposal` | Changes suggested by an external client, awaiting confirmation | payload, origin, status (pending, confirmed, dismissed) |
| `connection` | The registry of outbound integrations | see Connection registry |
| `outbound_log` | One row per outbound call | connection, timestamp, endpoint, tickers sent |

**Transaction types:** buy, sell, dividend, deposit, withdrawal, fee, split, transfer in, transfer out.

**Derived, never stored as truth:** positions (quantity and average cost per account and security), market value, gain and loss, exposure. A cache is allowed if it can be rebuilt from transactions alone.

**Corrections** are new transactions or a voided-and-replaced pair, so history stays auditable.

## v1 features

v1 ships five features. Each is done when its acceptance check passes.

| ID | Feature | Acceptance check |
| --- | --- | --- |
| F1 | **Accounts and manual entry.** Create an account, then add, void and correct transactions from a form that works on a phone. | The nine TFSA positions held on 13 Nov 2026 (AAPL, GOOG, MDA.TO, NOK, NVDA, RKLB, VGRO, XEQT, XGRO) can be entered and show the same share counts to four decimals. |
| F2 | **Wealthsimple CSV import.** Upload an activity statement; rows become transactions. Re-uploading the same file or an overlapping date range creates no duplicates. | Importing the full TFSA activity history reproduces the manually entered positions. A second upload of the same file adds zero rows. |
| F3 | **Daily prices and FX.** The backend polls one provider on a schedule for every held ticker and for USD/CAD. | Every held security has a close for the last trading day. Portfolio value is shown in CAD with the rate and its date visible. |
| F4 | **Look-through exposure.** Show total exposure per underlying company, sector and currency across all accounts, with ETFs unpacked into their holdings. | NVDA exposure shows the direct position plus the share held through VGRO, XEQT and XGRO as one number, with the split visible. |
| F5 | **Reconciliation.** Upload a broker holdings report; the app diffs it against derived positions and lists mismatches per security. | A deliberately wrong quantity is flagged. A clean report sets the account's last reconciled date. |

**Look-through note.** VGRO, XEQT and XGRO are funds of funds, so unpacking takes two levels: the wrapper's underlying ETFs, then their holdings. v1 may cap this at the largest holdings per fund and show the remainder as "other".

## Connection registry and outbound privacy

Nothing leaves the app except through a registry row that Musa created and can switch off.

**Each connection records**

- Name and kind (market data, news, LLM, MCP client).
- Direction: outbound call from the app, or inbound client of the app.
- Scope: exactly which fields may be sent or read.
- Where its secret lives (an `.env` key name, never the value).
- Enabled flag, created date, last used.

**Outbound rules by kind**

| Kind | May send | Never sends |
| --- | --- | --- |
| Market data | Tickers, date ranges | Quantities, values, account names |
| News | Tickers, company names | Quantities, values, account names |
| LLM analysis | Tickers, portfolio weights and dollar amounts | Account nicknames, broker labels |

**Inbound rules**

- An MCP client holds an app-issued token with scope `read` or `read+propose`. There is no write scope.
- Tokens are revocable from the registry and show their last use.

**Protecting the data at rest**

- Auth on every route, including read-only ones.
- Encrypted off-box backups.
- The outbound log is viewable in the app, so any call can be checked against INV-4.

## Claude surface

Claude reads the ledger and proposes changes through an MCP endpoint; it never writes. This is the last v1 task and the app works without it.

| Tool | Does | Scope |
| --- | --- | --- |
| `get_portfolio` | Totals per account and overall, in base currency | read |
| `get_position` | One security: quantity, cost, value, gain, recent transactions | read |
| `get_exposure` | Look-through exposure by company, sector or currency | read |
| `get_reconciliation_status` | Last reconciled date and open mismatches per account | read |
| `propose_transactions` | Creates pending proposals from parsed trades or a screenshot | read+propose |
| `list_proposals` | Pending proposals and their status | read |

Read tools return brief results by default and take `detail=True` for the full record, as in Anton. Lists are paged.

**Propose and confirm**

1. Musa makes a trade in the broker app.
2. He tells Claude, or shares a screenshot or CSV.
3. Claude calls `propose_transactions` with one row per trade.
4. The proposals appear in the app's inbox, one line each.
5. Musa confirms or dismisses them in the app. Only then does a transaction exist.

## Roadmap and parked items

Four releases follow v1, each started only when the need is felt in real use.

1. **R2: Policy rules.** A written cap on any single company including look-through, and on total single-stock share. The exposure view flags breaches in bands, like Anton's 600/700/800 km thresholds.
2. **R3: Event inbox.** Earnings dates, large moves and news for held securities, each with a short summary to confirm or dismiss.
3. **R4: Decision journal.** A thesis per position and what would trigger a sale, written in advance. Every buy and sell is logged with its reason and reviewed later.
4. **R5: Scheduled briefs.** A weekly portfolio review and a brief before each holding's earnings.

**Parked**

- Backtesting, signal generation and valuation models.
- Chequing, budgeting and net-worth views (schema ready, nothing built).
- Tax-lot tracking, until a taxable account is added.
- Push notifications, until R3 shows they are needed.
- Any broker API, including Wealthsimple's planned AI access. Reopening this means revisiting D-1.

## Build plan

Eleven tasks, each sized for one subagent and one commit, run through `/orchestrate`.

| Task | What | Size | Depends on |
| --- | --- | --- | --- |
| T1 | Repo scaffold, Docker Compose, test runner, docs spine (invariants, decisions, constraints, roadmap, changelog, handover template) | Small | none |
| T2 | Schema and migrations for the ten tables | Small | T1 |
| T3 | Position derivation from transactions, with tests for buys, sells, splits, voids and fractional shares | Complex | T2 |
| T4 | Auth, account CRUD and the manual transaction form (F1) | Medium | T3 |
| T5 | Importer interface and the Wealthsimple activity-statement adapter with dedup (F2) | Medium | T3 |
| T6 | Connection registry and outbound log | Small | T2 |
| T7 | Price and FX poller on a schedule, through the registry (F3) | Medium | T6 |
| T8 | ETF constituent loader and two-level look-through (F4) | Complex | T7 |
| T9 | Exposure and portfolio views | Medium | T8 |
| T10 | Holdings-report parser and reconciliation diff (F5) | Medium | T5 |
| T11 | MCP endpoint, tokens and the proposal inbox | Medium | T9 |

**Working rules, carried over from Anton**

- Small tasks go to the cheap model. Complex tasks get a bigger model. The orchestrator reviews every diff against this spec.
- One commit per task, with the suite green.
- Briefs are written from the source files, not from a handover summary.
- Each task's brief names the invariants it touches.
- Confirm with Musa before anything destructive or auth-related.
- Push-to-main deploy to Hetzner is set up in T1, so it never becomes a manual habit.

## Open questions

Seven answers are needed before T1; the first three change the design.

- [ ] Which market-data provider for prices and FX? It must cover both TSX and US tickers. - let’s look at any providers within the Canadian market
- [x] Where do ETF holdings come from: issuer files uploaded by hand, or a provider endpoint? - provider endpoint if it doesn’t risk security guardrails in place
- [x] Should LLM analysis default to weights only, or may it see dollar amounts? - weights but it can also see dollar amounts
- [x] What is the project and repo name? - let’s workshop this, I like “Son of Anton” to be all inclusive of all my AI stuff so it needs to fall along these lines
- [x] Is the UI a PWA like Anton, and does it share Anton's login or have its own? - yes, pwa like Anton but has its own login
- [x] Is CAD the base currency for every total? - yes, CAD. if all is good, I’m planning to add ZAR accounts in the future so I have an overall picture but this may come at a later stage
- [x] Which account comes after the TFSA? - RRSP is the next best account to look into

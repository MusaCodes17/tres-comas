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
| D-15 | Decimals (money, quantities, rates, weights) are stored as exact plain-notation TEXT via `app.models.types.DecimalText`, which refuses float, bool, NaN and infinity. All arithmetic happens in Python. (Was P-1; Musa, 13 Nov 2026, during T2.) | SQLite has no decimal type and `Numeric` rounds through float. The cost is that SQL can't `SUM`/`ORDER BY` these columns, which is acceptable at personal scale. |
| D-16 | The database enforces append-only on `transactions` with two triggers in migration 0001: no `DELETE`, and no `UPDATE` except setting `voided_at` once. (Musa, T2.) | A second barrier under the ledger service for INV-2. A future migration that rebuilds `transactions` must re-create both triggers. |
| D-17 | Registry `connections` rows default to `enabled = false`. (Musa, T2.) | Adding a provider never sends a request by itself (INV-7). |
| D-18 | Table names are plural snake_case (`accounts`, `transactions`, …); the spec's singular names map one to one. | Anton convention, and it avoids the SQL keyword `transaction`. |
| D-19 | Average cost is weighted average per account and security, in the security's own currency. A buy adds its amount (fees included) to total cost; a sell or transfer_out removes cost proportionally (`C × qty / held`, so a full sell leaves exactly 0) and only a sell records realised gain; a split multiplies quantity by `split_ratio` and leaves total cost unchanged. No rounding in derivation. (Was P-4; Musa, T3.) | Matches Canadian adjusted cost base. Tax lots stay parked (C-2). |
| D-20 | The ledger refuses, at write time, any new row, void or replacement that would make a position negative on any date (it replays the affected account × security first). Derivation raises if it ever meets one. (Musa, T3.) | Back-dated entries can't silently break later sells; derived views never show negative holdings. |
| D-21 | Positions are securities only in v1; cash balances are not derived. (Musa, T3.) | D-5: nothing built ahead of need. Revisit in T9/T10 if the holdings report or portfolio view needs cash. |
| D-22 | Position-affecting rows must be in the security's currency, and one position never mixes currencies. A `natural_key` is unique across all rows, voided ones included, and the ledger checks it before writing. (T3.) | Keeps cost in one native currency. **T5 check:** if Wealthsimple reports CAD amounts for USD stocks, decide how to carry FX before importing. A corrected import row needs a new key. |
| D-23 | The app's own login is a single password. Its scrypt hash (`scrypt$n$r$p$salt$hash`, stdlib only) lives only in the production `.env` as `TRES_COMAS_PASSWORD_HASH`, made with `backend/hash_password.py`; unset means login answers 503, never an open app. Sessions are server-side rows in `auth_sessions` (sha256 of the token only) behind an HttpOnly, Secure, SameSite=Strict `tc_session` cookie. Every route is default-deny via an app-level dependency; only `/health` and `/api/auth/login` are public, and the OpenAPI/docs routes are off. Five failed logins in 15 minutes give 429. (Was P-5; Musa, T4.) | Mirrors Anton without new dependencies. A stolen database yields no usable cookie, and sessions can be revoked. MCP bearer tokens (`read` / `read+propose`) are built in T11. |
| D-24 | Sessions last 30 days, sliding: a request more than an hour after the last one extends expiry and re-issues the cookie. Log out and log out everywhere revoke. (Musa, T4.) | The phone PWA stays signed in; any session can still be killed. |
| D-25 | Accounts can be created and edited (nickname, type, broker label) but not deleted in v1; base currency is fixed at creation. The API has no DELETE route anywhere. (Musa, T4.) | History stays complete; RESTRICT foreign keys would block most deletes anyway. |

**Naming.** The project and repo are Tres Comas. "Son of Anton" is the umbrella for all of Musa's AI tools; each tool takes a name from the same show.

## C. Pending (P-*) — proposed, not yet decided

| ID | Question | Proposal | Needed by |
| --- | --- | --- | --- |
| P-2 | Which market-data provider for prices (TSX + US)? Musa asked to look at providers within the Canadian market first. | Run the D-14 spike: shortlist 2–3, test all nine tickers + VGRO/XEQT/XGRO holdings, record results in `docs/spikes/price_provider.md`, then decide. | T7 |
| P-3 | Natural key for Wealthsimple activity-row dedup. The column `transactions.natural_key` (unique, nullable) exists since T2; its contents are still to decide. | Hash of (account, trade date, type, security, quantity, net amount, currency) plus the file hash on `import_batch`; confirm against a real export's columns during T5. | T5 |

## D. Superseded

None yet.

## E. Debt list

- **Schema drift blind spot (T2).** Alembic autogenerate does not compare CHECK constraints or triggers, so `alembic check` and `test_migration_matches_models` can't see drift there. `tests/test_schema.py` exercises each constraint and trigger by behaviour instead. Keep that true when adding constraints.

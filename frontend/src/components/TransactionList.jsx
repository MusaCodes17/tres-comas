import { useState } from "react";
import { useTransactions, useVoidTransaction } from "../hooks/useApi.js";
import { formatDecimal, formatMoney } from "../lib/format.js";
import TransactionForm from "./TransactionForm.jsx";
import { btnSmCls, ErrorText } from "./ui.jsx";

export default function TransactionList({ account }) {
  const { data, isPending, error } = useTransactions(account.id);
  const voidTx = useVoidTransaction(account.id);
  const [correctingId, setCorrectingId] = useState(null);

  function onVoid(t) {
    if (window.confirm(`Void transaction #${t.id}?`)) voidTx.mutate(t.id);
  }

  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-base font-medium">Transactions</h3>
      {isPending && <p className="text-muted">Loading…</p>}
      <ErrorText error={error} />
      <ErrorText error={voidTx.error} />
      {data && data.length === 0 && <p className="text-muted">No transactions.</p>}
      <ul className="flex flex-col gap-2">
        {data?.map((t) => {
          const voided = t.voided_at != null;
          if (correctingId === t.id) {
            return (
              <li key={t.id}>
                <TransactionForm account={account} correcting={t} onDone={() => setCorrectingId(null)} />
              </li>
            );
          }
          return (
            <li key={t.id} className="rounded border border-muted/30 px-3 py-2">
              <div className={voided ? "opacity-50 line-through" : ""}>
                <div className="flex justify-between">
                  <span>
                    {t.trade_date} · {t.type}
                    {t.security_ticker ? ` · ${t.security_ticker}` : ""}
                  </span>
                  <span>{formatMoney(t.amount, t.currency)}</span>
                </div>
                <div className="text-sm text-muted">
                  {t.quantity != null && <span>qty {formatDecimal(t.quantity, 4)} </span>}
                  {t.split_ratio != null && <span>ratio {t.split_ratio} </span>}
                  {t.note && <span>{t.note}</span>}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
                <span>#{t.id}</span>
                {voided && <span>voided</span>}
                {t.replaces_id != null && <span>corrects #{t.replaces_id}</span>}
              </div>
              {!voided && (
                <div className="mt-1 flex gap-2">
                  <button className={btnSmCls} onClick={() => setCorrectingId(t.id)}>
                    Correct
                  </button>
                  <button className={btnSmCls} disabled={voidTx.isPending} onClick={() => onVoid(t)}>
                    Void
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

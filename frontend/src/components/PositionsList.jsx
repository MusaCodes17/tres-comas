import { useState } from "react";
import { usePositions } from "../hooks/useApi.js";
import { formatDecimal, formatMoney } from "../lib/format.js";
import { ErrorText } from "./ui.jsx";

export default function PositionsList({ accountId }) {
  const [includeClosed, setIncludeClosed] = useState(false);
  const { data, isPending, error } = usePositions(accountId, { includeClosed });

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-medium">Positions</h3>
        <label className="flex min-h-[44px] items-center gap-2 text-sm text-muted">
          <input type="checkbox" checked={includeClosed} onChange={(e) => setIncludeClosed(e.target.checked)} />
          Show closed
        </label>
      </div>
      {isPending && <p className="text-muted">Loading…</p>}
      <ErrorText error={error} />
      {data && data.length === 0 && <p className="text-muted">No positions.</p>}
      <ul className="flex flex-col gap-2">
        {data?.map((p) => (
          <li key={p.security_id} className="rounded border border-muted/30 px-3 py-2">
            <div className="flex justify-between">
              <span>
                {p.ticker} <span className="text-muted">· {p.exchange}</span>
              </span>
              <span>{formatDecimal(p.quantity, 4)}</span>
            </div>
            <div className="flex justify-between text-sm text-muted">
              <span>
                avg {formatDecimal(p.average_cost, 4)} {p.currency}
              </span>
              <span>cost {formatMoney(p.total_cost, p.currency)}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

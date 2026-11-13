import { useState } from "react";
import { useCreateSecurity } from "../hooks/useApi.js";
import { btnCls, btnGhostCls, ErrorText, Field, inputCls } from "./ui.jsx";

const KINDS = ["stock", "etf", "cash"];

/** Add a security. A security is ticker plus exchange, never ticker alone. */
export default function SecurityForm({ onCreated, onCancel }) {
  const create = useCreateSecurity();
  const [f, setF] = useState({ ticker: "", exchange: "", currency: "CAD", kind: "stock", name: "", sector: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  function submit(e) {
    e.preventDefault();
    create.mutate(
      {
        ticker: f.ticker.trim().toUpperCase(),
        exchange: f.exchange.trim().toUpperCase(),
        currency: f.currency.trim().toUpperCase(),
        kind: f.kind,
        name: f.name.trim() || null,
        sector: f.sector.trim() || null,
      },
      { onSuccess: (row) => onCreated(row) },
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded border border-muted/30 p-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Ticker">
          <input className={inputCls} value={f.ticker} onChange={set("ticker")} autoCapitalize="characters" />
        </Field>
        <Field label="Exchange">
          <input className={inputCls} value={f.exchange} onChange={set("exchange")} autoCapitalize="characters" />
        </Field>
        <Field label="Currency">
          <input className={inputCls} value={f.currency} onChange={set("currency")} />
        </Field>
        <Field label="Kind">
          <select className={inputCls} value={f.kind} onChange={set("kind")}>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Name (optional)">
        <input className={inputCls} value={f.name} onChange={set("name")} />
      </Field>
      <Field label="Sector (optional)">
        <input className={inputCls} value={f.sector} onChange={set("sector")} />
      </Field>
      <ErrorText error={create.error} />
      <div className="flex gap-2">
        <button
          type="button"
          className={btnCls}
          disabled={create.isPending || !f.ticker.trim() || !f.exchange.trim() || !f.currency.trim()}
          onClick={submit}
        >
          Add security
        </button>
        <button type="button" className={btnGhostCls} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

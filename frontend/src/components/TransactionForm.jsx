import { useState } from "react";
import { useCreateTransaction, useReplaceTransaction, useSecurities } from "../hooks/useApi.js";
import SecurityForm from "./SecurityForm.jsx";
import { btnCls, btnGhostCls, btnSmCls, ErrorText, Field, inputCls } from "./ui.jsx";

const TYPES = ["buy", "sell", "dividend", "deposit", "withdrawal", "fee", "split", "transfer_in", "transfer_out"];
const DECIMAL_RE = /^\d+(\.\d+)?$/;

// Which inputs each type shows, mirroring the backend rules (the server still decides).
const TRADE = ["buy", "sell", "transfer_in", "transfer_out"];
const showQuantity = (t) => TRADE.includes(t);
const showPrice = (t) => TRADE.includes(t);
const showRatio = (t) => t === "split";
const showAmount = (t) => t !== "split";
const securityMode = (t) => (TRADE.includes(t) || t === "split" ? "required" : t === "dividend" || t === "fee" ? "optional" : "none");

function todayLocal() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/**
 * Add a transaction, or (with `correcting`) replace an existing one.
 * Decimal fields are sent as the trimmed strings the user typed.
 */
export default function TransactionForm({ account, correcting, onDone }) {
  const { data: securities = [] } = useSecurities();
  const create = useCreateTransaction(account.id);
  const replace = useReplaceTransaction(account.id);
  const mutation = correcting ? replace : create;
  const [addingSecurity, setAddingSecurity] = useState(false);
  const [clientError, setClientError] = useState(null);
  const c = correcting;
  const [f, setF] = useState({
    type: c?.type ?? "buy",
    security_id: c?.security_id != null ? String(c.security_id) : "",
    quantity: c?.quantity ?? "",
    price: c?.price ?? "",
    amount: c?.amount ?? "",
    split_ratio: c?.split_ratio ?? "",
    currency: c?.currency ?? account.base_currency,
    trade_date: c?.trade_date ?? todayLocal(),
    note: c?.note ?? "",
  });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const mode = securityMode(f.type);

  function pickSecurity(id) {
    const sec = securities.find((s) => String(s.id) === id);
    setF((prev) => ({ ...prev, security_id: id, currency: sec ? sec.currency : prev.currency }));
  }

  function submit(e) {
    e.preventDefault();
    setClientError(null);
    const t = f.type;
    const checks = [];
    if (showAmount(t)) checks.push(["Amount", f.amount.trim(), true]);
    if (showQuantity(t)) checks.push(["Quantity", f.quantity.trim(), true]);
    if (showPrice(t)) checks.push(["Price", f.price.trim(), false]);
    if (showRatio(t)) checks.push(["Split ratio", f.split_ratio.trim(), true]);
    for (const [label, val, required] of checks) {
      if ((required && !val) || (val && !DECIMAL_RE.test(val))) {
        setClientError(`${label} must be a plain number like 12.50`);
        return;
      }
    }
    if (mode === "required" && !f.security_id) {
      setClientError("Choose a security");
      return;
    }
    const body = {
      type: t,
      amount: showAmount(t) ? f.amount.trim() : "0",
      currency: f.currency.trim().toUpperCase(),
      trade_date: f.trade_date,
      security_id: mode !== "none" && f.security_id ? Number(f.security_id) : null,
      quantity: showQuantity(t) ? f.quantity.trim() || null : null,
      price: showPrice(t) ? f.price.trim() || null : null,
      split_ratio: showRatio(t) ? f.split_ratio.trim() || null : null,
      note: f.note.trim() || null,
    };
    if (correcting) {
      replace.mutate({ id: correcting.id, body: { ...body, account_id: account.id } }, { onSuccess: onDone });
    } else {
      create.mutate(body, {
        onSuccess: () => {
          setF((prev) => ({ ...prev, quantity: "", price: "", amount: "", split_ratio: "", note: "" }));
          if (onDone) onDone();
        },
      });
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded border border-muted/30 p-3">
      <h3 className="text-base font-medium">
        {correcting ? `Correct transaction #${correcting.id}` : "Add transaction"}
      </h3>
      <Field label="Type">
        <select className={inputCls} value={f.type} onChange={set("type")}>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </Field>
      {mode !== "none" && (
        <div className="flex flex-col gap-2">
          <Field label={mode === "optional" ? "Security (optional)" : "Security"}>
            <select className={inputCls} value={f.security_id} onChange={(e) => pickSecurity(e.target.value)}>
              <option value="">—</option>
              {securities.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.ticker} · {s.exchange}
                </option>
              ))}
            </select>
          </Field>
          {!addingSecurity && (
            <button type="button" className={btnSmCls} onClick={() => setAddingSecurity(true)}>
              Add security
            </button>
          )}
          {addingSecurity && (
            <SecurityForm
              onCancel={() => setAddingSecurity(false)}
              onCreated={(row) => {
                setAddingSecurity(false);
                pickSecurity(String(row.id));
              }}
            />
          )}
        </div>
      )}
      {showQuantity(f.type) && (
        <Field label="Quantity">
          <input type="text" inputMode="decimal" className={inputCls} value={f.quantity} onChange={set("quantity")} />
        </Field>
      )}
      {showRatio(f.type) && (
        <Field label="Split ratio">
          <input type="text" inputMode="decimal" className={inputCls} value={f.split_ratio} onChange={set("split_ratio")} />
        </Field>
      )}
      {showAmount(f.type) && (
        <Field label="Amount">
          <input type="text" inputMode="decimal" className={inputCls} value={f.amount} onChange={set("amount")} />
        </Field>
      )}
      {showPrice(f.type) && (
        <Field label="Price (optional)">
          <input type="text" inputMode="decimal" className={inputCls} value={f.price} onChange={set("price")} />
        </Field>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Currency">
          <input className={inputCls} value={f.currency} onChange={set("currency")} />
        </Field>
        <Field label="Trade date">
          <input type="date" className={inputCls} value={f.trade_date} onChange={set("trade_date")} required />
        </Field>
      </div>
      <Field label="Note (optional)">
        <input className={inputCls} value={f.note} onChange={set("note")} />
      </Field>
      {clientError && (
        <p role="alert" className="text-sm text-danger">
          {clientError}
        </p>
      )}
      <ErrorText error={mutation.error} />
      <div className="flex gap-2">
        <button type="submit" className={btnCls} disabled={mutation.isPending}>
          {correcting ? "Replace" : "Add"}
        </button>
        {correcting && (
          <button type="button" className={btnGhostCls} onClick={onDone}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

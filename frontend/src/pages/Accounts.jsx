import { useState } from "react";
import { useAccounts, useCreateAccount, useUpdateAccount } from "../hooks/useApi.js";
import { btnCls, btnGhostCls, btnSmCls, ErrorText, Field, inputCls } from "../components/ui.jsx";

const TYPES = ["tfsa", "rrsp", "non_registered", "cash"];

/** Create form (no `account`) or edit form (nickname, type, broker label only). */
function AccountForm({ account, onDone }) {
  const create = useCreateAccount();
  const update = useUpdateAccount();
  const mutation = account ? update : create;
  const [nickname, setNickname] = useState(account?.nickname ?? "");
  const [type, setType] = useState(account?.type ?? "tfsa");
  const [currency, setCurrency] = useState(account?.base_currency ?? "CAD");
  const [broker, setBroker] = useState(account?.broker_label ?? "");

  function submit(e) {
    e.preventDefault();
    const brokerLabel = broker.trim() || null;
    if (account) {
      update.mutate(
        { id: account.id, patch: { nickname: nickname.trim(), type, broker_label: brokerLabel } },
        { onSuccess: onDone },
      );
    } else {
      create.mutate(
        {
          nickname: nickname.trim(),
          type,
          base_currency: currency.trim().toUpperCase(),
          broker_label: brokerLabel,
        },
        { onSuccess: onDone },
      );
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded border border-muted/30 p-3">
      <Field label="Nickname">
        <input className={inputCls} value={nickname} onChange={(e) => setNickname(e.target.value)} required />
      </Field>
      <Field label="Type">
        <select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </Field>
      {!account && (
        <Field label="Base currency">
          <input className={inputCls} value={currency} onChange={(e) => setCurrency(e.target.value)} required />
        </Field>
      )}
      <Field label="Broker label (optional)">
        <input className={inputCls} value={broker} onChange={(e) => setBroker(e.target.value)} />
      </Field>
      <ErrorText error={mutation.error} />
      <div className="flex gap-2">
        <button type="submit" className={btnCls} disabled={mutation.isPending || !nickname.trim()}>
          {account ? "Save" : "Create"}
        </button>
        <button type="button" className={btnGhostCls} onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function Accounts({ onOpen }) {
  const { data, isPending, error } = useAccounts();
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState(null);

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Accounts</h2>
        {!creating && (
          <button className={btnSmCls} onClick={() => setCreating(true)}>
            New account
          </button>
        )}
      </div>
      {creating && <AccountForm onDone={() => setCreating(false)} />}
      {isPending && <p className="text-muted">Loading…</p>}
      <ErrorText error={error} />
      {data && data.length === 0 && !creating && <p className="text-muted">No accounts yet.</p>}
      <ul className="flex flex-col gap-2">
        {data?.map((a) =>
          editingId === a.id ? (
            <li key={a.id}>
              <AccountForm account={a} onDone={() => setEditingId(null)} />
            </li>
          ) : (
            <li key={a.id} className="flex items-stretch gap-2">
              <button
                className="min-h-[44px] flex-1 rounded border border-muted/30 px-3 py-2 text-left"
                onClick={() => onOpen(a)}
              >
                <span className="block text-base">{a.nickname}</span>
                <span className="block text-sm text-muted">
                  {a.type} · {a.base_currency}
                </span>
              </button>
              <button className={btnSmCls} onClick={() => setEditingId(a.id)}>
                Edit
              </button>
            </li>
          ),
        )}
      </ul>
    </section>
  );
}

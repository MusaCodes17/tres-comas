import { useState } from "react";
import { useConnectionLog, useConnections, useSetConnectionEnabled } from "../hooks/useApi.js";
import { btnSmCls, ErrorText } from "../components/ui.jsx";

// Registry view (INV-7): every outbound connection can be switched on or off, and
// its recent calls are listed so tickers-only (INV-4) can be checked by eye.
// Read-only apart from the enabled flag. Secret values never reach the client.

function formatTime(iso) {
  if (!iso) return "never";
  return new Date(iso).toLocaleString();
}

function Badge({ tone, children }) {
  const cls = tone === "ok" ? "border-accent/60 text-accent" : "border-muted/50 text-muted";
  return <span className={`rounded border px-2 py-0.5 text-xs ${cls}`}>{children}</span>;
}

function LogList({ id }) {
  const { data, isPending, error } = useConnectionLog(id, { enabled: true });
  if (isPending) return <p className="text-sm text-muted">Loading log…</p>;
  if (error) return <ErrorText error={error} />;
  if (data.length === 0) return <p className="text-sm text-muted">No calls yet</p>;
  return (
    <ul className="flex flex-col gap-2">
      {data.map((row) => (
        <li key={row.id} className="rounded border border-muted/30 px-3 py-2 text-sm">
          <span className="block text-muted">{formatTime(row.called_at)}</span>
          <span className="block break-all text-fg">{row.endpoint}</span>
          <span className="block text-fg">
            Tickers: {row.tickers_sent.length > 0 ? row.tickers_sent.join(", ") : "none"}
          </span>
          <span className={row.succeeded === false ? "text-danger" : "text-muted"}>
            {row.succeeded === true ? "succeeded" : row.succeeded === false ? "failed" : "unknown"}
          </span>
        </li>
      ))}
    </ul>
  );
}

function ConnectionCard({ connection }) {
  const setEnabled = useSetConnectionEnabled();
  const [showLog, setShowLog] = useState(false);
  const c = connection;
  const hosts = c.scope?.hosts ?? [];
  const params = c.scope?.params ?? [];

  function toggle() {
    if (!c.enabled && !window.confirm(`Switch on ${c.name}? It will be allowed to make outbound calls.`)) {
      return;
    }
    setEnabled.mutate({ id: c.id, enabled: !c.enabled });
  }

  return (
    <li className="flex flex-col gap-3 rounded border border-muted/30 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-base font-medium text-fg">{c.name}</span>
        <span className="text-sm text-muted">
          {c.kind} · {c.direction}
        </span>
      </div>

      <dl className="flex flex-col gap-1 text-sm">
        <div className="flex flex-col">
          <dt className="text-muted">Allowed hosts</dt>
          <dd className="break-all text-fg">{hosts.length > 0 ? hosts.join(", ") : "none"}</dd>
        </div>
        <div className="flex flex-col">
          <dt className="text-muted">Allowed params</dt>
          <dd className="break-all text-fg">{params.length > 0 ? params.join(", ") : "none"}</dd>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <dt className="text-muted">Secret</dt>
          <dd className="flex flex-wrap items-center gap-2 text-fg">
            {c.secret_env_key ? (
              <>
                <code className="break-all">{c.secret_env_key}</code>
                <Badge tone={c.secret_configured ? "ok" : "off"}>
                  {c.secret_configured ? "configured" : "not set"}
                </Badge>
              </>
            ) : (
              "none needed"
            )}
          </dd>
        </div>
        <div className="flex flex-col">
          <dt className="text-muted">Last used</dt>
          <dd className="text-fg">{c.last_used_at ? formatTime(c.last_used_at) : "never"}</dd>
        </div>
      </dl>

      <ErrorText error={setEnabled.error} />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={`min-h-[44px] rounded px-4 text-base font-medium ${
            c.enabled ? "bg-accent text-bg" : "border border-muted/40 text-fg"
          } disabled:opacity-50`}
          aria-pressed={c.enabled}
          onClick={toggle}
          disabled={setEnabled.isPending}
        >
          {c.enabled ? "Enabled" : "Disabled"}
        </button>
        <button
          type="button"
          className={btnSmCls}
          aria-expanded={showLog}
          onClick={() => setShowLog((v) => !v)}
        >
          {showLog ? "Hide log" : "Show log"}
        </button>
      </div>

      {showLog && <LogList id={c.id} />}
    </li>
  );
}

export default function Connections() {
  const { data, isPending, error } = useConnections();

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-medium">Connections</h2>
      <p className="text-sm text-muted">
        Outbound links are off until switched on. Each call is logged with the tickers it sent.
      </p>
      {isPending && <p className="text-muted">Loading…</p>}
      <ErrorText error={error} />
      {data && data.length === 0 && <p className="text-muted">No connections yet.</p>}
      <ul className="flex flex-col gap-3">
        {data?.map((c) => (
          <ConnectionCard key={c.id} connection={c} />
        ))}
      </ul>
    </section>
  );
}

// Small shared presentational pieces. No data fetching here.

export const inputCls =
  "min-h-[44px] w-full rounded border border-muted/40 bg-bg px-3 text-base text-fg placeholder:text-muted/60 focus:border-accent focus:outline-none";
export const btnCls =
  "min-h-[44px] rounded bg-accent px-4 text-base font-medium text-bg disabled:opacity-50";
export const btnGhostCls =
  "min-h-[44px] rounded border border-muted/40 px-4 text-base text-fg disabled:opacity-50";
export const btnSmCls =
  "min-h-[44px] rounded border border-muted/40 px-3 text-sm text-fg disabled:opacity-50";

/** Labelled form row. */
export function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-muted">
      <span>{label}</span>
      {children}
    </label>
  );
}

/** Inline API error, shown next to the form that caused it. */
export function ErrorText({ error }) {
  if (!error) return null;
  return (
    <p role="alert" className="text-sm text-danger">
      {error.detail || error.message}
    </p>
  );
}

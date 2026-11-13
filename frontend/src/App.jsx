import { useHealth } from "./hooks/useApi.js";

function StatusLine() {
  const { isPending, isError } = useHealth();
  if (isPending) return <p className="text-muted">Checking…</p>;
  if (isError) return <p className="text-muted">Backend: unreachable</p>;
  return <p className="text-accent">Backend: ok</p>;
}

export default function App() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col gap-2 px-4 pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)]">
      <header className="pt-8">
        <h1 className="text-2xl font-semibold text-fg">Tres Comas</h1>
        <p className="text-sm text-muted">Investment ledger</p>
      </header>
      <main className="pt-4 text-sm">
        <StatusLine />
      </main>
    </div>
  );
}

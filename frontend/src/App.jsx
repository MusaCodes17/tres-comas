import { useState } from "react";
import { useLogout, useMe } from "./hooks/useApi.js";
import Accounts from "./pages/Accounts.jsx";
import AccountDetail from "./pages/AccountDetail.jsx";
import Connections from "./pages/Connections.jsx";
import Login from "./pages/Login.jsx";
import { btnSmCls } from "./components/ui.jsx";

// Navigation is a tiny state machine: accounts list <-> one account's detail,
// with the Connections screen reachable from the top bar.
function Authed() {
  const [account, setAccount] = useState(null);
  const [onConnections, setOnConnections] = useState(false);
  const logout = useLogout();

  function openConnections() {
    setAccount(null);
    setOnConnections(true);
  }

  let screen;
  if (onConnections) screen = <Connections />;
  else if (account) screen = <AccountDetail account={account} onBack={() => setAccount(null)} />;
  else screen = <Accounts onOpen={setAccount} />;

  return (
    <>
      <div className="flex justify-end gap-2">
        {onConnections ? (
          <button className={btnSmCls} onClick={() => setOnConnections(false)}>
            Accounts
          </button>
        ) : (
          <button className={btnSmCls} onClick={openConnections}>
            Connections
          </button>
        )}
        <button className={btnSmCls} onClick={() => logout.mutate()} disabled={logout.isPending}>
          Log out
        </button>
      </div>
      {screen}
    </>
  );
}

export default function App() {
  const me = useMe();
  let body;
  if (me.isPending) body = <p className="text-muted">Checking…</p>;
  else if (me.isError && me.error.status === 401) body = <Login />;
  else if (me.isError) body = <p className="text-danger">Backend unreachable: {me.error.message}</p>;
  else body = <Authed />;

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col gap-2 px-4 pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)]">
      <header className="pt-6">
        <h1 className="text-2xl font-semibold text-fg">Tres Comas</h1>
        <p className="text-sm text-muted">Investment ledger</p>
      </header>
      <main className="flex flex-col gap-2 pb-8 pt-4 text-sm">{body}</main>
    </div>
  );
}

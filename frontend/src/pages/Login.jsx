import { useState } from "react";
import { useLogin } from "../hooks/useApi.js";
import { btnCls, inputCls, Field } from "../components/ui.jsx";

const MESSAGES = {
  401: "Wrong password",
  429: "Too many attempts, try again later",
  503: "Login is not configured on the server",
};

export default function Login() {
  const [password, setPassword] = useState("");
  const login = useLogin();

  function submit(e) {
    e.preventDefault();
    if (password) login.mutate(password);
  }

  const err = login.error;
  const message = err ? MESSAGES[err.status] || err.detail || "Login failed" : null;

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Field label="Password">
        <input
          type="password"
          autoComplete="current-password"
          className={inputCls}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
        />
      </Field>
      {message && (
        <p role="alert" className="text-sm text-danger">
          {message}
        </p>
      )}
      <button type="submit" className={btnCls} disabled={login.isPending || !password}>
        {login.isPending ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

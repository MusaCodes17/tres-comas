/**
 * The single HTTP client for the frontend. Every server call goes through here,
 * and React Query hooks live in src/hooks/useApi.js.
 *
 * Money and quantities travel as strings in both directions and must never be
 * parsed to Number (INV-9). The server owns every rule; callers show `detail`.
 */

/** Error carrying the HTTP status and a human-readable server message. */
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function extractDetail(payload, status) {
  const d = payload && payload.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length > 0) {
    const first = d[0];
    if (typeof first === "string") return first;
    if (first && typeof first.msg === "string") {
      const loc = Array.isArray(first.loc) ? first.loc.filter((p) => p !== "body").join(".") : "";
      return loc ? `${loc}: ${first.msg}` : first.msg;
    }
  }
  return `Request failed (HTTP ${status})`;
}

/**
 * Fetch a same-origin API path and return parsed JSON (null for 204).
 * @throws {ApiError} on any non-2xx response.
 */
async function request(path, { method = "GET", body } = {}) {
  const init = { method, credentials: "same-origin" };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(path, init);
  if (!res.ok) {
    let payload = null;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }
    throw new ApiError(res.status, extractDetail(payload, res.status));
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => request("/health"),
  login: (password) => request("/api/auth/login", { method: "POST", body: { password } }),
  logout: () => request("/api/auth/logout", { method: "POST" }),
  me: () => request("/api/auth/me"),

  listAccounts: () => request("/api/accounts"),
  createAccount: (body) => request("/api/accounts", { method: "POST", body }),
  updateAccount: (id, patch) => request(`/api/accounts/${id}`, { method: "PATCH", body: patch }),

  listSecurities: () => request("/api/securities"),
  createSecurity: (body) => request("/api/securities", { method: "POST", body }),

  listTransactions: (accountId) => request(`/api/accounts/${accountId}/transactions`),
  createTransaction: (accountId, body) =>
    request(`/api/accounts/${accountId}/transactions`, { method: "POST", body }),
  voidTransaction: (id) => request(`/api/transactions/${id}/void`, { method: "POST" }),
  replaceTransaction: (id, body) =>
    request(`/api/transactions/${id}/replace`, { method: "POST", body }),

  listPositions: (accountId, { includeClosed = false } = {}) =>
    request(`/api/accounts/${accountId}/positions?include_closed=${includeClosed ? "true" : "false"}`),
};

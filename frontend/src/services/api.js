/**
 * The single HTTP client for the frontend. Every server call goes through here,
 * and React Query hooks live in src/hooks/useApi.js.
 *
 * Money arrives as strings and must never be parsed to Number for arithmetic
 * (INV-9). Format it for display only.
 */

/**
 * Fetch a same-origin API path and return parsed JSON.
 * @param {string} path  e.g. "/health"
 * @returns {Promise<any>}
 * @throws {Error} on any non-2xx response or network failure.
 */
async function request(path) {
  const res = await fetch(path, { credentials: "same-origin" });
  if (!res.ok) {
    throw new Error(`${path} failed with HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),
};

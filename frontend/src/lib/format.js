/**
 * Display formatting for money and quantities (INV-9).
 *
 * Values arrive from the API as decimal strings and are rounded by string
 * manipulation only. Nothing here ever converts to Number.
 */

const DASH = "—";

/** Add one to a string of decimal digits ("1999" -> "2000", "999" -> "1000"). */
function incrementDigits(digits) {
  const out = digits.split("");
  let i = out.length - 1;
  while (i >= 0) {
    if (out[i] === "9") {
      out[i] = "0";
      i -= 1;
    } else {
      out[i] = String(Number(out[i]) + 1); // single digit, not a money value
      return out.join("");
    }
  }
  return "1" + out.join("");
}

/**
 * Round a decimal string half-up (away from zero) to `dp` places.
 * @param {string|null|undefined} value  e.g. "1.99995"
 * @param {number} dp  decimal places
 * @returns {string}  "2.0000", or an em dash for null/undefined. Unparseable
 *   input is returned unchanged. A result of zero carries no sign.
 */
export function formatDecimal(value, dp) {
  if (value === null || value === undefined) return DASH;
  const m = /^([+-]?)(\d*)(?:\.(\d*))?$/.exec(String(value).trim());
  if (!m || (m[2] === "" && (m[3] === undefined || m[3] === ""))) return String(value);
  const sign = m[1] === "-" ? "-" : "";
  const intPart = m[2] === "" ? "0" : m[2];
  const frac = (m[3] ?? "").padEnd(dp + 1, "0");
  const roundUp = frac.charAt(dp) >= "5";
  let digits = intPart + frac.slice(0, dp);
  if (roundUp) digits = incrementDigits(digits);
  digits = digits.padStart(dp + 1, "0");
  const whole = digits.slice(0, digits.length - dp).replace(/^0+(?=\d)/, "");
  const fraction = digits.slice(digits.length - dp);
  const text = dp > 0 ? `${whole}.${fraction}` : whole;
  const isZero = /^[0.]*$/.test(text);
  return (isZero ? "" : sign) + text;
}

/** Two-place amount followed by its currency code, e.g. "12.00 CAD". */
export function formatMoney(value, currency) {
  return formatDecimal(value, 2) + " " + currency;
}

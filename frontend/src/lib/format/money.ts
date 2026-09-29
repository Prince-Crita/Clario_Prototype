/**
 * Indian-style money and percent formatting — the TypeScript twin of `clario.core.money`.
 *
 * Both implementations must pass `contracts/money-format-vectors.json`, so a figure looks
 * identical on the dashboard and in the assistant's answer. Inputs are decimal STRINGS from the
 * API (never JS numbers), so no precision is lost; the UI never does financial arithmetic
 * (plan §9.2) — it only rounds for display.
 */

const MINUS = "−";
const RUPEE = "₹";

interface Parsed {
  negative: boolean;
  integer: string; // digits, no leading zeros (except "0")
  fraction: string; // digits
}

function parseDecimal(value: string): Parsed {
  const match = /^\s*([+-])?(\d*)(?:\.(\d*))?\s*$/.exec(value);
  if (!match || (!match[2] && !match[3])) throw new Error(`Not a decimal string: ${value}`);
  const integer = (match[2] ?? "").replace(/^0+(?=\d)/, "") || "0";
  return { negative: match[1] === "-", integer, fraction: match[3] ?? "" };
}

/** Round |value| half-up to `places` decimals; returns [integerDigits, fractionDigits]. */
function roundHalfUp(integer: string, fraction: string, places: number): [string, string] {
  const padded = fraction.padEnd(places + 1, "0");
  const kept = integer + padded.slice(0, places);
  const roundUp = padded.charCodeAt(places) - 48 >= 5;
  let digits = roundUp ? addOne(kept) : kept;
  digits = digits.padStart(places + 1, "0");
  const intPart = digits.slice(0, digits.length - places).replace(/^0+(?=\d)/, "");
  return [intPart, places ? digits.slice(digits.length - places) : ""];
}

function addOne(digits: string): string {
  const chars = digits.split("");
  for (let i = chars.length - 1; i >= 0; i--) {
    if (chars[i] === "9") {
      chars[i] = "0";
    } else {
      chars[i] = String(Number(chars[i]) + 1);
      return chars.join("");
    }
  }
  return "1" + chars.join("");
}

function groupIndian(integer: string): string {
  if (integer.length <= 3) return integer;
  let head = integer.slice(0, -3);
  const groups: string[] = [];
  while (head.length > 2) {
    groups.unshift(head.slice(-2));
    head = head.slice(0, -2);
  }
  if (head) groups.unshift(head);
  return `${groups.join(",")},${integer.slice(-3)}`;
}

function isZero(integer: string, fraction: string): boolean {
  return /^0*$/.test(integer) && /^0*$/.test(fraction);
}

/** ₹12,45,300 · −₹6,48,028 · ₹1,234.50 (decimals = 2). */
export function formatInr(value: string, decimals = 0): string {
  const { negative, integer, fraction } = parseDecimal(value);
  const [intPart, fracPart] = roundHalfUp(integer, fraction, decimals);
  const sign = negative && !isZero(intPart, fracPart) ? MINUS : "";
  return `${sign}${RUPEE}${groupIndian(intPart)}${decimals ? `.${fracPart}` : ""}`;
}

/** Shift a decimal string left by `places` digits (divide by 10^places) without floats. */
function shiftLeft(integer: string, fraction: string, places: number): [string, string] {
  const padded = integer.padStart(places + 1, "0");
  return [padded.slice(0, padded.length - places), padded.slice(padded.length - places) + fraction];
}

function trimFraction(intPart: string, fracPart: string): string {
  const trimmed = fracPart.replace(/0+$/, "");
  return trimmed ? `${intPart}.${trimmed}` : intPart;
}

/** ₹4.82 lakh · ₹1.2 crore · ₹62,000 (below one lakh, full form). */
export function formatInrCompact(value: string): string {
  const { negative, integer, fraction } = parseDecimal(value);
  if (integer.length <= 5) return formatInr(value); // < 1,00,000
  let unit = integer.length >= 8 ? "crore" : "lakh";
  let [intPart, fracPart] = roundHalfUp(
    ...shiftLeft(integer, fraction, unit === "crore" ? 7 : 5),
    2,
  );
  if (unit === "lakh" && intPart.length >= 3) {
    // 99.999… lakh rounds to 100 lakh → show as 1 crore
    unit = "crore";
    [intPart, fracPart] = roundHalfUp(...shiftLeft(integer, fraction, 7), 2);
  }
  return `${negative ? MINUS : ""}${RUPEE}${trimFraction(intPart, fracPart)} ${unit}`;
}

/** 67% · −89% · 11.4% (decimals = 1) · "n/a" when undefined. */
export function formatPercent(value: string | null, decimals = 0): string {
  if (value === null) return "n/a";
  const { negative, integer, fraction } = parseDecimal(value);
  const [intPart, fracPart] = roundHalfUp(integer, fraction, decimals);
  const sign = negative && !isZero(intPart, fracPart) ? MINUS : "";
  return `${sign}${intPart}${decimals ? `.${fracPart}` : ""}%`;
}

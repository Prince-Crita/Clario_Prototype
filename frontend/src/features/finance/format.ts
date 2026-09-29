/**
 * Display helpers for the Command Centre. Values arrive as exact decimal strings and are only
 * formatted here (plan §9.2): the UI never adds, nets or derives a financial figure. `plot()`
 * turns a string into a number for chart geometry only; labels always use the original string.
 */
import { formatInr, formatInrCompact, formatPercent } from "../../lib/format/money";

export const money = (value: string): string => formatInr(value);
export const percent = (value: string | null | undefined, decimals = 0): string =>
  formatPercent(value ?? null, decimals);

export function isNegative(value: string): boolean {
  return /^\s*-/.test(value) && !/^\s*-0*(\.0*)?\s*$/.test(value);
}

export function isZero(value: string): boolean {
  return /^\s*[+-]?0*(\.0*)?\s*$/.test(value);
}

/** For chart geometry only (bar lengths, axis scale). */
export const plot = (value: string): number => Number(value);

/** Axis ticks: compact rupees (₹2.5 lakh). */
export const axisInr = (value: number): string => formatInrCompact(String(Math.round(value)));

const MONTH = new Intl.DateTimeFormat("en-IN", { month: "short", timeZone: "UTC" });
const DAY = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });
const DATE = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});
const STAMP = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
});

const asDate = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00Z`);

/** "2026-03-01" → "Mar '26" */
export const monthLabel = (iso: string): string =>
  `${MONTH.format(asDate(iso))} '${iso.slice(2, 4)}`;
/** "2026-09-25" → "25 Sept" */
export const dayLabel = (iso: string): string => DAY.format(asDate(iso));
/** "2026-09-25" → "25 Sept 2026" */
export const dateLabel = (iso: string): string => DATE.format(asDate(iso));
/** A timestamp in the viewer's time zone: "25 Sept, 3:56 pm" */
export const stampLabel = (iso: string): string => STAMP.format(new Date(iso));

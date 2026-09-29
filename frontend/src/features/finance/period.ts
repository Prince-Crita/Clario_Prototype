/**
 * The Command Centre period (plan §27.8). The finance API returns monthly series for the imported
 * window; headline figures carry their own stated window (the API has no period parameter). So the
 * period selects which MONTHS the charts and monthly tables show; it never recomputes a figure.
 * Month keys are "YYYY-MM"; fiscal quarters follow the organisation's fiscal-year start.
 */

export type PeriodKey =
  | "all"
  | "this_month"
  | "last_month"
  | "this_quarter"
  | "last_quarter"
  | "fy"
  | "last_fy"
  | "custom";

export interface Period {
  key: PeriodKey;
  /** "This quarter" */
  name: string;
  /** "Jul – Sep 2026" (or "All imported months") */
  range: string;
  /** Inclusive month bounds; null = unbounded. */
  from: string | null;
  to: string | null;
}

export const PRESETS: { key: PeriodKey; name: string }[] = [
  { key: "all", name: "All imported data" },
  { key: "this_month", name: "This month" },
  { key: "last_month", name: "Last month" },
  { key: "this_quarter", name: "This quarter" },
  { key: "last_quarter", name: "Last quarter" },
  { key: "fy", name: "This financial year" },
  { key: "last_fy", name: "Last financial year" },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** 2026, 9 → "2026-09" */
export const monthKey = (year: number, month: number): string =>
  `${year}-${String(month).padStart(2, "0")}`;

function shift(key: string, months: number): string {
  const [y, m] = key.split("-").map(Number) as [number, number];
  const index = y * 12 + (m - 1) + months;
  return monthKey(Math.floor(index / 12), (index % 12) + 1);
}

const label = (key: string) => {
  const [y, m] = key.split("-").map(Number) as [number, number];
  return { month: MONTHS[m - 1] ?? "", year: y };
};

export function rangeLabel(from: string, to: string): string {
  const a = label(from);
  const b = label(to);
  if (from === to) return `${a.month} ${a.year}`;
  return a.year === b.year
    ? `${a.month} – ${b.month} ${b.year}`
    : `${a.month} ${a.year} – ${b.month} ${b.year}`;
}

/** The fiscal year containing `month`: its first month key. */
function fiscalStart(month: string, startMonth: number): string {
  const { year } = label(month);
  const m = Number(month.slice(5, 7));
  return monthKey(m >= startMonth ? year : year - 1, startMonth);
}

export function resolvePeriod(
  key: PeriodKey,
  today: Date,
  fyStartMonth: number,
  custom?: { from: string; to: string } | null,
): Period {
  const current = monthKey(today.getFullYear(), today.getMonth() + 1);
  const fy = fiscalStart(current, fyStartMonth);
  const quarter = shift(fy, Math.floor(monthsBetween(fy, current) / 3) * 3);
  const make = (from: string, to: string, name: string): Period => ({
    key,
    name,
    range: rangeLabel(from, to),
    from,
    to,
  });
  switch (key) {
    case "this_month":
      return make(current, current, "This month");
    case "last_month":
      return make(shift(current, -1), shift(current, -1), "Last month");
    case "this_quarter":
      return make(quarter, current, "This quarter");
    case "last_quarter":
      return make(shift(quarter, -3), shift(quarter, -1), "Last quarter");
    case "fy":
      return make(fy, current, "This financial year");
    case "last_fy":
      return make(shift(fy, -12), shift(fy, -1), "Last financial year");
    case "custom":
      if (custom && custom.from <= custom.to) return make(custom.from, custom.to, "Custom");
      return resolvePeriod("all", today, fyStartMonth);
    default:
      return {
        key: "all",
        name: "All imported data",
        range: "Every imported month",
        from: null,
        to: null,
      };
  }
}

function monthsBetween(from: string, to: string): number {
  const [fy, fm] = from.split("-").map(Number) as [number, number];
  const [ty, tm] = to.split("-").map(Number) as [number, number];
  return (ty - fy) * 12 + (tm - fm);
}

/** Does an ISO date or month ("2026-09-01") fall in the period? */
export function inPeriod(date: string, period: Period): boolean {
  const month = date.slice(0, 7);
  return (!period.from || month >= period.from) && (!period.to || month <= period.to);
}

/** The last `count` months up to today, newest first, for the custom range pickers. */
export function recentMonths(today: Date, count = 36): { key: string; label: string }[] {
  const current = monthKey(today.getFullYear(), today.getMonth() + 1);
  return Array.from({ length: count }, (_, i) => {
    const key = shift(current, -i);
    const { month, year } = label(key);
    return { key, label: `${month} ${year}` };
  });
}

const PERIOD_KEYS = new Set<string>([...PRESETS.map((p) => p.key), "custom"]);
export const isPeriodKey = (value: string | null): value is PeriodKey =>
  value !== null && PERIOD_KEYS.has(value);
const MONTH_KEY = /^\d{4}-(0[1-9]|1[0-2])$/;
export const isMonthKey = (value: string | null): value is string =>
  value !== null && MONTH_KEY.test(value);

/**
 * Command Centre charts (plan §22.2, §25, §27.5). Each sits in `ChartFrame` with the same data as
 * a table ("View as table"), uses the token series colours, an HTML legend, and tooltips that
 * show the server's exact figures (numbers are used for bar geometry only).
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  ChartFrame,
  DataTable,
  seriesColour,
  type Basis,
  type Column,
} from "../../../design-system";
import type { CashBucket, FinanceTrends, MonthFigures } from "../../../lib/api/types";
import { axisInr, dayLabel, isNegative, money, monthLabel, plot } from "../format";
import styles from "./charts.module.css";
import { niceScale } from "./scale";

type Row = Record<string, string | number>;

interface Series {
  key: string;
  name: string;
  colour: string;
  stack?: string;
}

const HEIGHT = 260;
const AXIS = { fontSize: 12, fill: "var(--ink-3)" };
const POSITIVE = "var(--positive)";
const NEGATIVE = "var(--negative)";
const OTHER = "var(--line-strong)";

/** Row for a chart: `key` → number (geometry) and `key__text` → the exact formatted figure. */
function row(label: string, values: Record<string, string>): Row {
  const result: Row = { label };
  for (const [key, value] of Object.entries(values)) {
    result[key] = plot(value);
    result[`${key}__text`] = money(value);
  }
  return result;
}

function Legend({ series }: { series: Series[] }) {
  return (
    <ul className={styles.legend} aria-hidden="true">
      {series.map((s) => (
        <li key={s.key}>
          <span className={styles.swatch} style={{ background: s.colour }} />
          {s.name}
        </li>
      ))}
    </ul>
  );
}

function tooltipText(value: unknown, name: unknown, item: { dataKey?: unknown; payload?: Row }) {
  const text = item.payload?.[`${String(item.dataKey)}__text`];
  return [typeof text === "string" ? text : String(value), String(name)] as [string, string];
}

function extents(data: Row[], series: Series[], line?: Series): number[] {
  const values: number[] = [];
  for (const d of data) {
    const stacked = { pos: 0, neg: 0 };
    for (const s of series) {
      const v = Number(d[s.key] ?? 0);
      if (s.stack) {
        if (v >= 0) stacked.pos += v;
        else stacked.neg += v;
      } else values.push(v);
    }
    values.push(stacked.pos, stacked.neg);
    if (line) values.push(Number(d[line.key] ?? 0));
  }
  return values;
}

interface BarsProps {
  data: Row[];
  series: Series[];
  /** Colour each bar of a single series by its sign (net cash). */
  bySign?: boolean;
  line?: Series;
}

function Bars({ data, series, bySign = false, line }: BarsProps) {
  const Chart = line ? ComposedChart : BarChart;
  const scale = niceScale(extents(data, series, line));
  return (
    <div className={styles.chart}>
      <ResponsiveContainer
        width="100%"
        height={HEIGHT}
        initialDimension={{ width: 640, height: HEIGHT }}
      >
        <Chart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }} barGap={2}>
          <CartesianGrid vertical={false} stroke="var(--line)" />
          <XAxis
            dataKey="label"
            tick={AXIS}
            tickLine={false}
            axisLine={{ stroke: "var(--line)" }}
          />
          <YAxis
            tickFormatter={axisInr}
            tick={AXIS}
            tickLine={false}
            axisLine={false}
            width={84}
            domain={scale.domain}
            ticks={scale.ticks}
            interval={0}
          />
          <ReferenceLine y={0} stroke="var(--line-strong)" />
          <Tooltip
            formatter={tooltipText}
            cursor={{ fill: "var(--paper)" }}
            contentStyle={{ borderRadius: 4, border: "1px solid var(--line)", fontSize: 13 }}
          />
          {series.map((s) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.name}
              fill={s.colour}
              maxBarSize={28}
              {...(s.stack ? { stackId: s.stack } : {})}
              isAnimationActive={false}
            >
              {bySign
                ? data.map((d) => (
                    <Cell key={String(d.label)} fill={Number(d[s.key]) < 0 ? NEGATIVE : POSITIVE} />
                  ))
                : null}
            </Bar>
          ))}
          {line ? (
            <Line
              dataKey={line.key}
              name={line.name}
              stroke={line.colour}
              strokeWidth={2}
              dot={{ r: 3 }}
              isAnimationActive={false}
            />
          ) : null}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}

function table<T extends { key: string }>(caption: string, columns: Column<T>[], rows: T[]) {
  return (
    <DataTable caption={caption} hideCaption columns={columns} rows={rows} rowKey={(r) => r.key} />
  );
}

const moneyCell = (value: string) => (
  <span data-negative={isNegative(value) || undefined} className={styles.figure}>
    {money(value)}
  </span>
);

// ---------------------------------------------------------------- monthly

const MONTH_SERIES: Series[] = [
  { key: "billed", name: "Billed", colour: seriesColour(0) },
  { key: "collected", name: "Collected", colour: seriesColour(1) },
  { key: "expenses", name: "Expenses", colour: seriesColour(2) },
];

type MonthRow = MonthFigures & { key: string };

const monthColumns: Column<MonthRow>[] = [
  { key: "month", header: "Month", cell: (m) => monthLabel(m.month) },
  { key: "billed", header: "Billed", align: "end", cell: (m) => moneyCell(m.billed) },
  { key: "collected", header: "Collected", align: "end", cell: (m) => moneyCell(m.collected) },
  { key: "expenses", header: "Expenses", align: "end", cell: (m) => moneyCell(m.expenses) },
  { key: "net", header: "Net cash", align: "end", cell: (m) => moneyCell(m.net_cash) },
];

interface WindowProps {
  basis?: Basis;
  window?: string | undefined;
}

export function MonthlyChart({ months, window }: { months: MonthFigures[] } & WindowProps) {
  const rows = months.map((m) => ({ ...m, key: m.month }));
  return (
    <ChartFrame
      title="Billed, collected and spent by month"
      description="Invoices raised, payments received and expenses paid"
      basis="cash"
      window={window}
      table={table("Billed, collected and spent by month", monthColumns, rows)}
    >
      <Legend series={MONTH_SERIES} />
      <Bars
        data={months.map((m) =>
          row(monthLabel(m.month), {
            billed: m.billed,
            collected: m.collected,
            expenses: m.expenses,
          }),
        )}
        series={MONTH_SERIES}
      />
    </ChartFrame>
  );
}

export function NetCashChart({ months, window }: { months: MonthFigures[] } & WindowProps) {
  const rows = months.map((m) => ({ ...m, key: m.month }));
  return (
    <ChartFrame
      title="Net cash by month"
      description="Collected minus spent: above the line cash came in, below it went out"
      basis="cash"
      window={window}
      table={table(
        "Net cash by month",
        [monthColumns[0], monthColumns[4]] as Column<MonthRow>[],
        rows,
      )}
    >
      <Bars
        data={months.map((m) => row(monthLabel(m.month), { net: m.net_cash }))}
        series={[{ key: "net", name: "Net cash", colour: POSITIVE }]}
        bySign
      />
    </ChartFrame>
  );
}

// ---------------------------------------------------------------- expense categories

export function ExpenseTrendChart({ trends }: { trends: FinanceTrends }) {
  const series: Series[] = [
    ...trends.top_categories.map((name, i) => ({
      key: `c${i}`,
      name,
      colour: seriesColour(i),
      stack: "spend",
    })),
    { key: "other", name: "Everything else", colour: OTHER, stack: "spend" },
  ];
  const data = trends.expense_trend.map((m) =>
    row(monthLabel(m.month), {
      ...Object.fromEntries(
        trends.top_categories.map((name, i) => [`c${i}`, m.amounts[name] ?? "0"]),
      ),
      other: m.other,
    }),
  );
  interface CatRow {
    key: string;
    month: string;
    values: Record<string, string>;
    other: string;
  }
  const rows: CatRow[] = trends.expense_trend.map((m) => ({
    key: m.month,
    month: m.month,
    values: m.amounts,
    other: m.other,
  }));
  const columns: Column<CatRow>[] = [
    { key: "month", header: "Month", cell: (r) => monthLabel(r.month) },
    ...trends.top_categories.map((name) => ({
      key: name,
      header: name,
      align: "end" as const,
      cell: (r: CatRow) => moneyCell(r.values[name] ?? "0"),
    })),
    { key: "other", header: "Everything else", align: "end", cell: (r) => moneyCell(r.other) },
  ];
  return (
    <ChartFrame
      title="Where spending goes, by month"
      description="Top five expense categories, stacked; the rest combined"
      basis="cash"
      window={trends.window.label}
      table={table("Expenses by category and month", columns, rows)}
    >
      <Legend series={series} />
      <Bars data={data} series={series} />
    </ChartFrame>
  );
}

// ---------------------------------------------------------------- weekly / daily cash

type BucketRow = CashBucket & { key: string };

export function CashFlowChart({
  buckets,
  granularity,
}: {
  buckets: CashBucket[];
  granularity: "week" | "day";
}) {
  const weekly = granularity === "week";
  const title = weekly ? "Weekly cash flow, last 10 weeks" : "Daily cash movement, last 30 days";
  const label = (start: string) => (weekly ? `w/c ${dayLabel(start)}` : dayLabel(start));
  const series: Series[] = [
    { key: "in", name: "Cash in", colour: seriesColour(1) },
    { key: "out", name: "Cash out", colour: seriesColour(2) },
  ];
  const columns: Column<BucketRow>[] = [
    { key: "start", header: weekly ? "Week starting" : "Day", cell: (b) => dayLabel(b.start) },
    { key: "in", header: "Cash in", align: "end", cell: (b) => moneyCell(b.cash_in) },
    { key: "out", header: "Cash out", align: "end", cell: (b) => moneyCell(b.cash_out) },
    { key: "net", header: "Net", align: "end", cell: (b) => moneyCell(b.net) },
  ];
  const rows = buckets.map((b) => ({ ...b, key: b.start }));
  return (
    <ChartFrame
      title={title}
      description={
        weekly
          ? "Collections in, expenses out; weeks start on Monday"
          : "Net of collections and expenses each day"
      }
      basis="cash"
      table={table(title, columns, rows)}
    >
      {weekly ? (
        <>
          <Legend series={[...series, { key: "net", name: "Net", colour: "var(--ink)" }]} />
          <Bars
            data={buckets.map((b) =>
              row(label(b.start), { in: b.cash_in, out: b.cash_out, net: b.net }),
            )}
            series={series}
            line={{ key: "net", name: "Net", colour: "var(--ink)" }}
          />
        </>
      ) : (
        <Bars
          data={buckets.map((b) => row(label(b.start), { net: b.net }))}
          series={[{ key: "net", name: "Net", colour: POSITIVE }]}
          bySign
        />
      )}
    </ChartFrame>
  );
}

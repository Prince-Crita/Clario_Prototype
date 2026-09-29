/** Trends & Analysis (plan §22.2): month-on-month table with totals, net cash, spending by
 * category, weekly cash flow (Monday weeks) and daily cash movement. All cash basis. */
import { BasisTag, DataTable, type Column } from "../../../design-system";
import type { FinanceTrends, MonthFigures } from "../../../lib/api/types";
import { CashFlowChart, ExpenseTrendChart, NetCashChart } from "../components/charts";
import { isNegative, money, monthLabel } from "../format";
import { useFinanceTab } from "../hooks";
import { TabBody, type TabProps } from "./TabBody";
import styles from "./tabs.module.css";

type Row = MonthFigures & { key: string };

const figure = (value: string) => (
  <span className={isNegative(value) ? styles.negative : undefined}>{money(value)}</span>
);

const COLUMNS: Column<Row>[] = [
  { key: "month", header: "Month", cell: (m) => monthLabel(m.month) },
  { key: "billed", header: "Billed", align: "end", cell: (m) => figure(m.billed) },
  { key: "collected", header: "Collected", align: "end", cell: (m) => figure(m.collected) },
  { key: "expenses", header: "Expenses", align: "end", cell: (m) => figure(m.expenses) },
  { key: "net", header: "Net cash", align: "end", cell: (m) => figure(m.net_cash) },
];

export function TrendsTab({ workspaceId, connectionId }: TabProps) {
  const query = useFinanceTab<FinanceTrends>(workspaceId, connectionId, "trends");
  return (
    <TabBody query={query}>
      {(t) => (
        <div className={styles.stack}>
          <section className={styles.panel} aria-labelledby="mom-title">
            <header className={styles.panelHeader}>
              <div>
                <h2 id="mom-title" className={styles.panelTitle}>
                  Month on month
                </h2>
                <p className={styles.muted}>
                  Cash collected against expenses, with the net each month
                </p>
              </div>
              <BasisTag basis="cash" window={t.window.label} />
            </header>
            <DataTable
              caption="Month on month"
              hideCaption
              columns={COLUMNS}
              rows={t.months.map((m) => ({ ...m, key: m.month }))}
              rowKey={(m) => m.key}
              totals={{
                month: "Total",
                billed: money(t.totals.billed),
                collected: money(t.totals.collected),
                expenses: money(t.totals.expenses),
                net: figure(t.totals.net_cash),
              }}
            />
          </section>
          <div className={styles.split}>
            <NetCashChart months={t.months} window={t.window.label} />
            <ExpenseTrendChart trends={t} />
          </div>
          <CashFlowChart buckets={t.weekly} granularity="week" />
          <CashFlowChart buckets={t.daily} granularity="day" />
        </div>
      )}
    </TabBody>
  );
}

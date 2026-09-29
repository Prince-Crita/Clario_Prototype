/**
 * Trends & Analysis (plan §22.2, §27.10): a highlights band first (a month, a client or a
 * category picked from the server's rows, or a count of them: never a computed amount; the first
 * in Crita green), then a sticky segmented jump bar over the sections:
 *   Performance → Cash movement → Revenue & billing → Expenses → Profitability
 * Monthly views follow the period; weekly and daily cash keep their fixed windows. The month table
 * shows the server's totals only for "All imported data" (the UI never sums).
 */
import { BasisTag, DataTable, type Column } from "../../../design-system";
import type { FinanceOverview, FinanceTrends, MonthFigures } from "../../../lib/api/types";
import { CashFlowChart, ExpenseTrendChart, MonthlyChart, NetCashChart } from "../components/charts";
import { PnlStatement } from "../components/PnlStatement";
import { RankedBars } from "../components/RankedBars";
import { AskLink, Section } from "../components/Section";
import { isNegative, isZero, money, monthLabel, percent, plot } from "../format";
import { useFinanceTab } from "../hooks";
import { inPeriod } from "../period";
import { both } from "../query";
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

const CHAPTERS = [
  { id: "performance", label: "Performance" },
  { id: "cash", label: "Cash movement" },
  { id: "revenue", label: "Revenue & billing" },
  { id: "expenses", label: "Expenses" },
  { id: "profitability", label: "Profitability" },
];

/** The row with the largest value of `key` (selection only). */
function peak(rows: MonthFigures[], key: "billed" | "collected"): MonthFigures | undefined {
  return rows.reduce<MonthFigures | undefined>(
    (best, row) => (!best || plot(row[key]) > plot(best[key]) ? row : best),
    undefined,
  );
}

/** One fact the server's rows point to, linking to the section that shows it. */
function Highlight({
  href,
  label,
  value,
  note,
}: {
  href: string;
  label: string;
  value: string;
  note?: string | undefined;
}) {
  return (
    <li>
      <a href={href} className={styles.highlight}>
        <span className={styles.highlightLabel}>{label}</span>
        <span className={styles.highlightValue}>{value}</span>
        {note ? <span className={styles.highlightNote}>{note}</span> : null}
      </a>
    </li>
  );
}

export function TrendsTab({ workspaceId, connectionId, period, ask }: TabProps) {
  const trends = useFinanceTab<FinanceTrends>(workspaceId, connectionId, "trends");
  const overview = useFinanceTab<FinanceOverview>(workspaceId, connectionId, "overview");
  return (
    <TabBody query={both(trends, overview)}>
      {([t, o]) => {
        const months = t.months.filter((m) => inPeriod(m.month, period));
        const window = period.from ? period.range : t.window.label;
        const filtered = {
          ...t,
          expense_trend: t.expense_trend.filter((m) => inPeriod(m.month, period)),
          window: { ...t.window, label: window },
        };
        const none = months.length === 0;
        const billedPeak = peak(months, "billed");
        const collectedPeak = peak(months, "collected");
        const negativeMonths = months.filter((m) => isNegative(m.net_cash)).length;
        const topClient = o.revenue_by_client[0];
        const topCost = o.expense_mix[0];
        const empty = (
          <p className={styles.pending}>
            No imported months fall in {period.name.toLowerCase()} ({period.range}). Choose another
            period, or All imported data ({t.window.label}).
          </p>
        );
        return (
          <div className={styles.stack}>
            <section aria-label="Trend highlights">
              <ul className={styles.highlights}>
                {billedPeak ? (
                  <Highlight
                    href="#performance"
                    label="Highest billing"
                    value={monthLabel(billedPeak.month)}
                    note={money(billedPeak.billed)}
                  />
                ) : null}
                {collectedPeak ? (
                  <Highlight
                    href="#performance"
                    label="Most collected"
                    value={monthLabel(collectedPeak.month)}
                    note={money(collectedPeak.collected)}
                  />
                ) : null}
                {none ? null : (
                  <Highlight
                    href="#cash"
                    label="More out than in"
                    value={`${negativeMonths} of ${months.length}`}
                    note="months shown"
                  />
                )}
                {topClient ? (
                  <Highlight
                    href="#revenue"
                    label="Largest client"
                    value={topClient.party_name}
                    note={`Billed ${money(topClient.billed)} in all`}
                  />
                ) : null}
                {topCost?.share ? (
                  <Highlight
                    href="#expenses"
                    label={`Largest cost · ${percent(topCost.share)} of operating`}
                    value={topCost.name}
                    note={money(topCost.amount)}
                  />
                ) : null}
              </ul>
            </section>

            <nav className={styles.jump} aria-label="Sections on this page">
              <ol>
                {CHAPTERS.map((s) => (
                  <li key={s.id}>
                    <a href={`#${s.id}`}>{s.label}</a>
                  </li>
                ))}
              </ol>
            </nav>

            <div className={styles.chapterBody}>
              <Section
                id="performance"
                eyebrow="01 · Month by month"
                title="Performance"
                description="Invoices raised, payments received and expenses paid, month by month."
                aside={
                  <AskLink ask={ask} question="How has our performance changed month by month?" />
                }
              >
                {none ? (
                  empty
                ) : (
                  <>
                    <MonthlyChart months={months} window={window} />
                    <section className={styles.panelFlush} aria-labelledby="mom-title">
                      <header className={`${styles.panelHeader} ${styles.tableHead}`}>
                        <div>
                          <h3 id="mom-title" className={styles.panelTitle}>
                            Month on month
                          </h3>
                          <p className={styles.muted}>
                            Cash collected against expenses, with the net each month
                          </p>
                        </div>
                        <BasisTag basis="cash" window={window} />
                      </header>
                      <DataTable
                        caption="Month on month"
                        hideCaption
                        columns={COLUMNS}
                        rows={months.map((m) => ({ ...m, key: m.month }))}
                        rowKey={(m) => m.key}
                        {...(period.from
                          ? {}
                          : {
                              totals: {
                                month: "Total",
                                billed: money(t.totals.billed),
                                collected: money(t.totals.collected),
                                expenses: money(t.totals.expenses),
                                net: figure(t.totals.net_cash),
                              },
                            })}
                      />
                      {period.from ? (
                        <p className={`${styles.note} ${styles.tableNote}`}>
                          Totals are shown for All imported data ({t.window.label}).
                        </p>
                      ) : null}
                    </section>
                  </>
                )}
              </Section>

              <Section
                id="cash"
                eyebrow="02 · In and out"
                title="Cash movement"
                description="Money in from customers against money out on expenses."
                aside={
                  <AskLink
                    ask={ask}
                    question="How did cash collection change over the last few months?"
                  />
                }
              >
                {none ? empty : <NetCashChart months={months} window={window} />}
                <div className={styles.split}>
                  <CashFlowChart buckets={t.weekly} granularity="week" />
                  <CashFlowChart buckets={t.daily} granularity="day" />
                </div>
              </Section>

              <Section
                id="revenue"
                eyebrow="03 · Who pays"
                title="Revenue & billing"
                description="Who the business bills, and what each client still owes."
                aside={<AskLink ask={ask} question="Which customers bring in the most revenue?" />}
              >
                <RankedBars
                  title="Revenue by client"
                  description="Everything billed to each client"
                  basis="billed"
                  window="all time"
                  rows={o.revenue_by_client.map((c) => ({
                    key: c.party_name,
                    label: c.party_name,
                    value: money(c.billed),
                    amount: c.billed,
                    flag: c.has_overdue ? `Overdue ${money(c.overdue)}` : undefined,
                    note:
                      !c.has_overdue && !isZero(c.outstanding)
                        ? `Owes ${money(c.outstanding)}`
                        : undefined,
                  }))}
                />
              </Section>

              <Section
                id="expenses"
                eyebrow="04 · Where it goes"
                title="Expenses"
                description="Where the money goes, and how spending by category moves month to month."
                aside={<AskLink ask={ask} question="What are our biggest expenses this year?" />}
              >
                <div className={`${styles.split} ${styles.wideLeft}`}>
                  {none ? empty : <ExpenseTrendChart trends={filtered} />}
                  <RankedBars
                    title="Where the money goes"
                    description="Operating expenses by account, excluding GST"
                    basis="accrual"
                    window={o.expense_mix_window.label}
                    rows={o.expense_mix.map((e) => ({
                      key: e.name,
                      label: e.name,
                      value: money(e.amount),
                      amount: e.amount,
                      note: e.share ? `${percent(e.share)} of operating expenses` : undefined,
                    }))}
                  />
                </div>
              </Section>

              <Section
                id="profitability"
                eyebrow="05 · What is left"
                title="Profitability"
                description="Revenue less the cost of sales and operating expenses (accrual)."
                aside={
                  <AskLink ask={ask} question="What is hurting our profit this financial year?" />
                }
              >
                <div className={styles.split}>
                  <PnlStatement pnl={o.pnl} />
                  <section className={styles.panel} aria-labelledby="drivers-title">
                    <h3 id="drivers-title" className={styles.panelTitle}>
                      What drives it
                    </h3>
                    <dl className={styles.statement}>
                      <div>
                        <dt>Gross margin</dt>
                        <dd>{percent(o.pnl.gross_margin)}</dd>
                      </div>
                      <div>
                        <dt>Net margin</dt>
                        <dd
                          className={
                            isNegative(o.pnl.net_margin ?? "0") ? styles.negative : undefined
                          }
                        >
                          {percent(o.pnl.net_margin)}
                        </dd>
                      </div>
                      {o.pnl.largest_cost ? (
                        <div>
                          <dt>Largest cost: {o.pnl.largest_cost.name}</dt>
                          <dd>{money(o.pnl.largest_cost.amount)}</dd>
                        </div>
                      ) : null}
                      <div>
                        <dt>Spent this month so far (cash)</dt>
                        <dd>{money(o.pnl.latest_month_spend)}</dd>
                      </div>
                    </dl>
                    <p className={styles.note}>
                      Accrual basis, {o.pnl.window.label}. Monthly profit and loss is not available
                      from the books yet.
                    </p>
                  </section>
                </div>
              </Section>
            </div>
          </div>
        );
      }}
    </TabBody>
  );
}

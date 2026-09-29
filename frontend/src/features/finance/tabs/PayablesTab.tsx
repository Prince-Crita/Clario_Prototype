/**
 * Payable — "what do we owe, and where is money going?" (plan §27.10). Mirrors Receivables: the
 * answer beside the liability groups, then the accounts, money going out and vendor bills.
 *
 * Built from what the finance API provides today: liability balances from the balance sheet and
 * cash spending from Trends. Vendor bills and their due dates are not imported yet, so "who do we
 * owe, what is overdue, what is due soon" is a clearly labelled section of what arrives with bill
 * import, never invented figures.
 */
import { DataTable, Figure, type Column } from "../../../design-system";
import type { FinanceBalanceSheet, FinanceTrends } from "../../../lib/api/types";
import { CashFlowChart, ExpenseTrendChart } from "../components/charts";
import { AskLink, Section } from "../components/Section";
import { dateLabel, isNegative, money } from "../format";
import { useFinanceTab } from "../hooks";
import { inPeriod } from "../period";
import { both } from "../query";
import { TabBody, type TabProps } from "./TabBody";
import styles from "./tabs.module.css";

const LIABILITY = /liabilit|payable|creditor|loan|borrow|credit card|duties|provision|overdraft/i;
const PAYABLE = /accounts payable|sundry creditors|trade creditors|creditors/i;

interface Line {
  key: string;
  group: string;
  name: string;
  balance: string;
}

const COLUMNS: Column<Line>[] = [
  { key: "group", header: "Group", cell: (l) => l.group },
  { key: "name", header: "Account", cell: (l) => l.name },
  {
    key: "balance",
    header: "Balance",
    align: "end",
    cell: (l) => (
      <span className={isNegative(l.balance) ? styles.negative : undefined}>
        {money(l.balance)}
      </span>
    ),
  },
];

export function PayablesTab({ workspaceId, connectionId, period, ask }: TabProps) {
  const sheet = useFinanceTab<FinanceBalanceSheet>(workspaceId, connectionId, "balance-sheet");
  const trends = useFinanceTab<FinanceTrends>(workspaceId, connectionId, "trends");
  return (
    <TabBody query={both(sheet, trends)}>
      {([b, t]) => {
        const asOf = b.as_of ? `As of ${dateLabel(b.as_of)}` : undefined;
        const groups = b.groups.filter((g) => LIABILITY.test(g.name));
        const payable = groups.find((g) => PAYABLE.test(g.name));
        const shown = payable ? [payable, ...groups.filter((g) => g !== payable)] : groups;
        const lines: Line[] = groups.flatMap((g) =>
          g.lines.map((l) => ({
            key: `${g.name}:${l.name}`,
            group: g.name,
            name: l.name,
            balance: l.balance,
          })),
        );
        const window = period.from ? period.range : t.window.label;
        const spending = {
          ...t,
          expense_trend: t.expense_trend.filter((m) => inPeriod(m.month, period)),
          window: { ...t.window, label: window },
        };
        const first = shown[0];
        return (
          <div className={styles.stack}>
            <div className={shown.length ? styles.opening : undefined}>
              <div className={styles.answer}>
                <p className={styles.kicker}>What the business owes</p>
                <p className={styles.answerLine}>
                  {first ? (
                    <>
                      The books show <strong>{money(first.total)}</strong> owed in{" "}
                      {first.name.toLowerCase()}
                      {shown.length > 1
                        ? ` and ${shown.length - 1} other liability groups`
                        : ""}.{" "}
                      {payable
                        ? null
                        : "Vendor bills aren't imported yet, so bills and due dates aren't here."}
                    </>
                  ) : (
                    <>No liability accounts appear in the connected books.</>
                  )}
                </p>
                <AskLink ask={ask} question="What does the business owe right now?" />
              </div>
              {shown.length ? (
                <section className={styles.summary} aria-label="Liabilities">
                  {shown.slice(0, 3).map((g) => (
                    <Figure
                      key={g.name}
                      label={g.name}
                      value={money(g.total)}
                      basis="balance"
                      window={asOf}
                      context={`${g.lines.length} ${g.lines.length === 1 ? "account" : "accounts"}`}
                    />
                  ))}
                </section>
              ) : null}
            </div>

            <Section
              eyebrow="Amounts owed"
              title="Liability accounts"
              description="Liability balances as your books group them."
            >
              {shown.length ? (
                <>
                  <div className={styles.panelFlush}>
                    <DataTable
                      caption="Liability accounts"
                      hideCaption
                      columns={COLUMNS}
                      rows={lines}
                      rowKey={(l) => l.key}
                    />
                  </div>
                  {!payable ? (
                    <p className={styles.note}>
                      No accounts-payable balance appears in the connected books; the liabilities
                      above are other amounts owed (for example tax collected on sales).
                    </p>
                  ) : null}
                </>
              ) : (
                <p className={styles.pending}>
                  No liability accounts appear in the connected books as of{" "}
                  {b.as_of ? dateLabel(b.as_of) : "the latest refresh"}.
                </p>
              )}
            </Section>

            <Section
              eyebrow="Where money goes"
              title="Money going out"
              description="Expenses paid, by category and week (cash basis; vendor bill payments are not included yet)."
              aside={
                <AskLink ask={ask} question="Where is our money going and is spending rising?" />
              }
            >
              <div className={`${styles.split} ${styles.wideLeft}`}>
                <ExpenseTrendChart trends={spending} />
                <CashFlowChart buckets={t.weekly} granularity="week" />
              </div>
            </Section>

            <Section
              eyebrow="Due and overdue"
              title="Vendor bills"
              description="Who you owe, what is overdue and what falls due next."
              aside={<span className={styles.early}>Needs bill import</span>}
            >
              <div className={styles.pending}>
                <h3>Arrives when vendor bills are imported from Zoho Books</h3>
                <ul>
                  <li>Total owed to vendors, overdue and due in the next 30 days</li>
                  <li>Who you owe the most, with each vendor's open bills</li>
                  <li>Ageing of unpaid bills, like Receivables</li>
                  <li>Upcoming payments and whether payables are rising or falling</li>
                </ul>
                <p className={styles.note}>
                  Clario reads liability balances and expenses today. Bills and their due dates are
                  a separate Zoho Books dataset that isn't imported yet, so nothing here is
                  estimated.
                </p>
              </div>
            </Section>
          </div>
        );
      }}
    </TabBody>
  );
}

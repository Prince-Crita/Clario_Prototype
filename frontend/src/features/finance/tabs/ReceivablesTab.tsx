/**
 * Receivables — "where is the business's money stuck?" (plan §22.2, §27.10). The answer in words
 * beside the summary (overdue first) → how late the money is (one bar, not yet due to 90+ days)
 * beside who owes → collecting it, with Ask Clario → open invoices, most overdue first → the full
 * invoice register. Balances as of today; every
 * figure is the server's, bar widths use them for geometry only.
 */
import { DataTable, Figure, Status, type Column } from "../../../design-system";
import type { FinanceOverview, FinanceReceivables, Invoice } from "../../../lib/api/types";
import { InvoiceRegister } from "../components/InvoiceRegister";
import { RankedBars } from "../components/RankedBars";
import { AskLink, Section } from "../components/Section";
import { dateLabel, isZero, money, plot } from "../format";
import { useFinanceTab } from "../hooks";
import { both } from "../query";
import { TabBody, type TabProps } from "./TabBody";
import styles from "./tabs.module.css";

const COLUMNS: Column<Invoice>[] = [
  { key: "number", header: "Invoice", cell: (i) => i.invoice_number },
  { key: "client", header: "Client", cell: (i) => i.party_name },
  { key: "due", header: "Due", cell: (i) => (i.due_date ? dateLabel(i.due_date) : "—") },
  { key: "billed", header: "Billed", align: "end", cell: (i) => money(i.total) },
  { key: "balance", header: "Balance", align: "end", cell: (i) => money(i.balance) },
  {
    key: "age",
    header: "Overdue",
    align: "end",
    cell: (i) =>
      i.status === "overdue" ? (
        <span className={styles.negative}>
          {i.days_overdue === 1 ? "1 day" : `${i.days_overdue} days`}
        </span>
      ) : (
        <Status tone="neutral">Not yet due</Status>
      ),
  },
];

/** Debt age: calm when not yet due, stronger red the older it is. */
const AGE_TONE: Record<string, string> = {
  not_due: "var(--series-2)",
  "1_30": "var(--age-1)",
  "31_60": "var(--age-2)",
  "61_90": "var(--age-3)",
  over_90: "var(--negative)",
};

export function ReceivablesTab({ workspaceId, connectionId, ask }: TabProps) {
  const receivables = useFinanceTab<FinanceReceivables>(workspaceId, connectionId, "receivables");
  const overview = useFinanceTab<FinanceOverview>(workspaceId, connectionId, "overview");
  return (
    <TabBody query={both(receivables, overview)}>
      {([r, o]) => {
        const notDue = r.ageing.find((b) => b.key === "not_due");
        const over90 = r.ageing.find((b) => b.key === "over_90");
        const today = `As of ${dateLabel(r.meta.today)}`;
        const allOverdue = !isZero(r.outstanding) && plot(r.overdue) === plot(r.outstanding);
        return (
          <div className={styles.stack}>
            <div className={styles.opening}>
              <div className={styles.answer}>
                <p className={styles.kicker}>Where the money is stuck</p>
                <p className={styles.answerLine}>
                  {r.overdue_count > 0 ? (
                    <>
                      <strong data-tone="negative">{money(r.overdue)}</strong>{" "}
                      {allOverdue ? (
                        "is overdue, which is everything customers owe you"
                      ) : (
                        <>
                          of the <strong>{money(r.outstanding)}</strong> customers owe is overdue
                        </>
                      )}
                      {over90 && over90.count > 0 ? (
                        <>
                          , and <strong>{money(over90.amount)}</strong> of it has waited more than
                          90 days.
                        </>
                      ) : (
                        "."
                      )}
                    </>
                  ) : (
                    <>
                      Customers owe <strong>{money(r.outstanding)}</strong>, and none of it is
                      overdue.
                    </>
                  )}
                </p>
                <p className={styles.muted}>{today} · balances, most overdue first</p>
              </div>

              <section className={styles.summary} aria-label="Receivables summary">
                <Figure
                  label="Overdue"
                  value={money(r.overdue)}
                  basis="balance"
                  window={today}
                  context={`${r.overdue_count} invoices`}
                  negative={r.overdue_count > 0}
                />
                <Figure
                  label="Outstanding"
                  value={money(r.outstanding)}
                  basis="balance"
                  window={today}
                  context={`${r.open_count} open invoices`}
                />
                <Figure
                  label="Not yet due"
                  value={money(notDue?.amount ?? "0")}
                  basis="balance"
                  window={today}
                  context={`${notDue?.count ?? 0} invoices`}
                />
              </section>
            </div>

            <div className={`${styles.split} ${styles.wideLeft}`}>
              <Section
                eyebrow="Collection risk"
                title="How overdue"
                description="Outstanding balances by days past the due date: the older a debt, the less likely it is to be paid."
                aside={
                  <AskLink
                    ask={ask}
                    question="Which invoices are overdue and who should I follow up with first?"
                  />
                }
              >
                <div className={styles.ageing}>
                  <div className={styles.ageStrip} aria-hidden="true">
                    {r.ageing
                      .filter((b) => !isZero(b.amount))
                      .map((b) => (
                        <span
                          key={b.key}
                          style={{ flexGrow: plot(b.amount), background: AGE_TONE[b.key] }}
                          title={`${b.label}: ${money(b.amount)}`}
                        />
                      ))}
                  </div>
                  <ul className={styles.ageScale}>
                    {r.ageing.map((b) => (
                      <li
                        key={b.key}
                        style={{ ["--tone" as string]: AGE_TONE[b.key] ?? "var(--line-strong)" }}
                      >
                        <span className={styles.ageLabel}>{b.label}</span>
                        <span className={styles.ageAmount}>{money(b.amount)}</span>
                        <span className={styles.note}>
                          {b.count === 1 ? "1 invoice" : `${b.count} invoices`}
                          {b.key === "over_90" && b.count > 0 ? " · oldest debts" : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </Section>

              <RankedBars
                title="Who owes"
                description="Outstanding balance by client"
                basis="balance"
                window={today}
                empty="No client owes anything."
                rows={r.by_client.map((c) => ({
                  key: c.party_name,
                  label: c.party_name,
                  value: money(c.outstanding),
                  amount: c.outstanding,
                  flag: c.has_overdue ? `Overdue ${money(c.overdue)}` : undefined,
                }))}
              />
            </div>

            <div className={styles.insightRow}>
              <div>
                <h3>Collecting it</h3>
                <p>
                  The oldest debt and the largest balance come first in the lists on this page. Ask
                  Clario to lay out who to chase and in what order.
                </p>
              </div>
              <AskLink ask={ask} question="Who owes us the most and what is overdue?" />
            </div>

            <Section
              eyebrow="Every unpaid invoice"
              title="Open invoices"
              description="Most overdue first."
            >
              <div className={styles.panelFlush}>
                <DataTable
                  caption="Open invoices"
                  hideCaption
                  columns={COLUMNS}
                  rows={r.invoices}
                  rowKey={(i) => i.id}
                />
              </div>
            </Section>

            <InvoiceRegister
              workspaceId={workspaceId}
              connectionId={connectionId}
              totals={o.register_totals}
            />
          </div>
        );
      }}
    </TabBody>
  );
}

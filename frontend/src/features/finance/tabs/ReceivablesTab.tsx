/** Receivables (plan §22.2): outstanding and overdue, ageing, by client, and every open invoice,
 * most overdue first. Balances as of today. */
import { DataTable, Figure, Status, type Column } from "../../../design-system";
import type { FinanceReceivables, Invoice } from "../../../lib/api/types";
import { RankedBars } from "../components/RankedBars";
import { dateLabel, money } from "../format";
import { useFinanceTab } from "../hooks";
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

export function ReceivablesTab({ workspaceId, connectionId }: TabProps) {
  const query = useFinanceTab<FinanceReceivables>(workspaceId, connectionId, "receivables");
  return (
    <TabBody query={query}>
      {(r) => {
        const notDue = r.ageing.find((b) => b.key === "not_due");
        const today = `As of ${dateLabel(r.meta.today)}`;
        return (
          <div className={styles.stack}>
            <section
              className={`${styles.panel} ${styles.figures}`}
              aria-label="Receivables summary"
            >
              <Figure
                label="Outstanding"
                value={money(r.outstanding)}
                basis="balance"
                window={today}
                context={`${r.open_count} open invoices`}
              />
              <Figure
                label="Overdue"
                value={money(r.overdue)}
                basis="balance"
                window={today}
                context={`${r.overdue_count} invoices`}
                negative={r.overdue_count > 0}
              />
              <Figure
                label="Not yet due"
                value={money(notDue?.amount ?? "0")}
                basis="balance"
                window={today}
                context={`${notDue?.count ?? 0} invoices`}
              />
            </section>
            <div className={styles.split}>
              <RankedBars
                title="How overdue"
                description="Outstanding balances by days past the due date"
                basis="balance"
                window={today}
                rows={r.ageing.map((b) => ({
                  key: b.key,
                  label: b.label,
                  value: money(b.amount),
                  amount: b.amount,
                  note: b.count === 1 ? "1 invoice" : `${b.count} invoices`,
                  flag: b.key === "over_90" && b.count > 0 ? "Oldest debts" : undefined,
                }))}
              />
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
            <section className={styles.panel} aria-labelledby="open-title">
              <h2 id="open-title" className={styles.panelTitle}>
                Open invoices
              </h2>
              <DataTable
                caption="Open invoices"
                hideCaption
                columns={COLUMNS}
                rows={r.invoices}
                rowKey={(i) => i.id}
              />
            </section>
          </div>
        );
      }}
    </TabBody>
  );
}

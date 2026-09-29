/** GST and Balance Sheet (plan §22.2). Both await the director's definitions (Q5, Q6): they show
 * the ledger figures the PDF implies and say so plainly. */
import { Alert, BasisTag, DataTable, Figure, type Column } from "../../../design-system";
import type { FinanceBalanceSheet, FinanceGst } from "../../../lib/api/types";
import { dateLabel, isNegative, money } from "../format";
import { useFinanceTab } from "../hooks";
import { TabBody, type TabProps } from "./TabBody";
import styles from "./tabs.module.css";

export function GstTab({ workspaceId, connectionId }: TabProps) {
  const query = useFinanceTab<FinanceGst>(workspaceId, connectionId, "gst");
  return (
    <TabBody query={query}>
      {(g) => (
        <div className={styles.stack}>
          <Alert tone="info" title="Early view">
            The GST period and method are still being agreed. Until then this shows the ledger
            position as of the latest balance sheet. Check it against your GST return before filing.
          </Alert>
          <section className={styles.panel} aria-labelledby="gst-title">
            <header className={styles.panelHeader}>
              <h2 id="gst-title" className={styles.panelTitle}>
                GST position
              </h2>
              <BasisTag
                basis="ledger"
                window={g.as_of ? `as of ${dateLabel(g.as_of)}` : undefined}
              />
            </header>
            {g.net_payable === null ? (
              <p className={styles.muted}>
                No GST accounts were found in the connected books. If your organisation is
                registered for GST, check that GST is switched on in Zoho Books.
              </p>
            ) : (
              <dl className={styles.statement}>
                <div>
                  <dt>Output GST (collected on sales)</dt>
                  <dd>{money(g.output_tax ?? "0")}</dd>
                </div>
                <div>
                  <dt>Less input credit (paid on purchases)</dt>
                  <dd>− {money(g.input_tax ?? "0")}</dd>
                </div>
                <div className={styles.total}>
                  <dt>
                    {isNegative(g.net_payable) ? "Credit carried forward" : "Payable to government"}
                  </dt>
                  <dd>{money(g.net_payable.replace(/^-/, ""))}</dd>
                </div>
              </dl>
            )}
          </section>
        </div>
      )}
    </TabBody>
  );
}

interface Line {
  key: string;
  name: string;
  balance: string;
}
const LINE_COLUMNS: Column<Line>[] = [
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

export function BalanceSheetTab({ workspaceId, connectionId }: TabProps) {
  const query = useFinanceTab<FinanceBalanceSheet>(workspaceId, connectionId, "balance-sheet");
  return (
    <TabBody query={query}>
      {(b) => (
        <div className={styles.stack}>
          <Alert tone="info" title="Early view">
            What this tab should summarise is still being agreed. It lists the balance-sheet lines
            Clario has read, grouped as your books group them.
          </Alert>
          <section className={`${styles.panel} ${styles.figures}`} aria-label="Balance summary">
            <Figure
              label="Cash on hand"
              value={money(b.cash_on_hand)}
              basis="balance"
              window={b.as_of ? `as of ${dateLabel(b.as_of)}` : undefined}
              context="Bank + cash"
            />
          </section>
          <div className={styles.split}>
            {b.groups.map((group) => (
              <section key={group.name} className={styles.panel} aria-label={group.name}>
                <h2 className={styles.panelTitle}>{group.name}</h2>
                <DataTable
                  caption={group.name}
                  hideCaption
                  columns={LINE_COLUMNS}
                  rows={group.lines.map((l) => ({ ...l, key: l.name }))}
                  rowKey={(l) => l.key}
                  totals={{ name: "Total", balance: money(group.total) }}
                />
              </section>
            ))}
          </div>
        </div>
      )}
    </TabBody>
  );
}

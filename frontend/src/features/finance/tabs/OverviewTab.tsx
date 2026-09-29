/** Overview (plan §22.2): KPI band, P&L statement, attention list, billed vs collected vs spent,
 * revenue by client, where the money goes, and the invoice register. */
import type { FinanceOverview } from "../../../lib/api/types";
import { ActionList } from "../components/ActionList";
import { MonthlyChart } from "../components/charts";
import { InvoiceRegister } from "../components/InvoiceRegister";
import { KpiBand } from "../components/KpiBand";
import { PnlStatement } from "../components/PnlStatement";
import { RankedBars } from "../components/RankedBars";
import { isZero, money, percent } from "../format";
import { useFinanceTab } from "../hooks";
import { TabBody, type TabProps } from "./TabBody";
import styles from "./tabs.module.css";

export function OverviewTab({ workspaceId, connectionId }: TabProps) {
  const query = useFinanceTab<FinanceOverview>(workspaceId, connectionId, "overview");
  return (
    <TabBody query={query}>
      {(o) => {
        const collected = o.kpis.find((k) => k.key === "cash_collected");
        return (
          <div className={styles.stack}>
            <KpiBand kpis={o.kpis} />
            <div className={`${styles.split} ${styles.wideLeft}`}>
              <PnlStatement pnl={o.pnl} />
              <ActionList items={o.actions} />
            </div>
            <MonthlyChart months={o.months} window={collected?.window.label} />
            <div className={styles.split}>
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

/**
 * Overview — how the business is performing right now (plan §22.2, §27.10, §27.11):
 *   Key figures: Financial health (briefing, Net P&L, revenue vs costs) beside the Crita-green
 *   Cash position (cash on hand, collected, receivables) →
 *   a line to Clario AI (how many signals it sees; the signals themselves live there) →
 *   Cash & profitability (highlighted chart + P&L statement) →
 *   Business performance (ruled columns) beside Ask Clario and where the business stands.
 * Signals, Decision support and Scenarios — what the figures mean and what could be done — are
 * on Clario AI. Revenue by client and where the money goes live in Trends & Analysis; the invoice
 * register in Receivables.
 */
import { ArrowRight } from "lucide-react";
import { Link } from "react-router";

import type { FinanceOverview, FinanceReceivables } from "../../../lib/api/types";
import { MonthlyChart } from "../components/charts";
import { BusinessPerformance, Position } from "../components/Intelligence";
import { KeyFigures } from "../components/KeyFigures";
import { PnlStatement } from "../components/PnlStatement";
import { Section } from "../components/Section";
import { stampLabel } from "../format";
import { useFinanceTab } from "../hooks";
import { briefing, insights, signals } from "../intelligence";
import { inPeriod } from "../period";
import { both } from "../query";
import { TabBody, type TabProps } from "./TabBody";
import styles from "./tabs.module.css";

export function OverviewTab({
  workspaceId,
  connectionId,
  period,
  pageHref,
  ask,
  askCard,
}: TabProps) {
  const overview = useFinanceTab<FinanceOverview>(workspaceId, connectionId, "overview");
  const receivables = useFinanceTab<FinanceReceivables>(workspaceId, connectionId, "receivables");
  return (
    <TabBody query={both(overview, receivables)}>
      {([o, r]) => {
        const found = signals(o, r);
        const high = found.filter((s) => s.severity === "high").length;
        const months = o.months.filter((m) => inPeriod(m.month, period));
        const asOf = o.meta.freshness.as_of ? stampLabel(o.meta.freshness.as_of) : o.meta.today;
        return (
          <div className={styles.stack}>
            <KeyFigures
              kpis={o.kpis}
              pnl={o.pnl}
              receivables={r}
              briefing={briefing(o.meta.organisation, o, r, found)}
              asOf={asOf}
              ask={ask}
            />

            <div className={styles.insightRow}>
              <div>
                <h2 className={styles.rowTitle}>
                  {found.length
                    ? `${found.length} ${found.length === 1 ? "signal needs" : "signals need"} attention${high ? `, ${high} high` : ""}`
                    : "Nothing needs attention right now"}
                </h2>
                <p>
                  Clario AI explains what these figures mean, what to consider next and what could
                  happen.
                </p>
              </div>
              <Link to={pageHref("clario")} className={styles.rowLink}>
                Open Clario AI
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            </div>

            <Section
              eyebrow="The year so far"
              title="Cash & profitability"
              description="The cash that moved each month, beside the year's profit and loss."
            >
              <div className={`${styles.split} ${styles.wideLeft}`}>
                <MonthlyChart
                  months={months}
                  window={
                    period.from
                      ? period.range
                      : o.kpis.find((k) => k.key === "cash_collected")?.window.label
                  }
                />
                <PnlStatement pnl={o.pnl} />
              </div>
            </Section>

            <div className={styles.lead}>
              <Section
                eyebrow="What the figures say"
                title="Business performance"
                description="Profitability, collections and costs, read from your figures."
              >
                <BusinessPerformance items={insights(o)} ask={ask} />
              </Section>
              <div className={styles.side}>
                {askCard}
                <Position overview={o} receivables={r} />
              </div>
            </div>
          </div>
        );
      }}
    </TabBody>
  );
}

/**
 * Clario's interpretation layer on the Overview (plan §27.10):
 *   Position             where the business stands, drawn to scale (beside Signals)
 *   BusinessPerformance  what the figures say (observation → impact), in ruled columns
 *   DecisionSupport      what to consider next, as numbered rows (observation → impact → action)
 *   Scenarios            risk · current trajectory · upside: today's levers, not forecasts
 * Everything comes from `intelligence.ts` rules over server figures; bar lengths use the figures
 * for geometry only. The briefing sentence opens the page inside KeyFigures.
 */
import { ArrowRight } from "lucide-react";
import { Link } from "react-router";

import type { FinanceOverview, FinanceReceivables } from "../../../lib/api/types";
import { isNegative, money, percent, plot } from "../format";
import type { FinanceTab } from "../hooks";
import type { Decision, Insight } from "../intelligence";
import styles from "./Intelligence.module.css";
import { AskLink } from "./Section";

type Ask = ((question: string, send?: boolean) => void) | undefined;
type Href = (tab: FinanceTab) => { pathname: string; search: string };

function Bar({ value, max, tone }: { value: string; max: number; tone: string }) {
  const width = max > 0 ? Math.max(1.5, (Math.abs(plot(value)) / max) * 100) : 0;
  return (
    <span className={styles.track} aria-hidden="true">
      <span className={styles.fill} data-tone={tone} style={{ width: `${width}%` }} />
    </span>
  );
}

export function Position({
  overview,
  receivables,
}: {
  overview: FinanceOverview;
  receivables: FinanceReceivables | undefined;
}) {
  const p = overview.pnl;
  const cash = overview.kpis.find((k) => k.key === "cash_on_hand");
  const collected = overview.kpis.find((k) => k.key === "cash_collected");
  const earnMax = Math.max(plot(p.revenue), plot(p.total_costs));
  const cashMax = Math.max(
    plot(cash?.value ?? "0"),
    plot(receivables?.outstanding ?? "0"),
    plot(p.latest_month_spend),
  );
  const loss = isNegative(p.net_pnl);
  return (
    <section className={styles.position} aria-label="Where the business stands">
      <h3 className={styles.positionTitle}>Where the business stands</h3>

      <div className={styles.block}>
        <p className={styles.blockLabel}>Earning vs spending · accrual, {p.window.label}</p>
        <dl className={styles.bars}>
          <div>
            <dt>Revenue</dt>
            <dd>
              <span>{money(p.revenue)}</span>
              <Bar value={p.revenue} max={earnMax} tone="primary" />
            </dd>
          </div>
          <div>
            <dt>Total costs</dt>
            <dd>
              <span>{money(p.total_costs)}</span>
              <Bar value={p.total_costs} max={earnMax} tone="neutral" />
            </dd>
          </div>
        </dl>
        <p className={styles.result} data-tone={loss ? "negative" : "positive"}>
          {loss ? "Net loss" : "Net profit"} {money(p.net_pnl)}
          <span> · {percent(p.net_margin)} margin</span>
        </p>
      </div>

      <div className={styles.block}>
        <p className={styles.blockLabel}>Cash and what is owed to you · balances today</p>
        <dl className={styles.bars}>
          {cash ? (
            <div>
              <dt>Cash on hand</dt>
              <dd>
                <span>{money(cash.value)}</span>
                <Bar value={cash.value} max={cashMax} tone="primary" />
              </dd>
            </div>
          ) : null}
          {receivables ? (
            <div>
              <dt>Receivables</dt>
              <dd>
                <span>{money(receivables.outstanding)}</span>
                <span className={styles.track} aria-hidden="true">
                  <span
                    className={styles.fill}
                    data-tone="accent"
                    style={{
                      width: `${cashMax > 0 ? (plot(receivables.outstanding) / cashMax) * 100 : 0}%`,
                    }}
                  >
                    <span
                      className={styles.overdueFill}
                      style={{
                        width: `${plot(receivables.outstanding) > 0 ? (plot(receivables.overdue) / plot(receivables.outstanding)) * 100 : 0}%`,
                      }}
                    />
                  </span>
                </span>
                <p className={styles.barNote}>
                  <span className={styles.overdueKey} aria-hidden="true" />
                  {money(receivables.overdue)} overdue
                </p>
              </dd>
            </div>
          ) : null}
          <div>
            <dt>Spent this month so far</dt>
            <dd>
              <span>{money(p.latest_month_spend)}</span>
              <Bar value={p.latest_month_spend} max={cashMax} tone="neutral" />
            </dd>
          </div>
        </dl>
      </div>

      {collected?.ratio && collected.related ? (
        <div className={styles.block}>
          <p className={styles.blockLabel}>Collections · {collected.window.label}</p>
          <p className={styles.collection}>
            <strong>{percent(collected.ratio)}</strong> of {money(collected.related.amount)}{" "}
            {collected.related.name} collected
          </p>
          <span className={styles.track} aria-hidden="true">
            <span
              className={styles.fill}
              data-tone="accent"
              style={{ width: `${Math.min(100, plot(collected.ratio))}%` }}
            />
          </span>
        </div>
      ) : null}
    </section>
  );
}

export function BusinessPerformance({ items, ask }: { items: Insight[]; ask: Ask }) {
  return (
    <ul className={styles.insights}>
      {items.map((i) => (
        <li key={i.id} className={styles.insight} data-tone={i.tone}>
          <p className={styles.area}>{i.area}</p>
          <p className={styles.metric}>
            <span className={styles.metricValue}>{i.metric}</span>
            <span className={styles.metricLabel}>{i.metricLabel}</span>
          </p>
          <p className={styles.observation}>{i.observation}</p>
          <p className={styles.impact}>
            <span className={styles.impactLabel}>Impact</span>
            {i.impact}
          </p>
          <AskLink ask={ask} question={i.question} label="Ask why" />
        </li>
      ))}
    </ul>
  );
}

export function DecisionSupport({
  items,
  pageHref,
  ask,
}: {
  items: Decision[];
  pageHref: Href;
  ask: Ask;
}) {
  if (items.length === 0) {
    return (
      <p className={styles.empty}>
        Nothing to act on right now. Clario will suggest next steps when a signal appears.
      </p>
    );
  }
  return (
    <ol className={styles.timeline}>
      {items.map((d, index) => (
        <li key={d.id} className={styles.step} data-severity={d.severity}>
          <span className={styles.node}>{index + 1}</span>
          <div className={styles.stepBody}>
            <p className={styles.when}>{d.when}</p>
            <div className={styles.stepGrid}>
              <div>
                <p className={styles.cellLabel}>Observation</p>
                <p>{d.observation}</p>
              </div>
              <div>
                <p className={styles.cellLabel}>Impact</p>
                <p>{d.impact}</p>
              </div>
              <div>
                <p className={styles.cellLabel}>Recommended action</p>
                <p className={styles.action}>{d.action}</p>
              </div>
            </div>
            <p className={styles.stepLinks}>
              <Link to={pageHref(d.page)} className={styles.open}>
                See {d.pageLabel}
                <ArrowRight size={13} aria-hidden="true" />
              </Link>
              <AskLink ask={ask} question={d.question} />
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function Scenarios({
  overview,
  receivables,
}: {
  overview: FinanceOverview;
  receivables: FinanceReceivables | undefined;
}) {
  const cash = overview.kpis.find((k) => k.key === "cash_on_hand");
  const over90 = receivables?.ageing.find((b) => b.key === "over_90");
  return (
    <div className={styles.spectrumWrap}>
      <div className={styles.spectrum}>
        <article className={styles.scenario} data-kind="risk">
          <p className={styles.scenarioKind}>Risk</p>
          <h3>If debts over 90 days are never paid</h3>
          <p className={styles.scenarioFigure}>
            {over90
              ? `${money(over90.amount)} · ${over90.count} ${over90.count === 1 ? "invoice" : "invoices"}`
              : "—"}
          </p>
          <p className={styles.scenarioNote}>Receivables at risk</p>
        </article>
        <article className={styles.scenario} data-kind="baseline">
          <p className={styles.scenarioKind}>Current trajectory</p>
          <h3>Actual figures to date</h3>
          <dl>
            <div>
              <dt>Net P&amp;L, {overview.pnl.window.label}</dt>
              <dd data-negative={isNegative(overview.pnl.net_pnl) || undefined}>
                {money(overview.pnl.net_pnl)}
              </dd>
            </div>
            {cash ? (
              <div>
                <dt>Cash on hand, {cash.window.label.replace(/^As of/, "as of")}</dt>
                <dd>{money(cash.value)}</dd>
              </div>
            ) : null}
          </dl>
        </article>
        <article className={styles.scenario} data-kind="upside">
          <p className={styles.scenarioKind}>Upside</p>
          <h3>If every overdue invoice is collected</h3>
          <p className={styles.scenarioFigure}>
            {receivables ? `up to ${money(receivables.overdue)}` : "—"}
          </p>
          <p className={styles.scenarioNote}>Cash that would come in</p>
        </article>
      </div>
      <p className={styles.spectrumNote}>
        Levers from today's figures, not forecasts. Projected profit and cash for each case arrive
        with scenario modelling.
      </p>
    </div>
  );
}

/**
 * The Overview's panels (plan §27.12). Presentation only: every figure and sentence comes from
 * `intelligence.ts` rules over server figures, exactly as before.
 *   PerformanceInsights  what the figures say: the metric first, its one-line basis, "Ask why"
 *   DecisionRows         what is happening → why it matters → what to consider, in order
 *   ScenarioCards        risk · where things stand · upside
 * Decision support and Scenarios are also on Clario AI; those renderers are untouched, so this is
 * a second presentation of the same content, not a change to it.
 */
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { Link, type To } from "react-router";

import type { FinanceOverview, FinanceReceivables } from "../../../lib/api/types";
import { isNegative, money, percent } from "../format";
import type { FinanceTab } from "../hooks";
import type { Decision, Insight } from "../intelligence";
import styles from "./OverviewPanels.module.css";

type Ask = ((question: string, send?: boolean) => void) | undefined;
type Href = (tab: FinanceTab) => To;

// ---------------------------------------------------------------- what the figures say

export function PerformanceInsights({ items, ask }: { items: Insight[]; ask: Ask }) {
  return (
    <ul className={styles.insights}>
      {items.map((i) => (
        <li key={i.id} className={styles.insight} data-tone={i.tone}>
          <p className={styles.insightArea}>{i.area}</p>
          <p className={styles.insightMetric}>
            <span className={styles.insightValue}>{i.metric}</span>
            <span className={styles.insightLabel}>{i.metricLabel}</span>
          </p>
          <p className={styles.insightText}>{i.observation}</p>
          {ask ? (
            <button
              type="button"
              className={styles.insightAsk}
              onClick={() => ask(i.question)}
              aria-label={`Ask Clario: ${i.question}`}
              title={`Ask Clario: “${i.question}”`}
            >
              Ask why
              <ArrowUpRight size={13} aria-hidden="true" />
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------- what to consider next

export function DecisionRows({
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
      <p className={styles.clear}>
        Nothing to act on right now. Clario will suggest next steps when a signal appears.
      </p>
    );
  }
  return (
    <ol className={styles.decisions}>
      {items.map((d, index) => (
        <li key={d.id} className={styles.decision} data-severity={d.severity}>
          <div className={styles.decisionWhen}>
            <span className={styles.decisionNo}>{String(index + 1).padStart(2, "0")}</span>
            <span className={styles.decisionChip}>{d.when}</span>
          </div>
          <div className={styles.decisionCell}>
            <p className={styles.cellLabel}>What is happening</p>
            <p className={styles.cellLead}>{d.observation}</p>
          </div>
          <div className={styles.decisionCell}>
            <p className={styles.cellLabel}>Why it matters</p>
            <p>{d.impact}</p>
          </div>
          <div className={styles.decisionCell} data-action>
            <p className={styles.cellLabel}>What to consider</p>
            <p>{d.action}</p>
            <p className={styles.decisionLinks}>
              <Link to={pageHref(d.page)} className={styles.decisionOpen}>
                See {d.pageLabel}
                <ArrowRight size={13} aria-hidden="true" />
              </Link>
              {ask ? (
                <button
                  type="button"
                  className={styles.insightAsk}
                  onClick={() => ask(d.question)}
                  aria-label={`Ask Clario: ${d.question}`}
                  title={`Ask Clario: “${d.question}”`}
                >
                  Ask Clario
                  <ArrowUpRight size={13} aria-hidden="true" />
                </button>
              ) : null}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

// ---------------------------------------------------------------- what could happen

export function ScenarioCards({
  overview,
  receivables,
}: {
  overview: FinanceOverview;
  receivables: FinanceReceivables | undefined;
}) {
  const cash = (overview.kpis ?? []).find((k) => k.key === "cash_on_hand");
  const over90 = (receivables?.ageing ?? []).find((b) => b.key === "over_90");
  return (
    <div className={styles.scenarios}>
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
        <dl className={styles.scenarioFacts}>
          <div>
            <dt>Net P&amp;L, {overview.pnl.window.label}</dt>
            <dd data-negative={isNegative(overview.pnl.net_pnl) || undefined}>
              {money(overview.pnl.net_pnl)}
              {overview.pnl.net_margin !== null ? (
                <span className={styles.scenarioMeta}>
                  {percent(overview.pnl.net_margin)} margin
                </span>
              ) : null}
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
  );
}

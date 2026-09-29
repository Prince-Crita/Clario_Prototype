/**
 * The Overview's opening composition (plan §27.10): the six headline figures, not as six equal
 * tiles, but as two questions a director asks first.
 *   Financial health (white, wide)  — today's briefing in words, Net P&L at display size, then
 *                                     revenue against total costs drawn to scale.
 *   Cash position (Crita green)     — cash on hand, cash collected and what customers still owe.
 * Every figure keeps its label, value, one context line from server fields, its basis and window,
 * and "Ask". Bar lengths use the figures for geometry only; nothing here is summed.
 */
import type { ReactNode } from "react";

import type { FinanceOverview, FinanceReceivables, Kpi } from "../../../lib/api/types";
import { isNegative, money, percent, plot } from "../format";
import styles from "./KeyFigures.module.css";
import { AskLink } from "./Section";

type Ask = ((question: string, send?: boolean) => void) | undefined;

const QUESTIONS: Record<string, string> = {
  revenue: "What's our revenue this financial year?",
  net_pnl: "Are we making a profit this year?",
  cash_on_hand: "How much cash do we have on hand?",
  cash_collected: "How much cash have we collected from customers this financial year?",
  total_costs: "What are our biggest expenses this year?",
  receivables: "How much do customers owe us in total?",
};

function context(kpi: Kpi) {
  const { change } = kpi;
  if (kpi.key === "cash_collected" && kpi.related) {
    return `${percent(kpi.ratio)} of ${money(kpi.related.amount)} ${kpi.related.name}`;
  }
  if (kpi.key === "net_pnl" && kpi.ratio !== null && kpi.ratio !== undefined) {
    return (
      <span data-tone={isNegative(kpi.ratio) ? "negative" : "positive"}>
        {percent(kpi.ratio)} margin
      </span>
    );
  }
  if (kpi.key === "receivables" && kpi.count !== null && kpi.count !== undefined) {
    return (
      <span data-tone={kpi.count > 0 ? "negative" : undefined}>
        {`${kpi.count} ${kpi.note ?? ""}`.trim()}
      </span>
    );
  }
  if (change && change.percent !== null) {
    const down = isNegative(change.percent);
    // For costs, down is good news: the arrow says the direction, the colour says good or bad.
    return (
      <>
        <span data-tone={down ? "positive" : "negative"}>
          <span aria-hidden="true">{down ? "▼" : "▲"}</span>{" "}
          {percent(change.percent.replace(/^-/, ""))} {down ? "lower" : "higher"}
        </span>{" "}
        · <span className={styles.muted}>{change.compared_to.toLowerCase()}</span>
      </>
    );
  }
  return kpi.note ?? null;
}

function Figure({
  kpi,
  size,
  ask,
  children,
}: {
  kpi: Kpi;
  size: "hero" | "lead" | "row";
  ask: Ask;
  children?: ReactNode;
}) {
  return (
    <figure className={styles.figure} data-size={size}>
      <figcaption className={styles.label}>{kpi.label}</figcaption>
      <p className={styles.value} data-negative={isNegative(kpi.value) || undefined}>
        {money(kpi.value)}
      </p>
      <p className={styles.context}>{context(kpi)}</p>
      {children}
      <p className={styles.basis}>
        {kpi.basis} · {kpi.window.label}
      </p>
      <span className={styles.ask}>
        <AskLink
          ask={ask}
          question={QUESTIONS[kpi.key] ?? `Tell me about ${kpi.label}`}
          label="Ask"
        />
      </span>
    </figure>
  );
}

/** A proportion drawn as a bar (decorative; the figure beside it carries the number). */
function Meter({ share, tone }: { share: number; tone: "ink" | "negative" }) {
  const width = Number.isFinite(share) ? Math.max(0, Math.min(100, share)) : 0;
  return (
    <span className={styles.meter} aria-hidden="true">
      <span className={styles.meterFill} data-tone={tone} style={{ width: `${width}%` }} />
    </span>
  );
}

export function KeyFigures({
  kpis,
  pnl,
  receivables,
  briefing,
  asOf,
  ask,
}: {
  kpis: Kpi[];
  pnl: FinanceOverview["pnl"];
  receivables: FinanceReceivables | undefined;
  briefing: string[];
  asOf: string;
  ask: Ask;
}) {
  const by = (key: string) => kpis.find((k) => k.key === key);
  const known = [
    "net_pnl",
    "revenue",
    "total_costs",
    "cash_on_hand",
    "cash_collected",
    "receivables",
  ];
  const others = kpis.filter((k) => !known.includes(k.key));
  const net = by("net_pnl");
  const revenue = by("revenue");
  const costs = by("total_costs");
  const cash = by("cash_on_hand");
  const collected = by("cash_collected");
  const owed = by("receivables");

  const earn = Math.max(plot(pnl.revenue), 0);
  const spend = Math.max(plot(pnl.total_costs), 0);
  const scale = Math.max(earn, spend);
  const outstanding = receivables ? plot(receivables.outstanding) : 0;

  return (
    <section className={styles.hero} aria-label="Key figures">
      <div className={styles.health}>
        <div className={styles.healthHead}>
          <p className={styles.kicker}>Financial health</p>
          <p className={styles.stamp}>Briefing · {asOf}</p>
        </div>
        <p className={styles.briefing}>
          {briefing.map((line, i) => (
            <span key={line} className={i === 0 ? styles.briefingFirst : undefined}>
              {line}{" "}
            </span>
          ))}
        </p>

        <div className={styles.healthBody}>
          {net ? <Figure kpi={net} size="hero" ask={ask} /> : null}
          <div className={styles.compare}>
            {scale > 0 ? (
              <div className={styles.scale} aria-hidden="true">
                <span className={styles.scaleRow}>
                  <span className={styles.scaleKey}>In</span>
                  <span className={styles.scaleTrack}>
                    <span
                      className={styles.scaleFill}
                      data-tone="in"
                      style={{ width: `${(earn / scale) * 100}%` }}
                    />
                  </span>
                </span>
                <span className={styles.scaleRow}>
                  <span className={styles.scaleKey}>Out</span>
                  <span className={styles.scaleTrack}>
                    <span
                      className={styles.scaleFill}
                      data-tone="out"
                      style={{ width: `${(spend / scale) * 100}%` }}
                    />
                  </span>
                </span>
              </div>
            ) : null}
            <div className={styles.pair}>
              {revenue ? <Figure kpi={revenue} size="lead" ask={ask} /> : null}
              {costs ? <Figure kpi={costs} size="lead" ask={ask} /> : null}
              {others.slice(0, 6 - (kpis.length - others.length)).map((k) => (
                <Figure key={k.key} kpi={k} size="lead" ask={ask} />
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className={styles.cash}>
        <p className={styles.kicker}>Cash position</p>
        {cash ? <Figure kpi={cash} size="hero" ask={ask} /> : null}
        <div className={styles.cashRows}>
          {collected ? (
            <Figure kpi={collected} size="row" ask={ask}>
              {collected.ratio ? <Meter share={plot(collected.ratio)} tone="ink" /> : null}
            </Figure>
          ) : null}
          {owed ? (
            <Figure kpi={owed} size="row" ask={ask}>
              {receivables && outstanding > 0 ? (
                <Meter share={(plot(receivables.overdue) / outstanding) * 100} tone="negative" />
              ) : null}
            </Figure>
          ) : null}
        </div>
      </div>
    </section>
  );
}

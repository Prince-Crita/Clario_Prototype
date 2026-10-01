/**
 * The six headline figures on the Overview (plan §27.12).
 *
 * Laid out as one row across the top of the page: a deep-green "cash card" leads five compact
 * metric cards. All six stay inside one "Key figures" region, so the set the director asked for
 * remains a single, checkable group: Revenue, Net P&L, Cash on hand, Cash collected, Total costs,
 * Receivables. Every figure keeps its label, value, one context line built from server fields, and
 * its basis and window. Nothing here is summed or derived.
 */
import { ArrowUpRight } from "lucide-react";

import { ApertureMark } from "../../../brand/ApertureMark";
import type { Kpi } from "../../../lib/api/types";
import { isNegative, money, percent } from "../format";
import styles from "./KeyFigures.module.css";

type Ask = ((question: string, send?: boolean) => void) | undefined;

const ORDER = [
  "cash_on_hand",
  "revenue",
  "net_pnl",
  "cash_collected",
  "total_costs",
  "receivables",
];

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
        <span className={styles.muted}>{change.compared_to.toLowerCase()}</span>
      </>
    );
  }
  return kpi.note ?? null;
}

/** The circular "ask about this figure" button the reference puts at a card's top-right. */
function AskDot({ ask, question }: { ask: Ask; question: string }) {
  if (!ask) return null;
  return (
    <button
      type="button"
      className={styles.dot}
      onClick={() => ask(question)}
      aria-label={`Ask Clario: ${question}`}
      title={`Ask Clario: “${question}”`}
    >
      <ArrowUpRight size={14} aria-hidden="true" />
    </button>
  );
}

function Metric({ kpi, ask }: { kpi: Kpi; ask: Ask }) {
  const question = QUESTIONS[kpi.key] ?? `Tell me about ${kpi.label}`;
  return (
    <figure className={styles.card}>
      <figcaption className={styles.label}>{kpi.label}</figcaption>
      <AskDot ask={ask} question={question} />
      <p className={styles.value} data-negative={isNegative(kpi.value) || undefined}>
        {money(kpi.value)}
      </p>
      <p className={styles.context}>{context(kpi)}</p>
      <p className={styles.basis}>
        {kpi.basis} · {kpi.window.label}
      </p>
    </figure>
  );
}

/** Cash on hand, as the page's one solid object: what the business can actually spend today. */
function CashCard({ kpi, ask }: { kpi: Kpi; ask: Ask }) {
  return (
    <figure className={styles.cash}>
      <div className={styles.cashTop}>
        <span className={styles.cashMark} aria-hidden="true">
          <ApertureMark size={20} tone="inverse" />
        </span>
        <AskDot
          ask={ask}
          question={QUESTIONS.cash_on_hand ?? "How much cash do we have on hand?"}
        />
      </div>
      <figcaption className={styles.cashLabel}>{kpi.label}</figcaption>
      <p className={styles.cashValue}>{money(kpi.value)}</p>
      <p className={styles.cashFoot}>
        <span>{kpi.note ?? "Available today"}</span>
        <span>
          {kpi.basis} · {kpi.window.label}
        </span>
      </p>
    </figure>
  );
}

export function KeyFigures({ kpis, ask }: { kpis: Kpi[]; ask: Ask }) {
  const rank = (kpi: Kpi) => (ORDER.includes(kpi.key) ? ORDER.indexOf(kpi.key) : ORDER.length);
  // Stable for unknown keys, and tolerant of a payload that carries none.
  const ordered = [...(kpis ?? [])].sort((a, b) => rank(a) - rank(b)).slice(0, 6);
  return (
    <section className={styles.figures} aria-label="Key figures">
      {ordered.map((kpi) =>
        kpi.key === "cash_on_hand" ? (
          <CashCard key={kpi.key} kpi={kpi} ask={ask} />
        ) : (
          <Metric key={kpi.key} kpi={kpi} ask={ask} />
        ),
      )}
    </section>
  );
}

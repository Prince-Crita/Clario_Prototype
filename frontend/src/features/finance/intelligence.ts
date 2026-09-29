/**
 * Clario's decision-support layer (plan §27.8): DATA → SIGNAL → INSIGHT → ACTION.
 *
 * Pure rules over figures the SERVER computed. They compare figures to choose wording, but never
 * derive a new amount: every number printed here is a server value, formatted (plan §9.2). The
 * guidance is observational and tied to the condition that triggered it; it is not financial
 * advice, and the UI says so.
 */
import type { ActionItem, FinanceOverview, FinanceReceivables, Kpi } from "../../lib/api/types";
import type { FinanceTab } from "./hooks";
import { isNegative, isZero, money, percent } from "./format";

export type Severity = "high" | "medium" | "low";

export interface Signal {
  id: string;
  category: "Collections" | "Cash" | "Tax" | "Profitability";
  severity: Severity;
  /** What happened, with the key figure. */
  headline: string;
  /** The server's supporting detail. */
  detail?: string | undefined;
  /** Up to three supporting lines (e.g. the most overdue invoices). */
  items?: { text: string; sub?: string }[];
  more?: number;
  why: string;
  consider: string;
  page: FinanceTab;
  pageLabel: string;
  question: string;
}

export interface Insight {
  id: string;
  tone: "positive" | "negative" | "neutral" | "warning";
  area: string;
  /** The headline figure of the insight, as the server formatted it. */
  metric: string;
  metricLabel: string;
  observation: string;
  impact: string;
  question: string;
}

export interface Decision {
  id: string;
  when: "This week" | "This month" | "Before the next GST return" | "Keep watching";
  severity: Severity;
  observation: string;
  impact: string;
  action: string;
  page: FinanceTab;
  pageLabel: string;
  question: string;
}

/** Comparisons only (never displayed). */
const n = (value: string | null | undefined): number => Number(value ?? 0);
const kpi = (o: FinanceOverview, key: string): Kpi | undefined => o.kpis.find((k) => k.key === key);
const RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 };
const worst = (items: ActionItem[]): Severity =>
  items.reduce<Severity>((s, i) => (RANK[i.severity] < RANK[s] ? i.severity : s), "low");

// ---------------------------------------------------------------- signals: what needs attention

export function signals(o: FinanceOverview, r: FinanceReceivables | undefined): Signal[] {
  const out: Signal[] = [];
  const overdue = o.actions.filter((a) => a.kind === "overdue_invoice");
  if (overdue.length) {
    const oldest = overdue[0];
    const allOverdue =
      r !== undefined && !isZero(r.outstanding) && n(r.overdue) === n(r.outstanding);
    out.push({
      id: "collections",
      category: "Collections",
      severity: worst(overdue),
      headline: r
        ? `${money(r.overdue)} overdue across ${r.overdue_count} ${r.overdue_count === 1 ? "invoice" : "invoices"}`
        : `${overdue.length} overdue ${overdue.length === 1 ? "invoice" : "invoices"}`,
      detail: allOverdue ? "Everything customers owe is past its due date." : undefined,
      items: overdue.slice(0, 3).map((a) => ({ text: a.title, sub: a.detail })),
      more: Math.max(0, overdue.length - 3),
      why: "Cash you have already earned is still with customers, and the older a debt gets, the harder it is to collect.",
      consider: oldest?.reference
        ? `Start with ${oldest.reference}, the longest overdue, then work down the list.`
        : "Follow up on the longest-overdue invoices first.",
      page: "receivables",
      pageLabel: "Receivables",
      question: "Which invoices are overdue and who should I follow up with first?",
    });
  }

  const cash = kpi(o, "cash_on_hand");
  if (cash && n(cash.value) < n(o.pnl.latest_month_spend) && !isZero(o.pnl.latest_month_spend)) {
    out.push({
      id: "cash",
      category: "Cash",
      severity: "medium",
      headline: `Cash on hand ${money(cash.value)} is below this month's spending so far`,
      detail: `${money(o.pnl.latest_month_spend)} has been spent this month (cash basis).`,
      why: "A thin cash buffer leaves little room if a customer pays late or a large bill falls due.",
      consider: "Bring collections forward and time larger payments after customers pay.",
      page: "balance-sheet",
      pageLabel: "Balance Sheet",
      question: "How much cash do we have and how does it compare with our spending?",
    });
  }

  for (const a of o.actions.filter((x) => x.kind === "gst_payable")) {
    out.push({
      id: "gst",
      category: "Tax",
      severity: a.severity,
      headline: a.title,
      detail: a.detail,
      why: "This amount is owed to the government with the next GST return.",
      consider: "Check it against the GST return and set the amount aside before the due date.",
      page: "gst",
      pageLabel: "GST",
      question: "What is our GST position?",
    });
  }

  for (const a of o.actions.filter((x) => x.kind === "accrual_loss")) {
    const largest = o.pnl.largest_cost;
    out.push({
      id: "loss",
      category: "Profitability",
      severity: a.severity,
      headline: a.title,
      detail: a.detail,
      why: "Costs are running ahead of revenue, so the business is funding the gap from cash.",
      consider: largest
        ? `Review ${largest.name} (${money(largest.amount)}), the largest cost, against the revenue it supports.`
        : "Review the largest cost lines against the revenue they support.",
      page: "trends",
      pageLabel: "Trends & Analysis",
      question: "What is hurting our profit this financial year?",
    });
  }
  return out.sort((a, b) => RANK[a.severity] - RANK[b.severity]);
}

// ---------------------------------------------------------------- insights: how the business performs

export function insights(o: FinanceOverview): Insight[] {
  const out: Insight[] = [];
  const p = o.pnl;
  const loss = isNegative(p.net_pnl);
  out.push({
    id: "profitability",
    tone: loss ? "negative" : "positive",
    area: "Profitability",
    metric: percent(p.net_margin),
    metricLabel: "net margin",
    observation: `${loss ? "Net loss" : "Net profit"} of ${money(p.net_pnl.replace(/^-/, ""))} on revenue of ${money(p.revenue)}, ${p.window.label}.`,
    impact: loss
      ? `Total costs of ${money(p.total_costs)} are larger than revenue, so the business is spending more than it earns.`
      : "Revenue covers costs, and the business is generating a surplus from operations.",
    question: loss ? "Why are we making a loss this year?" : "How profitable are we this year?",
  });

  if (p.gross_margin !== null && p.gross_margin !== undefined) {
    out.push({
      id: "gross",
      tone: n(p.operating_expenses) > n(p.gross_profit) ? "warning" : "neutral",
      area: "Gross margin",
      metric: percent(p.gross_margin),
      metricLabel: "gross margin",
      observation: `After direct costs of ${money(p.cogs)}, ${money(p.gross_profit)} of revenue remains to cover operating expenses.`,
      impact:
        n(p.operating_expenses) > n(p.gross_profit)
          ? `Operating expenses of ${money(p.operating_expenses)} are larger than that, which is where the loss comes from.`
          : `Operating expenses of ${money(p.operating_expenses)} fit within it.`,
      question: "What is our gross margin and what are our operating expenses?",
    });
  }

  const collected = kpi(o, "cash_collected");
  if (collected?.ratio && collected.related) {
    const strong = n(collected.ratio) >= 90;
    out.push({
      id: "collections",
      tone: strong ? "positive" : "warning",
      area: "Collections",
      metric: percent(collected.ratio),
      metricLabel: `of ${collected.related.name} collected`,
      observation: `${money(collected.value)} collected against ${money(collected.related.amount)} ${collected.related.name}, ${collected.window.label}.`,
      impact: strong
        ? "Billing is turning into cash reliably."
        : "Billing is running ahead of collections, so cash lags revenue.",
      question: "How has cash collection changed over the last few months?",
    });
  }

  const costs = kpi(o, "total_costs");
  if (costs?.change?.percent !== null && costs?.change?.percent !== undefined) {
    const down = isNegative(costs.change.percent);
    out.push({
      id: "spending",
      tone: down ? "positive" : "warning",
      area: "Spending",
      metric: `${down ? "▼" : "▲"} ${percent(costs.change.percent.replace(/^-/, ""))}`,
      metricLabel: down ? "lower" : "higher",
      observation: `${costs.change.compared_to}: ${percent(costs.change.percent.replace(/^-/, ""))} ${down ? "lower" : "higher"}.`,
      impact: down
        ? "Spending is easing month on month."
        : "Spending is rising month on month; the category breakdown shows what drove it.",
      question: "What are our biggest expenses and how is spending changing?",
    });
  }

  const top = o.revenue_by_client[0];
  const total = o.register_totals.billed;
  if (top && n(top.billed) * 2 > n(total) && o.revenue_by_client.length > 1) {
    out.push({
      id: "concentration",
      tone: "warning",
      area: "Client concentration",
      metric: money(top.billed),
      metricLabel: `billed to ${top.party_name}`,
      observation: `${top.party_name} accounts for ${money(top.billed)} of ${money(total)} billed in total.`,
      impact:
        "More than half of billing depends on one client, so a delay or loss there would be felt across the business.",
      question: `How much have we billed ${top.party_name} and what do they owe?`,
    });
  }

  const biggest = o.expense_mix[0];
  if (biggest?.share) {
    out.push({
      id: "cost-mix",
      tone: "neutral",
      area: "Cost structure",
      metric: percent(biggest.share),
      metricLabel: "of operating expenses",
      observation: `${biggest.name} is the largest operating expense at ${money(biggest.amount)}, ${o.expense_mix_window.label}.`,
      impact: "Most of the cost base sits in one account, so that is where changes matter most.",
      question: "What are our biggest expenses this year?",
    });
  }
  return out;
}

// ---------------------------------------------------------------- decisions: what to consider doing

const WHEN_ORDER: Decision["when"][] = [
  "This week",
  "Before the next GST return",
  "This month",
  "Keep watching",
];

export function decisions(
  o: FinanceOverview,
  r: FinanceReceivables | undefined,
  s: Signal[],
): Decision[] {
  const out: Decision[] = [];
  const collections = s.find((x) => x.id === "collections");
  if (collections) {
    const over90 = r?.ageing.find((b) => b.key === "over_90");
    out.push({
      id: "collect",
      when: "This week",
      severity: collections.severity,
      observation: collections.headline + ".",
      impact:
        over90 && over90.count > 0
          ? `${money(over90.amount)} of it is more than 90 days late, the debt least likely to be paid.`
          : "Cash conversion is slower than the invoices' terms.",
      action: collections.consider,
      page: "receivables",
      pageLabel: "Receivables",
      question: collections.question,
    });
  }
  const cash = s.find((x) => x.id === "cash");
  if (cash) {
    out.push({
      id: "cash",
      when: "This week",
      severity: "medium",
      observation: cash.headline + ".",
      impact: cash.why,
      action: cash.consider,
      page: "balance-sheet",
      pageLabel: "Balance Sheet",
      question: cash.question,
    });
  }
  const gst = s.find((x) => x.id === "gst");
  if (gst) {
    out.push({
      id: "gst",
      when: "Before the next GST return",
      severity: gst.severity,
      observation: gst.headline + ".",
      impact: gst.why,
      action: gst.consider,
      page: "gst",
      pageLabel: "GST",
      question: gst.question,
    });
  }
  const loss = s.find((x) => x.id === "loss");
  if (loss) {
    out.push({
      id: "costs",
      when: "This month",
      severity: loss.severity,
      observation: loss.headline + ".",
      impact: loss.why,
      action: loss.consider,
      page: "trends",
      pageLabel: "Trends & Analysis",
      question: loss.question,
    });
  }
  const top = o.revenue_by_client[0];
  if (top && n(top.billed) * 2 > n(o.register_totals.billed) && o.revenue_by_client.length > 1) {
    out.push({
      id: "concentration",
      when: "Keep watching",
      severity: "low",
      observation: `${top.party_name} accounts for ${money(top.billed)} of ${money(o.register_totals.billed)} billed.`,
      impact: "Dependence on one client raises the cost of any delay or loss there.",
      action: `Keep ${top.party_name}'s invoices current and widen the client base where you can.`,
      page: "trends",
      pageLabel: "Trends & Analysis",
      question: `What is ${top.party_name}'s billing and payment history?`,
    });
  }
  return out.sort(
    (a, b) =>
      WHEN_ORDER.indexOf(a.when) - WHEN_ORDER.indexOf(b.when) ||
      RANK[a.severity] - RANK[b.severity],
  );
}

// ---------------------------------------------------------------- the briefing: the page's lead

/**
 * Two to four sentences that open the Overview: how the business stands, in words. Every figure
 * is a server value; the sentences only choose which facts to state.
 */
export function briefing(
  organisation: string,
  o: FinanceOverview,
  r: FinanceReceivables | undefined,
  s: Signal[],
): string[] {
  const p = o.pnl;
  const lines = [
    isNegative(p.net_pnl)
      ? `${organisation} is operating at a loss this financial year: revenue of ${money(p.revenue)} against total costs of ${money(p.total_costs)}.`
      : `${organisation} is profitable this financial year: a net profit of ${money(p.net_pnl)} on revenue of ${money(p.revenue)}.`,
  ];
  if (r && r.overdue_count > 0) {
    const all = !isZero(r.outstanding) && n(r.overdue) === n(r.outstanding);
    lines.push(
      all
        ? `${money(r.overdue)} is overdue from customers, which is everything they owe.`
        : `${money(r.overdue)} of the ${money(r.outstanding)} customers owe is overdue.`,
    );
  }
  const cash = kpi(o, "cash_on_hand");
  if (cash && s.some((x) => x.id === "cash")) {
    lines.push(`Cash on hand of ${money(cash.value)} is below this month's spending so far.`);
  }
  const gst = s.find((x) => x.id === "gst");
  if (gst)
    lines.push(
      `${gst.headline.replace(/^GST payable/, "GST of")} is payable with the next return.`,
    );
  return lines;
}

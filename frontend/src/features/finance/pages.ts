/**
 * The Command Centre's six pages, in navigation order (plan §27.9), each with the question it
 * answers and a few things to ask Clario there. The prompts are questions the Finance
 * Assistant's tools can answer; they are placed or sent only when the user chooses one.
 */
import type { FinanceTab } from "./hooks";

export interface Page {
  value: FinanceTab;
  label: string;
  lede: string;
  prompts: string[];
}

export const OVERVIEW: Page = {
  value: "overview",
  label: "Overview",
  lede: "How the business is performing right now: income, costs, cash and what customers owe.",
  prompts: [
    "How are we doing this financial year?",
    "What is hurting our profit this year?",
    "What should I pay attention to?",
  ],
};

/**
 * Clario AI: the Finance Assistant with the intelligence built from the same figures (Signals,
 * Decision support, Scenarios). A product capability, not a seventh report: the top bar reaches it
 * through the Ask Clario pill rather than the report links.
 */
export const CLARIO: Page = {
  value: "clario",
  label: "Clario AI",
  lede: "Ask about your business, see what needs attention, and decide what to do next.",
  prompts: [
    "How are we doing this financial year?",
    "What is affecting our profit?",
    "Who owes us the most?",
    "Which invoices are overdue?",
    "Where are we spending the most?",
    "How did cash collection change this month?",
    "What needs my attention?",
    "What should I do next?",
  ],
};

/** The six financial reports, in navigation order. */
export const PAGES: Page[] = [
  OVERVIEW,
  {
    value: "trends",
    label: "Trends & Analysis",
    lede: "How performance, cash, billing and spending are moving over time.",
    prompts: [
      "How did cash collection change over the last few months?",
      "Which month this financial year had the highest revenue?",
      "What are our biggest expenses this year?",
    ],
  },
  {
    value: "payables",
    label: "Payable",
    lede: "What the business owes and the money going out.",
    prompts: [
      "What does the business owe right now?",
      "Where is our money going?",
      "How has spending changed month to month?",
    ],
  },
  {
    value: "gst",
    label: "GST",
    lede: "Tax collected, tax paid and the net position.",
    prompts: [
      "What is our GST position?",
      "How much GST do we have to pay?",
      "How much input credit do we have?",
    ],
  },
  {
    value: "receivables",
    label: "Receivables",
    lede: "Where the business's money is stuck: who owes you, how late it is and what needs action.",
    prompts: [
      "Who owes us the most?",
      "Which invoices are overdue?",
      "Which invoice has been overdue the longest?",
    ],
  },
  {
    value: "balance-sheet",
    label: "Balance Sheet",
    lede: "Cash, what you own and what you owe, as your books group them.",
    prompts: [
      "How much cash do we have on hand?",
      "How much do customers owe us in total?",
      "What does the business owe right now?",
    ],
  },
];

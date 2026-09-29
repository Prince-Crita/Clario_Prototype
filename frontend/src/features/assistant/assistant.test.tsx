/**
 * The Finance Assistant on the Clario AI page (plan §26, §27.11), on the real route tree against
 * a stateful mock of the chat API.
 */
import { configure, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AssistantInfo, ChatMessage, ConversationDetail } from "../../lib/api/types";
import {
  ALPHA,
  ALPHA_DETAIL,
  CONNECTION_ID,
  expectNoA11yViolations,
  mockApi,
  renderApp,
  session,
  zohoConnection,
  zohoTile,
  type Call,
} from "../../test/harness";
import { formatWait } from "./usage";
import golden from "../finance/testing/golden-responses.json";

// The Command Centre and the panel are lazy chunks; the first load of each can take a moment.
configure({ asyncUtilTimeout: 5000 });
vi.setConfig({ testTimeout: 30_000 });

const integrations = `/workspaces/${ALPHA.id}/integrations`;
const connection = `/workspaces/${ALPHA.id}/connections/${CONNECTION_ID}`;
const assistant = `${connection}/assistant`;
const PAGE = "/w/alpha-traders/zoho-books/finance";
const AS_OF = "2026-09-25T10:26:00Z";

const INFO: AssistantInfo = {
  domain: "finance",
  display_name: "Finance Assistant",
  suggested_questions: ["Which invoices are overdue?", "Who owes us the most?"],
  available: true,
  status: { state: "available", resets_in_seconds: null, limit_scope: null },
};

type Answer = { status: number; body?: unknown } | { content: string; sources: string[] };

interface Options {
  permissions?: string[];
  info?: AssistantInfo | { status: number; body: unknown } | (() => AssistantInfo);
  needsReauth?: boolean;
  conversations?: ConversationDetail[];
  answers?: Answer[];
}

let ids = 0;
const message = (
  role: "user" | "assistant",
  content: string,
  extra: Partial<ChatMessage> = {},
): ChatMessage => ({
  id: `m-${++ids}`,
  role,
  content,
  status: "complete",
  created_at: AS_OF,
  sources: [],
  as_of: null,
  ...extra,
});

const conversation = (id: string, title: string, messages: ChatMessage[]): ConversationDetail => ({
  id,
  title,
  created_at: AS_OF,
  last_message_at: AS_OF,
  messages,
});

const summaryOf = ({ id, title, created_at, last_message_at }: ConversationDetail) => ({
  id,
  title,
  created_at,
  last_message_at,
});

/** The chat API as a small in-memory server: conversations, questions and scripted answers. */
function api(options: Options = {}) {
  const store = new Map((options.conversations ?? []).map((c) => [c.id, c]));
  const answers = [...(options.answers ?? [])];
  const c = zohoConnection(options.needsReauth ? "needs_reauth" : "connected");
  const tile = zohoTile(true, {
    ...c,
    account: c.account ? { ...c.account, name: "Crita Creative LLP" } : null,
  });
  const idOf = (call: Call) => call.path.split("/conversations/")[1]?.split("/")[0] ?? "";

  const calls = mockApi({
    "GET /auth/session": { status: 200, body: session() },
    [`GET /workspaces/${ALPHA.id}`]: {
      status: 200,
      body: {
        ...ALPHA_DETAIL,
        permissions: options.permissions ?? ["workspace.view", "finance.view", "assistant.use"],
      },
    },
    [`GET ${integrations}`]: { status: 200, body: { integrations: [tile] } },
    [`GET ${integrations}/zoho-books`]: { status: 200, body: tile },
    [`GET ${connection}/sync`]: {
      status: 200,
      body: { state: "idle", as_of: AS_OF, run: null, datasets: [] },
    },
    [`GET ${connection}/finance/overview`]: { status: 200, body: golden.overview },
    [`GET ${connection}/finance/trends`]: { status: 200, body: golden.trends },
    [`GET ${connection}/finance/receivables`]: { status: 200, body: golden.receivables },
    [`GET ${connection}/finance/invoices`]: { status: 200, body: golden.invoices },
    [`GET ${assistant}`]: () => {
      const info = typeof options.info === "function" ? options.info() : options.info;
      return info && "body" in info ? info : { status: 200, body: info ?? INFO };
    },
    [`GET ${assistant}/conversations`]: () => ({
      status: 200,
      body: {
        conversations: [...store.values()].filter((x) => x.messages.length).map(summaryOf),
      },
    }),
    [`POST ${assistant}/conversations`]: () => {
      const id = `c-${store.size + 1}`;
      const created = { ...conversation(id, "", []), title: null, last_message_at: null };
      store.set(id, created);
      return { status: 201, body: summaryOf(created) };
    },
    ...Object.fromEntries(
      ["c-1", "c-2", "c-3"].flatMap((id) => [
        [
          `GET ${assistant}/conversations/${id}`,
          () =>
            store.has(id)
              ? { status: 200, body: store.get(id) }
              : {
                  status: 404,
                  body: { code: "conversation.not_found", detail: "Conversation not found." },
                },
        ],
        [
          `DELETE ${assistant}/conversations/${id}`,
          () => {
            store.delete(id);
            return { status: 204 };
          },
        ],
        [
          `POST ${assistant}/conversations/${id}/messages`,
          (call: Call) => {
            const current = store.get(idOf(call));
            if (!current) return { status: 404, body: { code: "conversation.not_found" } };
            const question = message("user", (call.body as { content: string }).content);
            const next = answers.shift() ?? { content: "Noted.", sources: [] };
            if ("status" in next) {
              if (next.status === 503) {
                const failed = message("assistant", "", { status: "failed" });
                current.messages.push(question, failed);
              }
              return next;
            }
            const reply = message("assistant", next.content, {
              sources: next.sources,
              as_of: next.sources.length ? AS_OF : null,
            });
            current.messages.push(question, reply);
            current.title ??= question.content;
            return {
              status: 200,
              body: {
                conversation: summaryOf(current),
                user_message: question,
                assistant_message: reply,
              },
            };
          },
        ],
      ]),
    ),
  });
  return { calls, store };
}

const box = () => screen.getByRole("textbox", { name: "Ask the Finance Assistant" });
/** The conversation, once its assistant info has loaded (the box is disabled until then). */
async function panel() {
  const aside = await screen.findByRole("region", { name: "Finance Assistant" });
  await waitFor(() => expect(box()).toBeEnabled());
  return aside;
}

/** The Ask Clario pill in the top bar. */
const topBarAsk = () =>
  within(screen.getAllByRole("banner")[0] as HTMLElement).findByRole("link", {
    name: "Ask Clario",
  });

describe("Clario AI: the Finance Assistant", () => {
  it("opens as its own page from the top bar and answers a suggested question", async () => {
    const { calls } = api({
      answers: [
        {
          content: "Nine invoices are overdue, **₹58,094** in total. The oldest is INV-000002.",
          sources: ["Receivables"],
        },
      ],
    });
    const { user, router } = renderApp(`${PAGE}/overview`);
    await screen.findByRole("region", { name: "Key figures" });
    const ask = await topBarAsk();
    expect(ask).not.toHaveAttribute("aria-current");
    await user.click(ask);

    expect(router.state.location.pathname).toBe(`${PAGE}/clario`);
    expect(await screen.findByRole("heading", { level: 1, name: "Clario AI" })).toBeVisible();
    const aside = await panel();
    expect(await topBarAsk()).toHaveAttribute("aria-current", "page");
    expect(
      within(aside).getByText("Finance Assistant · Crita Creative LLP · Zoho Books"),
    ).toBeInTheDocument();
    await waitFor(() => expect(box()).toHaveFocus());
    await user.click(within(aside).getByRole("button", { name: "Which invoices are overdue?" }));

    const log = await within(aside).findByRole("log", { name: "Conversation" });
    expect(await within(log).findByText("₹58,094")).toBeInTheDocument();
    expect(log).toHaveTextContent("You asked: Which invoices are overdue?");
    expect(log).toHaveTextContent("Based on Receivables · data as of 25 Sept");
    expect(router.state.location.search).toBe("?c=c-1");
    expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual([
      `${assistant}/conversations`,
      `${assistant}/conversations/c-1/messages`,
    ]);
    // Suggestions only appear on an empty conversation.
    expect(within(aside).queryByRole("list", { name: "Suggested questions" })).toBeNull();
  });

  it("sends with Enter, keeps Shift+Enter for new lines, and never pops up on a report", async () => {
    const { calls } = api();
    const { user, router } = renderApp(`${PAGE}/clario`);
    await panel();
    await user.type(box(), "Revenue this year?{Shift>}{Enter}{/Shift}please");
    expect(box()).toHaveValue("Revenue this year?\nplease");
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Noted.")).toBeInTheDocument();
    expect(box()).toHaveValue("");

    await user.click(
      within(screen.getByRole("navigation", { name: "Finance pages" })).getByRole("link", {
        name: "Trends & Analysis",
      }),
    );
    expect(router.state.location.pathname).toBe(`${PAGE}/trends`);
    expect(router.state.location.search).toBe("");
    await screen.findByRole("table", { name: "Month on month" });
    expect(screen.queryByRole("region", { name: "Finance Assistant" })).toBeNull();
  });

  it("reopens a conversation from the URL, lists earlier ones and deletes with confirmation", async () => {
    const first = conversation("c-1", "Who owes us the most?", [
      message("user", "Who owes us the most?"),
      message("assistant", "Client A owes ₹23,965.", { sources: ["Receivables"], as_of: AS_OF }),
    ]);
    const second = conversation("c-2", "GST payable?", [
      message("user", "GST payable?"),
      message("assistant", "GST payable is ₹5,665.", { sources: ["GST"], as_of: AS_OF }),
    ]);
    const { store } = api({ conversations: [first, second] });
    const { user, router, container } = renderApp(`${PAGE}/clario?c=c-1`);
    const aside = await panel();
    expect(await within(aside).findByText("Client A owes ₹23,965.")).toBeInTheDocument();

    await user.click(within(aside).getByRole("button", { name: "Your conversations" }));
    const list = await within(aside).findByRole("navigation", { name: "Your conversations" });
    expect(within(list).getByRole("button", { name: /^Who owes us the most\?/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    await expectNoA11yViolations(container);
    await user.click(within(list).getByRole("button", { name: /^GST payable\?/ }));
    expect(await within(aside).findByText("GST payable is ₹5,665.")).toBeInTheDocument();
    expect(router.state.location.search).toBe("?c=c-2");

    await user.click(within(aside).getByRole("button", { name: "Your conversations" }));
    await user.click(await within(aside).findByRole("button", { name: "Delete “GST payable?”" }));
    await user.click(within(aside).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(store.has("c-2")).toBe(false));
    expect(router.state.location.search).toBe("");
    expect(
      await within(aside).findByRole("button", { name: /^Who owes us the most\?/ }),
    ).toBeInTheDocument();
    expect(within(aside).queryByRole("button", { name: /^GST payable\?/ })).toBeNull();
  });

  it("keeps the question when the assistant is down, and asks again", async () => {
    const down = {
      status: 503,
      body: {
        code: "assistant.unavailable",
        detail: "The assistant is temporarily unavailable; your dashboard data is unaffected.",
      },
    };
    const { calls } = api({
      answers: [down, { content: "GST payable is ₹5,665.", sources: ["GST"] }],
    });
    const { user } = renderApp(`${PAGE}/clario`);
    await panel();
    await user.type(box(), "GST payable?{Enter}");
    expect(
      await screen.findByText(/wasn't answered: the assistant was temporarily unavailable/),
    ).toBeInTheDocument();
    expect(box()).toHaveValue(""); // the question is in the transcript, not back in the box
    await user.click(screen.getByRole("button", { name: "Ask again" }));
    expect(await screen.findByText("GST payable is ₹5,665.")).toBeInTheDocument();
    const asked = calls.filter((c) => c.method === "POST" && c.path.endsWith("/messages"));
    expect(asked.map((c) => c.body)).toEqual([
      { content: "GST payable?" },
      { content: "GST payable?" },
    ]);
  });

  it("gives the typed question back when sending too quickly", async () => {
    api({
      answers: [
        {
          status: 429,
          body: {
            code: "assistant.rate_limited",
            detail: "You're sending messages quickly. Wait a moment and try again.",
          },
        },
      ],
    });
    const { user } = renderApp(`${PAGE}/clario`);
    await panel();
    await user.type(box(), "Cash on hand?{Enter}");
    expect(await screen.findByText(/sending messages quickly/)).toBeInTheDocument();
    expect(box()).toHaveValue("Cash on hand?");
  });

  it("says so when the assistant isn't set up, or the connection needs reconnecting", async () => {
    api({ info: { ...INFO, available: false }, needsReauth: true });
    renderApp(`${PAGE}/clario`);
    const aside = await screen.findByRole("region", { name: "Finance Assistant" });
    expect(await within(aside).findByText(/isn't set up on this server yet/)).toBeInTheDocument();
    expect(within(aside).getByText(/needs reconnecting, so answers use figures/)).toBeVisible();
    expect(within(aside).getByRole("link", { name: "Reconnect" })).toHaveAttribute(
      "href",
      "/w/alpha-traders/zoho-books/connection",
    );
    expect(box()).toBeDisabled();
    expect(within(aside).queryByRole("list", { name: "Suggested questions" })).toBeNull();
  });

  it("takes links from the old popup (?assistant=open) to Clario AI, keeping the conversation", async () => {
    api({
      conversations: [
        conversation("c-1", "Who owes us the most?", [
          message("user", "Who owes us the most?"),
          message("assistant", "Client A owes ₹23,965.", { sources: ["Receivables"] }),
        ]),
      ],
    });
    const { router } = renderApp(`${PAGE}/overview?assistant=open&c=c-1`);
    const aside = await panel();
    expect(router.state.location.pathname).toBe(`${PAGE}/clario`);
    expect(router.state.location.search).toBe("?c=c-1");
    expect(await within(aside).findByText("Client A owes ₹23,965.")).toBeInTheDocument();
    // No close or expand: it is a page, not a panel.
    expect(within(aside).queryByRole("button", { name: /Close|Expand/ })).toBeNull();
  });

  it("sends a question typed into a report's Ask box on Clario AI; a suggestion only places it", async () => {
    const { calls } = api({ answers: [{ content: "TEST Bluefin owes the most.", sources: [] }] });
    const { user, router } = renderApp(`${PAGE}/trends?period=fy`);
    const field = await screen.findByRole("textbox", { name: "Ask Clario a question" });
    await user.type(field, "Who owes us the most?{Enter}");

    expect(router.state.location.pathname).toBe(`${PAGE}/clario`);
    const aside = await panel();
    expect(await within(aside).findByText("TEST Bluefin owes the most.")).toBeInTheDocument();
    expect(router.state.location.search).toBe("?period=fy&c=c-1");
    expect(calls.filter((c) => c.path.endsWith("/messages")).map((c) => c.body)).toEqual([
      { content: "Who owes us the most?" },
    ]);

    await user.click(
      within(screen.getByRole("navigation", { name: "Finance pages" })).getByRole("link", {
        name: "GST",
      }),
    );
    await user.click(await screen.findByRole("button", { name: "What is our GST position?" }));
    expect(router.state.location.pathname).toBe(`${PAGE}/clario`);
    await panel();
    expect(box()).toHaveValue("What is our GST position?");
    expect(calls.filter((c) => c.path.endsWith("/messages"))).toHaveLength(1);
  });

  it("renders answers as safe text: no raw HTML, no links", async () => {
    api({
      answers: [
        {
          content:
            'Revenue is ₹7,28,540. <img src=x onerror="alert(1)"> See [the report](https://evil.example).',
          sources: ["Overview"],
        },
      ],
    });
    const { user } = renderApp(`${PAGE}/clario`);
    const aside = await panel();
    await user.type(box(), "Revenue?{Enter}");
    const log = await within(aside).findByRole("log");
    await within(log).findByText(/Revenue is ₹7,28,540\./);
    expect(log.querySelector("img")).toBeNull();
    expect(within(log).queryByRole("link")).toBeNull();
    expect(log).toHaveTextContent("See the report.");
  });

  it("without the assistant permission, Clario AI shows its intelligence but no conversation", async () => {
    api({ permissions: ["workspace.view", "finance.view"] });
    renderApp(`${PAGE}/clario`);
    expect(await screen.findByRole("heading", { level: 1, name: "Clario AI" })).toBeVisible();
    expect(await screen.findByRole("region", { name: "Signals" })).toBeInTheDocument();
    expect(screen.getByText("Ask Clario isn't available for your role")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Finance Assistant" })).toBeNull();
    expect(screen.queryByRole("textbox", { name: "Ask Clario a question" })).toBeNull();
  });

  it("shows the AI usage limit with the server's reset time, and keeps the question", async () => {
    let limited = false;
    const LIMIT = {
      code: "assistant.limit_reached",
      detail: "AI usage limit reached. Your dashboard data is unaffected.",
      resets_in_seconds: 31331,
      limit_scope: "daily",
    };
    api({
      info: () =>
        limited
          ? {
              ...INFO,
              status: { state: "limit_reached", resets_in_seconds: 31331, limit_scope: "daily" },
            }
          : INFO,
      answers: [{ status: 429, body: LIMIT }],
    });
    const { user } = renderApp(`${PAGE}/clario`);
    const aside = await panel();
    expect(within(aside).getByText("Available")).toBeInTheDocument();
    limited = true; // the server records Groq's 429, so its status now reports the limit
    await user.type(box(), "Revenue this year?{Enter}");

    const alert = await within(aside).findByRole("alert");
    expect(alert).toHaveTextContent("AI usage limit reached");
    expect(alert).toHaveTextContent("Available again in 8h 42m.");
    expect(alert).toHaveTextContent("Your dashboard data is unaffected.");
    expect(within(aside).getByText("Usage limit reached")).toBeInTheDocument();
    expect(within(aside).queryByText("Available")).toBeNull();
    expect(box()).toBeDisabled();
    expect(box()).toHaveValue("Revenue this year?"); // not stored: the question stays in the box
    expect(box()).toHaveAttribute("placeholder", "Available again in 8h 42m");
    expect(within(aside).queryByText(/not found/i)).toBeNull();
    expect(within(aside).queryByRole("log")).toBeNull();
  });

  it("says the assistant can't be reached instead of showing Not Found", async () => {
    const { calls } = api({
      info: { status: 404, body: { code: "not_found", detail: "Not Found" } },
    });
    renderApp(`${PAGE}/clario`);
    const aside = await screen.findByRole("region", { name: "Finance Assistant" });
    expect(await within(aside).findByText(/can't be reached right now/)).toBeInTheDocument();
    expect(within(aside).getByText("Can't be reached")).toBeInTheDocument();
    expect(within(aside).queryByText("Not Found")).toBeNull();
    expect(box()).toBeDisabled();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("never claims Available until the server has confirmed it", async () => {
    api({
      info: {
        ...INFO,
        status: { state: "unconfirmed", resets_in_seconds: null, limit_scope: null },
      },
    });
    renderApp(`${PAGE}/clario`);
    const aside = await panel(); // the box is enabled: the next question decides
    expect(within(aside).queryByText("Available")).toBeNull();
    expect(within(aside).queryByText("Usage limit reached")).toBeNull();
  });

  it("counts down in hours and minutes, or minutes and seconds", () => {
    expect([formatWait(31331), formatWait(252), formatWait(9), formatWait(3600)]).toEqual([
      "8h 42m",
      "4m 12s",
      "9s",
      "1h",
    ]);
  });

  it("asks about a signal with the question ready to send, never sent automatically", async () => {
    const { calls } = api();
    const { user, router } = renderApp(`${PAGE}/clario`);
    const signals = await screen.findByRole("region", { name: "Signals" });
    const [ask] = within(signals).getAllByRole("button", { name: "Ask Clario" });
    await user.click(ask as HTMLElement);
    await panel();
    expect(box()).toHaveValue("Which invoices are overdue and who should I follow up with first?");
    expect(router.state.location.pathname).toBe(`${PAGE}/clario`);
    expect(router.state.location.search).toContain("q=");
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });
});

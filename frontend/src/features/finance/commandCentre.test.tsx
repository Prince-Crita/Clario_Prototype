/**
 * The Command Centre against the REAL API responses for the golden dataset (captured from the
 * backend, see testing/golden-responses.json): the screen shows the director's PDF figures.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
} from "../../test/harness";
import golden from "./testing/golden-responses.json";

const base = `/workspaces/${ALPHA.id}/integrations`;
const connection = `/workspaces/${ALPHA.id}/connections/${CONNECTION_ID}`;
const finance = `${connection}/finance`;
const PAGE = "/w/alpha-traders/zoho-books/finance";

function connected(state: "connected" | "needs_reauth" = "connected") {
  const c = zohoConnection(state);
  return zohoTile(true, {
    ...c,
    account: c.account ? { ...c.account, name: "Crita Creative LLP" } : null,
  });
}

function syncStatus(state: "idle" | "running" = "idle") {
  return {
    state,
    as_of: "2026-09-25T10:26:00Z",
    run: null,
    datasets: [],
  };
}

function api(options: { tile?: ReturnType<typeof zohoTile>; sync?: "idle" | "running" } = {}) {
  const tile = options.tile ?? connected();
  return mockApi({
    "GET /auth/session": { status: 200, body: session() },
    [`GET /workspaces/${ALPHA.id}`]: { status: 200, body: ALPHA_DETAIL },
    [`GET ${base}`]: { status: 200, body: { integrations: [tile] } },
    [`GET ${base}/zoho-books`]: { status: 200, body: tile },
    [`GET ${connection}/sync`]: { status: 200, body: syncStatus(options.sync) },
    [`POST ${connection}/sync`]: {
      status: 429,
      body: {
        code: "sync.cooldown",
        detail: "Data was refreshed moments ago. Try again in a minute.",
      },
    },
    [`GET ${finance}/overview`]: { status: 200, body: golden.overview },
    [`GET ${finance}/trends`]: { status: 200, body: golden.trends },
    [`GET ${finance}/receivables`]: { status: 200, body: golden.receivables },
    [`GET ${finance}/gst`]: { status: 200, body: golden.gst },
    [`GET ${finance}/balance-sheet`]: { status: 200, body: golden["balance-sheet"] },
    [`GET ${finance}/invoices`]: (call) => ({
      status: 200,
      body: call.path.includes("status=overdue") ? golden.invoices_overdue : golden.invoices,
    }),
  });
}

describe("Finance Command Centre", () => {
  it("opens from the integration once connected, with the header and freshness", async () => {
    api();
    const { router } = renderApp("/w/alpha-traders/zoho-books");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Crita Creative LLP" }),
    ).toBeVisible();
    expect(router.state.location.pathname).toBe(`${PAGE}/overview`);
    expect(await screen.findByText(/Data as of 25 Sept/)).toBeInTheDocument();
    expect(screen.getByText("Financial year April–March")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
  });

  it("shows the KPI band exactly as the director's PDF", async () => {
    api();
    const { container } = renderApp(`${PAGE}/overview`);
    const band = await screen.findByRole("region", { name: "Key figures" });
    const figure = (label: string) =>
      within(band).getByText(label).closest("figure") as HTMLElement;
    expect(figure("Revenue")).toHaveTextContent("₹7,28,540");
    expect(figure("Revenue")).toHaveTextContent(/accrual · FY 2026-27 to date/i);
    expect(figure("Cash collected")).toHaveTextContent("₹8,37,581");
    expect(figure("Cash collected")).toHaveTextContent("94% of ₹8,95,675 billed");
    expect(figure("Total costs")).toHaveTextContent("₹13,76,568");
    expect(figure("Total costs")).toHaveTextContent("▼ 7% lower");
    expect(figure("Net P&L")).toHaveTextContent("−₹6,48,028");
    expect(figure("Net P&L")).toHaveTextContent("−89% margin");
    expect(figure("Cash on hand")).toHaveTextContent("₹72,739");
    expect(figure("Receivables")).toHaveTextContent("₹58,094");
    expect(figure("Receivables")).toHaveTextContent("9 overdue");
    await screen.findByRole("table", { name: "Invoice register" });
    await expectNoA11yViolations(container);
  });

  it("typesets the P&L and lists what needs attention", async () => {
    api();
    renderApp(`${PAGE}/overview`);
    const pnl = await screen.findByRole("region", { name: "Profit and loss" });
    expect(pnl).toHaveTextContent("Gross profit54% margin₹3,92,462");
    expect(pnl).toHaveTextContent("Net loss−89% margin−₹6,48,028");
    expect(pnl).toHaveTextContent("Largest cost: Salaries and Employee Wages, ₹7,58,800");
    const attention = screen.getByRole("region", { name: "Needs attention" });
    expect(within(attention).getByRole("heading", { name: "Collections 9" })).toBeInTheDocument();
    const first = within(attention).getAllByRole("listitem")[0];
    expect(first).toHaveTextContent(
      "High priority: INV-000002 · Client D: ₹13,000 overdue 185 days",
    );
    expect(attention).toHaveTextContent("GST payable ₹5,665");
    expect(attention).toHaveTextContent("Accrual loss of ₹6,48,028 this fiscal year");
  });

  it("shows the five most overdue first and the rest on request", async () => {
    api();
    const { user } = renderApp(`${PAGE}/overview`);
    const attention = await screen.findByRole("region", { name: "Needs attention" });
    const collections = () => within(attention).getAllByRole("list")[0] as HTMLElement;
    expect(within(collections()).getAllByRole("listitem")).toHaveLength(5);
    await user.click(within(attention).getByRole("button", { name: "Show all 9" }));
    expect(within(collections()).getAllByRole("listitem")).toHaveLength(9);
    expect(within(attention).getByRole("button", { name: "Show fewer" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("offers every chart as a table", async () => {
    api();
    const { user } = renderApp(`${PAGE}/overview`);
    const chart = await screen.findByRole("region", {
      name: "Billed, collected and spent by month",
    });
    await user.click(within(chart).getByRole("button", { name: "View as table" }));
    const table = within(chart).getByRole("table", {
      name: "Billed, collected and spent by month",
    });
    expect(within(table).getByRole("row", { name: /Mar '26/ })).toHaveTextContent("₹36,000");
    expect(within(table).getByRole("row", { name: /Sept '26/ })).toHaveTextContent("−₹91,549");
  });

  it("shows the invoice register with totals and filters", async () => {
    const calls = api();
    const { user } = renderApp(`${PAGE}/overview`);
    const register = await screen.findByRole("table", { name: "Invoice register" });
    expect(within(register).getAllByRole("row")).toHaveLength(1 + 16 + 1); // header, rows, total
    const total = within(register).getByRole("row", { name: /Total/ });
    expect(total).toHaveTextContent("₹8,95,675");
    expect(total).toHaveTextContent("₹58,094");
    expect(within(register).getByRole("row", { name: /INV-00016/ })).toHaveTextContent(
      "Overdue38 days",
    );
    await user.click(screen.getByRole("button", { name: "Overdue" }));
    await waitFor(() => expect(calls.some((c) => c.path.includes("status=overdue"))).toBe(true));
    await waitFor(() =>
      expect(
        within(screen.getByRole("table", { name: "Invoice register" })).getAllByRole("row"),
      ).toHaveLength(1 + 9),
    );
  });

  it("switches tabs by URL: trends", async () => {
    api();
    const { user, router } = renderApp(`${PAGE}/overview`);
    await user.click(await screen.findByRole("tab", { name: "Trends & Analysis" }));
    expect(router.state.location.pathname).toBe(`${PAGE}/trends`);
    const table = await screen.findByRole("table", { name: "Month on month" });
    const total = within(table).getByRole("row", { name: /Total/ });
    expect(total).toHaveTextContent("₹8,95,675₹8,37,581₹11,20,687−₹2,83,106");
    const categories = screen.getByRole("region", { name: "Where spending goes, by month" });
    expect(categories).toHaveTextContent("Salaries and Employee Wages");
    expect(categories).toHaveTextContent("Construction expense");
  });

  it("shows receivables, GST and the balance sheet", async () => {
    api();
    renderApp(`${PAGE}/receivables`);
    const summary = await screen.findByRole("region", { name: "Receivables summary" });
    expect(summary).toHaveTextContent("Overdue₹58,094");
    const ageing = screen.getByRole("region", { name: "How overdue" });
    expect(within(ageing).getByText("Over 90 days overdue").closest("li")).toHaveTextContent(
      "₹30,000",
    );

    api();
    renderApp(`${PAGE}/gst`);
    const gst = await screen.findByRole("region", { name: "GST position" });
    expect(gst).toHaveTextContent("Payable to government₹5,665");
    expect(screen.getByText("Early view")).toBeInTheDocument();

    api();
    renderApp(`${PAGE}/balance-sheet`);
    expect(await screen.findByRole("region", { name: "Balance summary" })).toHaveTextContent(
      "₹72,739",
    );
  });

  it("shows a refresh in progress and explains a refused refresh", async () => {
    api({ sync: "running" });
    renderApp(`${PAGE}/overview`);
    expect(await screen.findByText("Updating from Zoho Books…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Updating…" })).toBeDisabled();

    const calls = api();
    const { user } = renderApp(`${PAGE}/overview`);
    await user.click(await screen.findByRole("button", { name: "Refresh live" }));
    expect(await screen.findByText(/refreshed moments ago/)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ mode: "manual" });
  });

  it("keeps showing the last data when access is lost", async () => {
    api({ tile: connected("needs_reauth") });
    renderApp(`${PAGE}/overview`);
    expect(await screen.findByRole("alert")).toHaveTextContent("Zoho Books needs reconnecting");
    expect(await screen.findByRole("region", { name: "Key figures" })).toHaveTextContent(
      "₹7,28,540",
    );
    expect(screen.getByRole("button", { name: "Refresh live" })).toBeDisabled();
  });

  it("sends an integration without an account to its connection page", async () => {
    api({ tile: zohoTile() });
    const { router } = renderApp(`${PAGE}/overview`);
    await waitFor(() => expect(router.state.location.pathname).toBe("/w/alpha-traders/zoho-books"));
    expect(await screen.findByRole("button", { name: "Connect Zoho Books" })).toBeInTheDocument();
  });
});

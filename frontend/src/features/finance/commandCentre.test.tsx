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
  it("opens from the integration once connected, with the page, organisation and freshness", async () => {
    api();
    const { router } = renderApp("/w/alpha-traders/zoho-books");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Overview" }, { timeout: 5000 }),
    ).toBeVisible();
    expect(router.state.location.pathname).toBe(`${PAGE}/overview`);
    expect(screen.getByText("Crita Creative LLP")).toBeInTheDocument();
    expect(await screen.findByText(/Synced 25 Sept/)).toBeInTheDocument();
    expect(screen.getByText("Financial year April–March")).toBeInTheDocument();
    const pages = screen.getByRole("navigation", { name: "Finance pages" });
    expect(
      within(pages)
        .getAllByRole("link")
        .map((a) => a.textContent),
    ).toEqual(["Overview", "Trends & Analysis", "Payable", "GST", "Receivables", "Balance Sheet"]);
    expect(within(pages).getByRole("link", { name: "Overview" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("shows the six headline figures exactly as the director's PDF", async () => {
    api();
    const { container } = renderApp(`${PAGE}/overview`);
    const band = await screen.findByRole("region", { name: "Key figures" });
    expect(within(band).getAllByRole("figure")).toHaveLength(6);
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
    await screen.findByRole("region", { name: "Business performance" });
    await expectNoA11yViolations(container);
  });

  it("keeps the Overview on performance, and points to Clario AI for what needs attention", async () => {
    api();
    const { user, router } = renderApp(`${PAGE}/overview?period=fy`);
    const performance = await screen.findByRole("region", { name: "Business performance" });
    expect(performance).toHaveTextContent("−89%net margin");
    expect(performance).toHaveTextContent(
      "Net loss of ₹6,48,028 on revenue of ₹7,28,540, FY 2026-27 to date.",
    );
    expect(performance).toHaveTextContent("94%of billed collected");

    const pnl = screen.getByRole("region", { name: "Profit and loss" });
    expect(pnl).toHaveTextContent("Gross profit54% margin₹3,92,462");
    expect(pnl).toHaveTextContent("Net loss−89% margin−₹6,48,028");
    expect(pnl).toHaveTextContent("Largest cost: Salaries and Employee Wages, ₹7,58,800");
    expect(screen.getByRole("region", { name: "Where the business stands" })).toBeInTheDocument();
    for (const moved of ["Signals", "Decision support", "Scenarios"]) {
      expect(screen.queryByRole("region", { name: moved })).toBeNull();
    }
    expect(screen.getByRole("heading", { name: /signals need attention, 2 high/ })).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Open Clario AI" }));
    expect(router.state.location.pathname).toBe(`${PAGE}/clario`);
    expect(router.state.location.search).toBe("?period=fy");
  });

  it("turns the figures into signals, next steps and scenarios on Clario AI", async () => {
    api();
    const { container } = renderApp(`${PAGE}/clario`);
    expect(await screen.findByRole("heading", { level: 1, name: "Clario AI" })).toBeVisible();
    const signals = await screen.findByRole("region", { name: "Signals" });
    const first = within(signals).getAllByRole("listitem")[0] as HTMLElement;
    expect(first).toHaveTextContent("High");
    expect(first).toHaveTextContent("₹58,094 overdue across 9 invoices");
    expect(first).toHaveTextContent("INV-000002 · Client D: ₹13,000 overdue 185 days");
    expect(first).toHaveTextContent("and 6 more in Receivables");
    expect(first).toHaveTextContent("Everything customers owe is past its due date.");
    expect(first).toHaveTextContent("Start with INV-000002, the longest overdue");
    expect(signals).toHaveTextContent("Accrual loss of ₹6,48,028 this fiscal year");
    expect(signals).toHaveTextContent("GST payable ₹5,665");
    // The guide beside the conversation says what lies below.
    const guide = screen.getByRole("navigation", { name: "What Clario sees right now" });
    expect(guide).toHaveTextContent(/What needs attention\d signals · 2 high/);

    const decisions = screen.getByRole("region", { name: "Decision support" });
    const steps = within(decisions).getAllByRole("listitem");
    expect(steps[0]).toHaveTextContent(/1This week.*₹58,094 overdue across 9 invoices\./);
    // Cash on hand (₹72,739) is below this month's spending (₹2,41,549): a real cash signal.
    expect(steps[1]).toHaveTextContent(/2This week.*Cash on hand ₹72,739 is below/);
    expect(signals).toHaveTextContent("₹2,41,549 has been spent this month");
    expect(decisions).toHaveTextContent("₹30,000 of it is more than 90 days late");
    const scenarios = screen.getByRole("region", { name: "Scenarios" });
    expect(scenarios).toHaveTextContent("up to ₹58,094");
    expect(scenarios).toHaveTextContent("not forecasts");
    expect(screen.queryByRole("region", { name: "Key figures" })).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("links a signal to the page with its evidence, keeping the period", async () => {
    api();
    const { user, router } = renderApp(`${PAGE}/clario?period=last_quarter`);
    const signals = await screen.findByRole("region", { name: "Signals" });
    const [open] = within(signals).getAllByRole("link", { name: /Open Receivables/ });
    await user.click(open as HTMLElement);
    expect(router.state.location.pathname).toBe(`${PAGE}/receivables`);
    expect(router.state.location.search).toBe("?period=last_quarter");
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

  it("shows the invoice register, now on Receivables, with totals and filters", async () => {
    const calls = api();
    const { user } = renderApp(`${PAGE}/receivables`);
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

  it("moves between pages by URL: trends", async () => {
    api();
    const { user, router } = renderApp(`${PAGE}/overview`);
    const pages = await screen.findByRole("navigation", { name: "Finance pages" });
    await user.click(within(pages).getByRole("link", { name: "Trends & Analysis" }));
    expect(router.state.location.pathname).toBe(`${PAGE}/trends`);
    const table = await screen.findByRole("table", { name: "Month on month" });
    const total = within(table).getByRole("row", { name: /Total/ });
    expect(total).toHaveTextContent("₹8,95,675₹8,37,581₹11,20,687−₹2,83,106");
    const categories = screen.getByRole("region", { name: "Where spending goes, by month" });
    expect(categories).toHaveTextContent("Salaries and Employee Wages");
    expect(categories).toHaveTextContent("Construction expense");
    // Moved from the Overview: nothing was removed.
    expect(screen.getByRole("region", { name: "Revenue by client" })).toHaveTextContent(
      "₹6,96,246",
    );
    expect(screen.getByRole("region", { name: "Where the money goes" })).toHaveTextContent(
      "₹7,58,800",
    );
  });

  it("filters monthly views by period without recomputing totals", async () => {
    api();
    const { user } = renderApp(`${PAGE}/trends?period=custom&from=2026-04&to=2026-06`);
    const table = await screen.findByRole("table", { name: "Month on month" });
    const months = within(table)
      .getAllByRole("row")
      .slice(1)
      .map((r) => r.firstElementChild?.textContent);
    expect(months).toEqual(["Apr '26", "May '26", "Jun '26"]);
    expect(within(table).queryByRole("row", { name: /Total/ })).toBeNull();
    expect(screen.getByText(/Totals are shown for All imported data/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Change period/ }));
    const dialog = screen.getByRole("dialog", { name: "Choose a period" });
    await user.click(within(dialog).getByRole("button", { name: "All imported data" }));
    const all = await screen.findByRole("table", { name: "Month on month" });
    expect(within(all).getByRole("row", { name: /Total/ })).toHaveTextContent("₹8,95,675");
  });

  it("shows payables from the liabilities Clario reads, and what needs bill import", async () => {
    api();
    renderApp(`${PAGE}/payables`);
    expect(await screen.findByRole("heading", { level: 1, name: "Payable" })).toBeVisible();
    expect(await screen.findByRole("region", { name: "Liabilities" })).toHaveTextContent(
      "Current Liabilities₹1,31,137",
    );
    expect(screen.getByText(/Arrives when vendor bills are imported/)).toBeInTheDocument();
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
    expect(screen.getByRole("region", { name: "GST summary" })).toHaveTextContent(
      "Net GST payable₹5,665",
    );
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
    await user.click(await screen.findByRole("button", { name: "Sync" }));
    expect(await screen.findByText(/refreshed moments ago/)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ mode: "manual" });
  });

  it("keeps showing the last data when access is lost", async () => {
    api({ tile: connected("needs_reauth") });
    renderApp(`${PAGE}/overview`);
    expect(await screen.findByRole("alert")).toHaveTextContent("Zoho Books needs reconnecting");
    expect(screen.getByText("Reconnect needed")).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Key figures" })).toHaveTextContent(
      "₹7,28,540",
    );
    expect(screen.getByRole("button", { name: "Sync" })).toBeDisabled();
  });

  it("sends an integration without an account to its connection page", async () => {
    api({ tile: zohoTile() });
    const { router } = renderApp(`${PAGE}/overview`);
    await waitFor(() => expect(router.state.location.pathname).toBe("/w/alpha-traders/zoho-books"));
    expect(await screen.findByRole("button", { name: "Connect Zoho Books" })).toBeInTheDocument();
  });
});

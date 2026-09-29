import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  ALPHA,
  ALPHA_DETAIL,
  comingSoonTile,
  expectNoA11yViolations,
  mockApi,
  renderApp,
  session,
  zohoTile,
} from "../../test/harness";

const CATALOG = {
  integrations: [
    zohoTile(),
    comingSoonTile("veloce-inventory", "Veloce Inventory", "Inventory"),
    comingSoonTile("lead-management", "Lead Management", "Leads"),
  ],
};
const base = `/workspaces/${ALPHA.id}/integrations`;

describe("integration catalog on workspace home", () => {
  it("shows available and coming-soon systems; only available ones are links", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET /workspaces/${ALPHA.id}`]: { status: 200, body: ALPHA_DETAIL },
      [`GET ${base}`]: { status: 200, body: CATALOG },
    });
    const { container } = renderApp("/w/alpha-traders");
    const main = await screen.findByRole("main");
    const zoho = await within(main).findByRole("link", { name: "Zoho Books" });
    expect(zoho).toHaveAttribute("href", "/w/alpha-traders/zoho-books");

    const veloce = within(main).getByRole("heading", { name: "Veloce Inventory" });
    const veloceCard = veloce.closest("article");
    expect(veloceCard).not.toBeNull();
    expect(within(veloceCard as HTMLElement).queryByRole("link")).toBeNull();
    expect(within(veloceCard as HTMLElement).getByText("Coming soon")).toBeInTheDocument();
    expect(screen.getAllByText("Coming soon")).toHaveLength(2);
    await expectNoA11yViolations(container);
  });

  it("lists only available systems in the navigation", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET /workspaces/${ALPHA.id}`]: { status: 200, body: ALPHA_DETAIL },
      [`GET ${base}`]: { status: 200, body: CATALOG },
    });
    renderApp("/w/alpha-traders");
    const nav = await screen.findByRole("navigation", { name: "Primary" });
    const systems = await within(nav).findByRole("list", { name: "Systems" });
    expect(
      within(systems)
        .getAllByRole("link")
        .map((a) => a.textContent),
    ).toEqual(["Zoho Books"]);
  });
});

describe("integration page", () => {
  it("explains what Clario reads and lets owners connect", async () => {
    const calls = mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: CATALOG },
      [`GET ${base}/zoho-books`]: { status: 200, body: zohoTile() },
      [`POST ${base}/zoho-books/connect`]: {
        status: 503,
        body: {
          code: "integration.connect_unavailable",
          detail: "Connecting Zoho Books is not enabled on this server yet.",
        },
      },
    });
    const { user, container } = renderApp("/w/alpha-traders/zoho-books");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Zoho Books" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Bank and cash account balances")).toBeInTheDocument();
    expect(screen.getByText(/It can never create, change or delete anything/)).toBeInTheDocument();
    await expectNoA11yViolations(container);

    await user.click(screen.getByRole("button", { name: "Connect Zoho Books" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not enabled on this server yet");
    expect(calls.find((c) => c.method === "POST")?.headers["X-CSRF-Token"]).toBe("csrf-token-123");
  });

  it("tells members without permission to ask an admin", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: CATALOG },
      [`GET ${base}/zoho-books`]: { status: 200, body: zohoTile(false) },
    });
    renderApp("/w/alpha-traders/zoho-books");
    expect(
      await screen.findByText(/Only workspace owners and admins can connect/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Connect/ })).toBeNull();
  });

  it("does not let anyone enter a coming-soon system by typing its address", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: CATALOG },
      [`GET ${base}/veloce-inventory`]: {
        status: 200,
        body: comingSoonTile("veloce-inventory", "Veloce Inventory", "Inventory"),
      },
    });
    renderApp("/w/alpha-traders/veloce-inventory");
    expect(await screen.findByText("Veloce Inventory isn't available yet")).toBeInTheDocument();
    expect(within(screen.getByRole("main")).queryByRole("button")).toBeNull();
  });

  it("handles unknown or hidden systems", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: CATALOG },
      [`GET ${base}/no-such-thing`]: {
        status: 404,
        body: { code: "integration.not_found", detail: "Integration not found." },
      },
    });
    renderApp("/w/alpha-traders/no-such-thing");
    expect(
      await screen.findByText("This system isn't available to your workspace"),
    ).toBeInTheDocument();
  });
});

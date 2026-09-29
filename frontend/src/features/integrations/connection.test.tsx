import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

const base = `/workspaces/${ALPHA.id}/integrations`;
const connection = `/workspaces/${ALPHA.id}/connections/${CONNECTION_ID}`;
const CONSENT = "https://accounts.zoho.eu/oauth/v2/auth?state=abc";

const ORGS = {
  accounts: [
    { id: "600111", name: "Old Org", detail: "", is_default: false, selectable: false },
    {
      id: "60089553909",
      name: "Crita TEST Trial",
      detail: "INR · Asia/Calcutta",
      is_default: true,
      selectable: true,
    },
    { id: "600222", name: "Second Org", detail: "USD", is_default: false, selectable: true },
  ],
};

let assign: ReturnType<typeof vi.fn>;
beforeEach(() => {
  assign = vi.fn();
  vi.stubGlobal("location", { ...window.location, assign });
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("integration tile", () => {
  it("shows the connection state and the organisation", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET /workspaces/${ALPHA.id}`]: { status: 200, body: ALPHA_DETAIL },
      [`GET ${base}`]: {
        status: 200,
        body: { integrations: [zohoTile(true, zohoConnection("needs_reauth"))] },
      },
    });
    renderApp("/w/alpha-traders");
    const card = (await screen.findByRole("heading", { name: "Zoho Books" })).closest("article");
    expect(card).not.toBeNull();
    const tile = within(card as HTMLElement);
    expect(tile.getByText("Needs reconnecting")).toBeInTheDocument();
    expect(tile.getByText("Crita TEST Trial")).toBeInTheDocument();
    expect(tile.getByText("Reconnect")).toBeInTheDocument();
  });
});

describe("connecting", () => {
  it("lets an owner choose the data center and sends the browser to Zoho", async () => {
    const calls = mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: { integrations: [zohoTile()] } },
      [`GET ${base}/zoho-books`]: { status: 200, body: zohoTile() },
      [`POST ${base}/zoho-books/connect`]: { status: 200, body: { redirect_url: CONSENT } },
    });
    const { user, container } = renderApp("/w/alpha-traders/zoho-books");
    const region = await screen.findByLabelText("Where is your Zoho account?");
    expect(region).toHaveValue("in");
    await expectNoA11yViolations(container);

    await user.selectOptions(region, "eu");
    await user.click(screen.getByRole("button", { name: "Connect Zoho Books" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith(CONSENT));
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ region: "eu" });
    expect(post?.headers["X-CSRF-Token"]).toBe("csrf-token-123");
  });

  it("explains a failed authorisation from the callback without details", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: { integrations: [zohoTile()] } },
      [`GET ${base}/zoho-books`]: {
        status: 200,
        body: zohoTile(true, zohoConnection("pending", false)),
      },
    });
    renderApp("/w/alpha-traders/zoho-books?error=missing_scopes");
    expect(await screen.findByRole("alert")).toHaveTextContent("Some permissions weren't granted");
  });

  it("uses a generic message for unknown failure codes", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: { integrations: [zohoTile()] } },
      [`GET ${base}/zoho-books`]: { status: 200, body: zohoTile() },
    });
    renderApp("/w/alpha-traders/zoho-books?error=%3Cscript%3E");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Zoho didn't respond as expected");
    expect(alert).not.toHaveTextContent("<script>");
  });

  it("sends an approved but unfinished setup to the organisation step", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: { integrations: [zohoTile()] } },
      [`GET ${base}/zoho-books`]: { status: 200, body: zohoTile(true, zohoConnection("pending")) },
      [`GET ${connection}/accounts`]: { status: 200, body: ORGS },
    });
    const { user, router } = renderApp("/w/alpha-traders/zoho-books");
    await user.click(await screen.findByRole("button", { name: "Choose organisation" }));
    expect(router.state.location.pathname).toBe("/w/alpha-traders/zoho-books/setup");
  });
});

describe("organisation step", () => {
  it("preselects the default organisation, skips unsupported ones, and connects", async () => {
    let chosen = false;
    const calls = mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: { integrations: [zohoTile()] } },
      [`GET ${base}/zoho-books`]: () => ({
        status: 200,
        body: zohoTile(true, zohoConnection(chosen ? "connected" : "pending")),
      }),
      [`GET ${connection}/accounts`]: { status: 200, body: ORGS },
      [`POST ${connection}/account`]: () => {
        chosen = true;
        return { status: 200, body: zohoConnection("connected") };
      },
    });
    const { user, router, container } = renderApp("/w/alpha-traders/zoho-books/setup");
    const trial = await screen.findByRole("radio", { name: /Crita TEST Trial/ });
    expect(trial).toBeChecked();
    expect(screen.getByRole("radio", { name: /Old Org/ })).toBeDisabled();
    await expectNoA11yViolations(container);

    await user.click(screen.getByRole("radio", { name: /Second Org/ }));
    await user.click(screen.getByRole("radio", { name: /Crita TEST Trial/ }));
    await user.click(screen.getByRole("button", { name: "Use Crita TEST Trial" }));

    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ account_id: "60089553909" });
    expect(await screen.findByText("Zoho Books is connected to Crita TEST Trial.")).toBeVisible();
    expect(router.state.location.pathname).toBe("/w/alpha-traders/zoho-books");
  });

  it("is only reachable while an approved setup is unfinished", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: { integrations: [zohoTile()] } },
      [`GET ${base}/zoho-books`]: { status: 200, body: zohoTile() },
    });
    const { router } = renderApp("/w/alpha-traders/zoho-books/setup");
    await waitFor(() => expect(router.state.location.pathname).toBe("/w/alpha-traders/zoho-books"));
  });
});

describe("a connected integration", () => {
  function connectedApi(canManage = true, state: "connected" | "needs_reauth" = "connected") {
    return mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: { integrations: [zohoTile()] } },
      [`GET ${base}/zoho-books`]: {
        status: 200,
        body: zohoTile(canManage, zohoConnection(state)),
      },
      [`POST ${base}/zoho-books/connect`]: { status: 200, body: { redirect_url: CONSENT } },
      [`DELETE ${connection}`]: { status: 204 },
      [`GET ${connection}/sync`]: { status: 200, body: syncStatus() },
    });
  }

  it("shows the organisation's details", async () => {
    connectedApi();
    const { container } = renderApp("/w/alpha-traders/zoho-books/connection");
    const details = await screen.findByRole("region", { name: "Connection" });
    expect(within(details).getByText("Crita TEST Trial")).toBeInTheDocument();
    expect(within(details).getByText("60089553909")).toBeInTheDocument();
    expect(within(details).getByText("April–March")).toBeInTheDocument();
    expect(within(details).getByText("India (zoho.in)")).toBeInTheDocument();
    expect(within(details).getByText(/by Prince M/)).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("reconnects in the same data center", async () => {
    const calls = connectedApi();
    const { user } = renderApp("/w/alpha-traders/zoho-books/connection");
    await user.click(await screen.findByRole("button", { name: "Reconnect" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith(CONSENT));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ region: "in" });
  });

  it("asks for confirmation before disconnecting", async () => {
    const calls = connectedApi();
    const { user } = renderApp("/w/alpha-traders/zoho-books/connection");
    await user.click(await screen.findByRole("button", { name: "Disconnect…" }));
    const confirm = screen.getByRole("group", { name: "Disconnect Zoho Books?" });
    expect(confirm).toHaveTextContent("Nothing in Zoho changes");
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);

    await user.click(within(confirm).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("group", { name: "Disconnect Zoho Books?" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Disconnect…" }));
    await user.click(screen.getByRole("button", { name: "Disconnect" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
    expect(calls.find((c) => c.method === "DELETE")?.headers["X-CSRF-Token"]).toBe(
      "csrf-token-123",
    );
  });

  it("warns when access was lost and leads with Reconnect", async () => {
    connectedApi(true, "needs_reauth");
    renderApp("/w/alpha-traders/zoho-books/connection");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Zoho stopped accepting Clario's access to Crita TEST Trial",
    );
    expect(screen.getByRole("button", { name: "Reconnect" })).toHaveAttribute(
      "data-variant",
      "primary",
    );
  });

  it("shows details but no controls to members who cannot manage it", async () => {
    connectedApi(false);
    renderApp("/w/alpha-traders/zoho-books/connection");
    expect(await screen.findByText(/Only workspace owners and admins can reconnect/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Reconnect" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Disconnect/ })).toBeNull();
  });
});

// ---------------------------------------------------------------- imported data

function dataset(
  key: string,
  label: string,
  rows: number | null,
  extra: Record<string, unknown> = {},
) {
  return {
    key,
    label,
    status: rows === null ? "never" : "ok",
    last_success_at: rows === null ? null : "2026-09-26T06:30:00Z",
    last_attempt_at: rows === null ? null : "2026-09-26T06:30:00Z",
    row_count: rows,
    window_start: null,
    window_end: null,
    error_code: null,
    ...extra,
  };
}

function syncStatus(overrides: Record<string, unknown> = {}) {
  return {
    state: "idle",
    as_of: "2026-09-26T06:30:00Z",
    run: {
      id: "run-1",
      trigger: "initial",
      status: "succeeded",
      started_at: "2026-09-26T06:29:40Z",
      finished_at: "2026-09-26T06:30:00Z",
      api_calls: 26,
      error_code: null,
    },
    datasets: [
      dataset("invoices", "Invoices", 1234),
      dataset("payments_received", "Customer payments", 3, {
        window_start: "2025-04-01",
        window_end: "2026-09-26",
      }),
      dataset("balances", "Balance sheet", 5, {
        window_start: "2026-09-26",
        window_end: "2026-09-26",
      }),
    ],
    ...overrides,
  };
}

describe("imported data", () => {
  function api(sync: unknown, refresh?: { status: number; body?: unknown }) {
    return mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET ${base}`]: { status: 200, body: { integrations: [zohoTile()] } },
      [`GET ${base}/zoho-books`]: {
        status: 200,
        body: zohoTile(false, zohoConnection("connected")),
      },
      [`GET ${connection}/sync`]: { status: 200, body: sync },
      ...(refresh ? { [`POST ${connection}/sync`]: refresh } : {}),
    });
  }

  it("lists each dataset with its records, period and freshness", async () => {
    api(syncStatus());
    const { container } = renderApp("/w/alpha-traders/zoho-books/connection");
    const table = await screen.findByRole("table", { name: "Data imported from Zoho Books" });
    const invoices = within(table).getByRole("row", { name: /Invoices/ });
    expect(invoices).toHaveTextContent("1,234");
    expect(invoices).toHaveTextContent("Everything");
    expect(within(table).getByRole("row", { name: /Customer payments/ })).toHaveTextContent(
      "Apr 2025 – 26 Sept 2026",
    );
    expect(within(table).getByRole("row", { name: /Balance sheet/ })).toHaveTextContent(
      "As of 26 Sept 2026",
    );
    expect(screen.getByText(/Up to date as of/)).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("shows progress while importing", async () => {
    api(
      syncStatus({
        state: "running",
        as_of: null,
        run: { ...syncStatus().run, status: "running", finished_at: null },
      }),
    );
    renderApp("/w/alpha-traders/zoho-books/connection");
    expect(await screen.findByText("Importing from Zoho Books… 3 of 3 done")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importing…" })).toBeDisabled();
  });

  it("says which data could not be refreshed", async () => {
    const partial = syncStatus();
    partial.datasets[0] = dataset("invoices", "Invoices", 1234, {
      status: "failed",
      error_code: "zoho.too_many_records",
    });
    api(partial);
    renderApp("/w/alpha-traders/zoho-books/connection");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invoices kept the last data Clario imported",
    );
  });

  it("refreshes on request and explains a cooldown", async () => {
    const calls = api(syncStatus(), {
      status: 429,
      body: {
        code: "sync.cooldown",
        detail: "Data was refreshed moments ago. Try again in a minute.",
      },
    });
    const { user } = renderApp("/w/alpha-traders/zoho-books/connection");
    await user.click(await screen.findByRole("button", { name: "Refresh now" }));
    expect(await screen.findByText(/refreshed moments ago/)).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ mode: "manual" });
    expect(post?.headers["X-CSRF-Token"]).toBe("csrf-token-123");
  });
});

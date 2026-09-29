/**
 * Test harness: mount the real route tree in a memory router against a mocked API.
 * `mockApi` replaces fetch with a tiny router keyed by "METHOD /path" (path without /api/v1).
 */
import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { createMemoryRouter } from "react-router";
import { expect, vi } from "vitest";

import { App } from "../app/App";
import { routes } from "../app/routes";
import { setCsrfToken } from "../lib/api/client";
import type { Connection, IntegrationTile, Session, WorkspaceSummary } from "../lib/api/types";

export interface Call {
  method: string;
  path: string;
  body: unknown;
  headers: Record<string, string>;
}
interface Reply {
  status: number;
  body?: unknown;
}
type Handler = Reply | ((call: Call) => Reply);

export function mockApi(routesByKey: Record<string, Handler>): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init: RequestInit = {}) => {
      const url = new URL(input, "http://localhost");
      const path = url.pathname.replace(/^\/api\/v1/, "") + url.search;
      const method = init.method ?? "GET";
      const call: Call = {
        method,
        path,
        body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
        headers: (init.headers ?? {}) as Record<string, string>,
      };
      calls.push(call);
      const handler = routesByKey[`${method} ${url.pathname.replace(/^\/api\/v1/, "")}`];
      const reply: Reply = !handler
        ? { status: 404, body: { code: "not_found", detail: `No mock for ${method} ${path}` } }
        : typeof handler === "function"
          ? handler(call)
          : handler;
      return new Response(reply.status === 204 ? null : JSON.stringify(reply.body ?? {}), {
        status: reply.status,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

export function renderApp(path: string) {
  setCsrfToken(null);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const utils = render(<App queryClient={queryClient} router={router} />);
  return { ...utils, router, user: userEvent.setup() };
}

export async function expectNoA11yViolations(container: Element): Promise<void> {
  // jsdom cannot compute colours; contrast is enforced by design-system/tokens.test.ts.
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`)).toEqual([]);
}

// ---------------------------------------------------------------- fixtures
export const ALPHA: WorkspaceSummary = {
  id: "01a0de00-0000-7000-8000-00000000000a",
  slug: "alpha-traders",
  name: "Alpha Traders",
  status: "active",
  role: "owner",
};
export const BETA: WorkspaceSummary = {
  id: "01a0de00-0000-7000-8000-00000000000b",
  slug: "beta-foods",
  name: "Beta Foods",
  status: "active",
  role: "viewer",
};

export function session(workspaces: WorkspaceSummary[] = [ALPHA]): Session {
  return {
    user: { id: "u-1", email: "prince@crita.in", full_name: "Prince M", is_platform_admin: false },
    workspaces,
    csrf_token: "csrf-token-123",
    expires_at: null,
  };
}

export const ALPHA_DETAIL = {
  ...ALPHA,
  timezone: "Asia/Kolkata",
  base_currency: "INR",
  fiscal_year_start_month: 4,
  permissions: ["finance.view", "workspace.view"],
};

export const SIGNED_OUT = {
  status: 401,
  body: { code: "auth.required", detail: "Sign in to continue" },
};

const ZOHO_READS = [
  "Invoices, customers and customer payments",
  "Expenses, bills and vendor payments",
  "Chart of accounts and financial reports (profit & loss, balance sheet, tax summary)",
  "Bank and cash account balances",
];

const ZOHO_REGIONS = [
  { code: "in", label: "India (zoho.in)" },
  { code: "com", label: "United States (zoho.com)" },
  { code: "eu", label: "Europe (zoho.eu)" },
];

export const CONNECTION_ID = "01a0de00-0000-7000-8000-0000000000c1";

type ConnectionState = IntegrationTile["connection_state"];

/** A connection as the API returns it; `state` drives which fields are filled. */
export function zohoConnection(
  state: Exclude<ConnectionState, "not_connected" | "coming_soon">,
  authorised = true,
): Connection {
  const linked = state !== "pending";
  return {
    id: CONNECTION_ID,
    integration_key: "zoho-books",
    status: state,
    authorised,
    account: linked
      ? {
          id: "60089553909",
          name: "Crita TEST Trial",
          currency: "INR",
          timezone: "Asia/Kolkata",
          fiscal_year_start_month: 4,
        }
      : null,
    region: "in",
    connected_at: linked ? "2026-09-26T10:30:00Z" : null,
    connected_by: linked ? "Prince M" : null,
    last_verified_at: linked ? "2026-09-26T10:30:00Z" : null,
    last_error_code: state === "needs_reauth" ? "zoho.refresh_rejected" : null,
  };
}

export function zohoTile(canManage = true, connection: Connection | null = null): IntegrationTile {
  return {
    key: "zoho-books",
    name: "Zoho Books",
    vendor: "Zoho",
    domain: "finance",
    domain_name: "Finance",
    summary: "Revenue, costs, cash, receivables and GST from your Zoho Books organisation.",
    reads: ZOHO_READS,
    read_only: true,
    availability: "available",
    connection_state: connection ? connection.status : "not_connected",
    connection,
    regions: ZOHO_REGIONS,
    account_noun: "organisation",
    can_manage: canManage,
  };
}

export function comingSoonTile(key: string, name: string, domainName: string) {
  return {
    key,
    name,
    vendor: "Crita",
    domain: domainName.toLowerCase(),
    domain_name: domainName,
    summary: `${name} data in Clario.`,
    reads: [],
    read_only: true,
    availability: "coming_soon" as const,
    connection_state: "coming_soon" as const,
    connection: null,
    regions: [],
    account_noun: "account",
    can_manage: true,
  };
}

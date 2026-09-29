/**
 * Where the finance pages and Clario AI live, for the shell. A finance page is
 * /w/:workspace/:integration/finance/:page (Clario AI is the page "clario"); the Command Centre
 * owns the page itself, the shell only links to it (keeping the period in the query string).
 */
import { useLocation, useSearchParams } from "react-router";

import { useIntegrations } from "../features/integrations/hooks";

export interface FinanceRoute {
  integration: string;
  page: string;
}

export function parseFinanceRoute(pathname: string): FinanceRoute | null {
  const match = /^\/w\/[^/]+\/([^/]+)\/finance\/([^/]+)/.exec(pathname);
  return match ? { integration: match[1] ?? "", page: match[2] ?? "" } : null;
}

/** The workspace's connected finance systems (those with an account chosen). */
export function useFinanceSystems(workspaceId: string) {
  const integrations = useIntegrations(workspaceId);
  return (integrations.data ?? []).filter(
    (i) => i.availability === "available" && i.domain === "finance" && i.connection?.account,
  );
}

/**
 * Where Ask Clario leads: the Clario AI page of the finance system you are in (else the first
 * one), keeping the period. Shown to everyone with a finance system: without the assistant
 * permission the page still carries Signals, Decision support and Scenarios.
 */
export function useAskClario(workspaceId: string, base: string) {
  const location = useLocation();
  const [search] = useSearchParams();
  const systems = useFinanceSystems(workspaceId);
  const route = parseFinanceRoute(location.pathname);
  const target = systems.find((s) => s.key === route?.integration) ?? systems[0];
  const params = new URLSearchParams();
  const here = route?.integration === target?.key;
  for (const name of ["period", "from", "to", ...(route?.page === "clario" ? ["c"] : [])]) {
    const value = here ? search.get(name) : null;
    if (value) params.set(name, value);
  }
  return {
    available: target !== undefined,
    active: route?.page === "clario",
    href: target
      ? { pathname: `${base}/${target.key}/finance/clario`, search: params.toString() }
      : null,
  };
}

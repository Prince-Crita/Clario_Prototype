import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { apiFetch } from "../../lib/api/client";
import type { InvoicePage } from "../../lib/api/types";
import { useSyncStatus } from "../integrations/sync";

export type FinanceTab = "overview" | "trends" | "receivables" | "gst" | "balance-sheet";
export type InvoiceFilter = "all" | "unpaid" | "overdue";

const base = (workspaceId: string, connectionId: string) =>
  `/workspaces/${workspaceId}/connections/${connectionId}/finance`;
export const financeKey = (workspaceId: string, connectionId: string) =>
  ["workspace", workspaceId, "connections", connectionId, "finance"] as const;

/** One Command Centre tab. The server computes every figure; this only fetches it. */
export function useFinanceTab<T>(workspaceId: string, connectionId: string, tab: FinanceTab) {
  return useQuery({
    queryKey: [...financeKey(workspaceId, connectionId), tab],
    queryFn: () => apiFetch<T>(`${base(workspaceId, connectionId)}/${tab}`),
  });
}

export function useInvoiceRegister(
  workspaceId: string,
  connectionId: string,
  filter: InvoiceFilter,
) {
  return useInfiniteQuery({
    queryKey: [...financeKey(workspaceId, connectionId), "invoices", filter],
    initialPageParam: "",
    queryFn: ({ pageParam }) => {
      const query = new URLSearchParams({ limit: "50" });
      if (filter !== "all") query.set("status", filter);
      if (pageParam) query.set("cursor", pageParam);
      return apiFetch<InvoicePage>(`${base(workspaceId, connectionId)}/invoices?${query}`);
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}

/**
 * Watches the connection's sync (plan §25): polls every 3 s while one runs, every 30 s otherwise
 * (opening a tab can start a background refresh), and reloads the finance tabs when a run ends.
 */
export function useSyncWatcher(workspaceId: string, connectionId: string) {
  const queryClient = useQueryClient();
  const status = useSyncStatus(workspaceId, connectionId, { idlePollMs: 30_000, busyPollMs: 3000 });
  const running = status.data?.state === "running";
  const wasRunning = useRef(false);
  useEffect(() => {
    if (wasRunning.current && !running) {
      void queryClient.invalidateQueries({ queryKey: financeKey(workspaceId, connectionId) });
    }
    wasRunning.current = running;
  }, [running, queryClient, workspaceId, connectionId]);
  return status;
}

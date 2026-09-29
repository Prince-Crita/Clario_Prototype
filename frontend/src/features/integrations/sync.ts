import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "../../lib/api/client";
import type { SyncStatus } from "../../lib/api/types";

const POLL_MS = 2000;

const syncPath = (workspaceId: string, connectionId: string) =>
  `/workspaces/${workspaceId}/connections/${connectionId}/sync`;
const syncKey = (workspaceId: string, connectionId: string) =>
  ["workspace", workspaceId, "connections", connectionId, "sync"] as const;

interface PollOptions {
  busyPollMs?: number;
  idlePollMs?: number | false;
}

/** Freshness of a connection's mirror; polls while a sync is running (and, optionally, idle). */
export function useSyncStatus(
  workspaceId: string,
  connectionId: string,
  { busyPollMs = POLL_MS, idlePollMs = false }: PollOptions = {},
) {
  return useQuery({
    queryKey: syncKey(workspaceId, connectionId),
    queryFn: () => apiFetch<SyncStatus>(syncPath(workspaceId, connectionId)),
    refetchInterval: (query) => (query.state.data?.state === "running" ? busyPollMs : idlePollMs),
  });
}

/** "Refresh now". The server applies a cooldown and the provider's daily budget. */
export function useRefresh(workspaceId: string, connectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<SyncStatus>(syncPath(workspaceId, connectionId), {
        method: "POST",
        body: { mode: "manual" },
      }),
    onSuccess: (status) => {
      queryClient.setQueryData(syncKey(workspaceId, connectionId), status);
    },
  });
}

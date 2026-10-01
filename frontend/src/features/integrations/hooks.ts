import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "../../lib/api/client";
import type { Connection, ExternalAccount, IntegrationTile } from "../../lib/api/types";

const catalogKey = (workspaceId: string) => ["workspace", workspaceId, "integrations"] as const;

export function useIntegrations(workspaceId: string) {
  return useQuery({
    queryKey: catalogKey(workspaceId),
    queryFn: async () =>
      (
        await apiFetch<{ integrations: IntegrationTile[] }>(
          `/workspaces/${workspaceId}/integrations`,
        )
      ).integrations,
  });
}

export function useIntegration(workspaceId: string, key: string) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: [...catalogKey(workspaceId), key],
    queryFn: () =>
      apiFetch<IntegrationTile>(
        `/workspaces/${workspaceId}/integrations/${encodeURIComponent(key)}`,
      ),
    // The shell already loads the whole catalogue, and the server builds a catalogue entry and a
    // single tile identically. Reuse the entry when it is there instead of making the dashboard
    // wait for a second round trip (it is refetched as usual once it goes stale).
    initialData: () =>
      queryClient
        .getQueryData<IntegrationTile[]>(catalogKey(workspaceId))
        ?.find((t) => t.key === key),
    initialDataUpdatedAt: () => queryClient.getQueryState(catalogKey(workspaceId))?.dataUpdatedAt,
  });
}

/**
 * Starts (or restarts) the connector's consent flow and sends the browser where the server says.
 * The provider redirects back to the API callback, which redirects into the app.
 */
export function useConnectIntegration(workspaceId: string, key: string) {
  return useMutation({
    mutationFn: (region: string | undefined) =>
      apiFetch<{ redirect_url: string }>(
        `/workspaces/${workspaceId}/integrations/${encodeURIComponent(key)}/connect`,
        { method: "POST", body: region ? { region } : {} },
      ),
    onSuccess: ({ redirect_url }) => window.location.assign(redirect_url),
  });
}

const connectionPath = (workspaceId: string, connectionId: string) =>
  `/workspaces/${workspaceId}/connections/${connectionId}`;

/** Accounts the authorised login can see (Zoho organisations). Live call: no background refetch. */
export function useAccounts(workspaceId: string, connectionId: string | undefined) {
  return useQuery({
    queryKey: ["workspace", workspaceId, "connections", connectionId, "accounts"],
    queryFn: async () =>
      (
        await apiFetch<{ accounts: ExternalAccount[] }>(
          `${connectionPath(workspaceId, connectionId ?? "")}/accounts`,
        )
      ).accounts,
    enabled: Boolean(connectionId),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

export function useSelectAccount(workspaceId: string, connectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (accountId: string) =>
      apiFetch<Connection>(`${connectionPath(workspaceId, connectionId)}/account`, {
        method: "POST",
        body: { account_id: accountId },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalogKey(workspaceId) }),
  });
}

export function useDisconnect(workspaceId: string, connectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<undefined>(connectionPath(workspaceId, connectionId), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalogKey(workspaceId) }),
  });
}

import { useQuery } from "@tanstack/react-query";
import { createContext, useContext } from "react";

import { apiFetch } from "../../lib/api/client";
import type { Member, WorkspaceDetail, WorkspaceSummary } from "../../lib/api/types";

/** The workspace selected by the URL slug; provided by the app shell. */
export const CurrentWorkspaceContext = createContext<WorkspaceSummary | null>(null);

export function useCurrentWorkspace(): WorkspaceSummary {
  const workspace = useContext(CurrentWorkspaceContext);
  if (!workspace) throw new Error("useCurrentWorkspace used outside the app shell");
  return workspace;
}

export function useWorkspaceDetail(workspaceId: string) {
  return useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () => apiFetch<WorkspaceDetail>(`/workspaces/${workspaceId}`),
  });
}

export function useMembers(workspaceId: string) {
  return useQuery({
    queryKey: ["workspace", workspaceId, "members"],
    queryFn: async () =>
      (await apiFetch<{ members: Member[] }>(`/workspaces/${workspaceId}/members`)).members,
  });
}

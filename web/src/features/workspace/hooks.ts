import { createContext, useContext } from "react";

import type { WorkspaceSummary } from "../../lib/api/types";

/** The workspace selected by the URL slug; provided by the app shell. */
export const CurrentWorkspaceContext = createContext<WorkspaceSummary | null>(null);

export function useCurrentWorkspace(): WorkspaceSummary {
  const workspace = useContext(CurrentWorkspaceContext);
  if (!workspace) throw new Error("useCurrentWorkspace used outside the app shell");
  return workspace;
}

/**
 * Route tree (plan §9.3). Exported as data so tests mount the exact same tree in a memory router.
 *   /login                      sign in
 *   /w                          workspace chooser (skipped with one workspace)
 *   /w/:workspace               workspace home          ┐ inside the app shell
 *   /w/:workspace/settings      members · your account  │
 *   /w/:workspace/:integration  its dashboard once connected, else the connection page
 *   /w/:workspace/:integration/connection     connection status, manage, imported data
 *   /w/:workspace/:integration/setup          choose the account (after consent)
 *   /w/:workspace/:integration/finance/:tab   Finance Command Centre ┘
 */
import { Navigate, type RouteObject } from "react-router";

import { LoginPage } from "../features/auth/LoginPage";
import { RequireSession } from "../features/auth/RequireSession";
import { IntegrationIndex } from "../features/integrations/IntegrationIndex";
import { IntegrationPage } from "../features/integrations/IntegrationPage";
import { SetupPage } from "../features/integrations/SetupPage";
import { WorkspaceChooser } from "../features/workspace/WorkspaceChooser";
import { WorkspaceHome } from "../features/workspace/WorkspaceHome";
import { WorkspaceSettings } from "../features/workspace/WorkspaceSettings";
import { AppShell } from "../shell/AppShell";
import { NotFound } from "../shell/NotFound";
import { LazyCommandCentre } from "./LazyCommandCentre";

export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireSession />,
    children: [
      { path: "/", element: <Navigate to="/w" replace /> },
      { path: "/w", element: <WorkspaceChooser /> },
      {
        path: "/w/:workspace",
        element: <AppShell />,
        children: [
          { index: true, element: <WorkspaceHome /> },
          { path: "settings", element: <WorkspaceSettings /> },
          { path: ":integration", element: <IntegrationIndex /> },
          { path: ":integration/connection", element: <IntegrationPage /> },
          { path: ":integration/setup", element: <SetupPage /> },
          { path: ":integration/finance", element: <Navigate to="overview" replace /> },
          {
            path: ":integration/finance/:tab",
            element: <LazyCommandCentre />,
          },
        ],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
];

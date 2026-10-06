import { Navigate, type RouteObject } from "react-router";

import { LoginPage } from "../features/auth/LoginPage";
import { RequireSession } from "../features/auth/RequireSession";
import { WorkspaceChooser } from "../features/workspace/WorkspaceChooser";
import { WorkspaceHome } from "../features/workspace/WorkspaceHome";
import { AppShell } from "../shell/AppShell";
import { NotFound } from "../shell/NotFound";

/**
 *   /login            sign in
 *   /w                workspace chooser (skipped with one workspace)
 *   /w/:workspace     workspace home, inside the app shell
 *   *                 not found
 */
export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  {
    // Everything inside `children` is protected by the guard.
    element: <RequireSession />,
    children: [
      { path: "/", element: <Navigate to="/w" replace /> },
      { path: "/w", element: <WorkspaceChooser /> },
      {
        path: "/w/:workspace",
        element: <AppShell />,
        children: [{ index: true, element: <WorkspaceHome /> }],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
];

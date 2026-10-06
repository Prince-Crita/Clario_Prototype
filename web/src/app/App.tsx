/**
 * Application root: providers + router. A 401 from any signed-in request (the session ended)
 * clears cached data and marks the session as signed out, so <RequireSession> sends the user
 * to /login with a `next` link back to where they were.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";

import { sessionKey } from "../features/auth/hooks";
import { setUnauthorizedHandler } from "../lib/api/client";
import { createQueryClient } from "./queryClient";
import { routes } from "./routes";

export function App() {
  // Both are created once. The router reads the browser URL and renders the matching route;
  // the query client holds the cached data (the session, later workspace data).
  const [queryClient] = useState(() => createQueryClient());
  const [router] = useState(() => createBrowserRouter(routes));

  useEffect(() => {
    setUnauthorizedHandler(() => {
      // Drop everything cached for the old session except the session key itself...
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== sessionKey[0] });
      // ...and mark the session as signed out. The guard reacts to this.
      queryClient.setQueryData(sessionKey, null);
    });
    return () => setUnauthorizedHandler(null);
  }, [queryClient]);

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

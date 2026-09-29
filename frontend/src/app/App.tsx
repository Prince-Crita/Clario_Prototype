/**
 * Application root: providers + router. A 401 from any data request (session ended elsewhere)
 * clears cached data and marks the session signed-out, so <RequireSession> sends the user to
 * sign in with a `next` link back to where they were.
 */
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createBrowserRouter, RouterProvider, type DataRouter } from "react-router";

import { sessionKey } from "../features/auth/hooks";
import { setUnauthorizedHandler } from "../lib/api/client";
import { createQueryClient } from "./queryClient";
import { routes } from "./routes";

interface AppProps {
  queryClient?: QueryClient;
  router?: DataRouter;
}

export function App({ queryClient: injectedClient, router: injectedRouter }: AppProps = {}) {
  const [queryClient] = useState(() => injectedClient ?? createQueryClient());
  const [router] = useState(() => injectedRouter ?? createBrowserRouter(routes));

  useEffect(() => {
    setUnauthorizedHandler(() => {
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== sessionKey[0] });
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

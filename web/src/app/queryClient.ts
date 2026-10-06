import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "../lib/api/client";

/** Retry only transient failures (network / 5xx), never client errors like 401/403/404/422. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (failureCount, error) =>
          failureCount < 2 &&
          (!(error instanceof ApiError) || error.status === 0 || error.status >= 500),
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
      mutations: { retry: false },
    },
  });
}

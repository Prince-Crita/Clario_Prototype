/** The parts of a TanStack query the page body needs (one query, or several combined). */
export interface QueryLike<T> {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  data: T | undefined;
  refetch: () => unknown;
}

/** Combine two queries: pending or failed if either is. */
export function both<A, B>(a: QueryLike<A>, b: QueryLike<B>): QueryLike<[A, B]> {
  return {
    isPending: a.isPending || b.isPending,
    isError: a.isError || b.isError,
    error: a.error ?? b.error,
    data: a.data !== undefined && b.data !== undefined ? [a.data, b.data] : undefined,
    refetch: () => {
      if (a.isError) void a.refetch();
      if (b.isError) void b.refetch();
    },
  };
}

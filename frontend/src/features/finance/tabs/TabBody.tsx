/** Loading and error states shared by the Command Centre pages (skeletons in the content's shape). */
import type { ReactNode } from "react";

import { Button, EmptyState, Skeleton } from "../../../design-system";
import { ApiError } from "../../../lib/api/client";
import type { FinanceTab } from "../hooks";
import type { Period } from "../period";
import type { QueryLike } from "../query";
import styles from "./tabs.module.css";

export interface TabProps {
  workspaceId: string;
  connectionId: string;
  /** Which months the charts and monthly tables show. */
  period: Period;
  /** A link to another page that keeps the period and assistant state. */
  pageHref: (tab: FinanceTab) => { pathname: string; search: string };
  /** Opens Ask Clario with a question ready to send (never sent automatically); absent without
   * the assistant permission. */
  ask?: ((question: string, send?: boolean) => void) | undefined;
  /** The Ask Clario card, for pages that place it in their own layout (the Overview). */
  askCard?: ReactNode;
  /** The Finance Assistant conversation (the Clario AI page); absent without the permission. */
  chat?: ReactNode;
  /** Organisation, system, sync, financial year and the connection link — for a page that lays
   * out its own header (the Overview). */
  context?: ReactNode;
  /** The period picker and Sync, for a page that lays out its own header. */
  controls?: ReactNode;
}

export function TabBody<T>({
  query,
  children,
  skeleton,
}: {
  query: QueryLike<T>;
  children: (data: T) => ReactNode;
  /** What to show while loading, in the shape of the page (default: two blocks). */
  skeleton?: ReactNode;
}) {
  if (query.isPending) {
    if (skeleton) {
      return (
        <div aria-busy="true" aria-label="Loading">
          {skeleton}
        </div>
      );
    }
    return (
      <div className={styles.stack} aria-busy="true" aria-label="Loading">
        <div className={styles.kpiSkeleton}>
          <Skeleton height={320} radius="md" />
          <Skeleton height={320} radius="md" />
        </div>
        <Skeleton height={220} radius="md" />
      </div>
    );
  }
  if (query.isError || query.data === undefined) {
    return (
      <EmptyState
        title="These figures couldn't be loaded"
        action={
          <Button size="sm" onClick={() => void query.refetch()}>
            Try again
          </Button>
        }
      >
        {query.error instanceof ApiError
          ? query.error.detail
          : "Check your connection and try again."}
      </EmptyState>
    );
  }
  return <>{children(query.data)}</>;
}

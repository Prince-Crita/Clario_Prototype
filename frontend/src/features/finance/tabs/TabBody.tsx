/** Loading and error states shared by the Command Centre tabs (skeletons in the content's shape). */
import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { Button, EmptyState, Skeleton } from "../../../design-system";
import { ApiError } from "../../../lib/api/client";
import styles from "./tabs.module.css";

export interface TabProps {
  workspaceId: string;
  connectionId: string;
}

export function TabBody<T>({
  query,
  children,
}: {
  query: UseQueryResult<T>;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) {
    return (
      <div className={styles.stack} aria-busy="true" aria-label="Loading">
        <Skeleton height={176} radius="md" />
        <div className={styles.split}>
          <Skeleton height={280} radius="md" />
          <Skeleton height={280} radius="md" />
        </div>
      </div>
    );
  }
  if (query.isError) {
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

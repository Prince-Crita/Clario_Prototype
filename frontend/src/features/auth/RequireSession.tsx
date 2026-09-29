/** Route guard: renders children only for a signed-in user; otherwise sends them to sign in. */
import { Navigate, Outlet, useLocation } from "react-router";

import { Alert, Button, Skeleton } from "../../design-system";
import { useSession } from "./hooks";
import styles from "./RequireSession.module.css";

export function RequireSession() {
  const location = useLocation();
  const { data, isPending, isError, refetch } = useSession();

  if (isPending) {
    return (
      <div className={styles.loading} aria-busy="true" aria-label="Loading Clario">
        <Skeleton width={232} height="100vh" radius="sm" />
        <div className={styles.loadingMain}>
          <Skeleton width="40%" height={28} />
          <Skeleton width="25%" height={16} />
          <Skeleton height={160} radius="md" />
        </div>
      </div>
    );
  }
  if (isError) {
    return (
      <main className={styles.error}>
        <Alert
          tone="negative"
          title="Clario couldn't load your session"
          action={<Button onClick={() => refetch()}>Try again</Button>}
        >
          Check your connection. If this keeps happening, contact Crita support.
        </Alert>
      </main>
    );
  }
  if (!data) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return <Outlet />;
}

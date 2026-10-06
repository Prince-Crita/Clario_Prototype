/** Route guard: renders children only for a signed-in user; otherwise sends them to sign in. */
import { Navigate, Outlet, useLocation } from "react-router";

import { Alert } from "../../design-system/primitives/Alert";
import { Button } from "../../design-system/primitives/Button";
import { Skeleton } from "../../design-system/primitives/Skeleton";
import { useSession } from "./hooks";
import styles from "./RequireSession.module.css";

export function RequireSession() {
  const location = useLocation();
  const { data, isPending, isError, refetch } = useSession();

  if (isPending) {
    return (
      <div className={styles.loading} aria-busy="true" aria-label="Loading Clario">
        <div className={styles.bar}>
          <Skeleton width={120} height={30} radius="sm" />
          <span className={styles.barPages}>
            <Skeleton width={420} height={38} radius="md" />
          </span>
        </div>
        <div className={styles.page}>
          <div className={styles.title}>
            <Skeleton width="34%" height={38} />
            <Skeleton width="52%" height={16} />
          </div>
          <div className={styles.cards}>
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} height={150} radius="md" />
            ))}
          </div>
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
    // Signed out: go to /login and remember where the user was headed.
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  // Signed in: render whichever protected route matched (the <Outlet />).
  return <Outlet />;
}

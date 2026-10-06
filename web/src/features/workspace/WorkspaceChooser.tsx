/**
 * /w — pick a workspace. Skipped automatically when the user has exactly one.
 * Rendered as a list of rows, not cards: it is a choice, not a dashboard.
 */
import { ChevronRight } from "lucide-react";
import { Link, Navigate } from "react-router";

import { Lockup } from "../../brand/Wordmark";
import { Button } from "../../design-system/primitives/Button";
import { EmptyState } from "../../design-system/primitives/EmptyState";
import { Status } from "../../design-system/primitives/Status";
import { ROLE_LABEL } from "../../lib/labels";
import { useRequiredSession, useSignOut } from "../auth/hooks";
import styles from "./WorkspaceChooser.module.css";

export function WorkspaceChooser() {
  const session = useRequiredSession();
  const signOut = useSignOut();
  const workspaces = session.workspaces;

  const [only] = workspaces;
  if (workspaces.length === 1 && only) return <Navigate to={`/w/${only.slug}`} replace />;

  return (
    <main className={styles.page}>
      <header className={styles.top}>
        <Lockup />
        <div className={styles.account}>
          <span>{session.user.email}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => signOut.mutate()}
            pending={signOut.isPending}
          >
            Sign out
          </Button>
        </div>
      </header>
      <section className={styles.body} aria-labelledby="choose-title">
        <h1 id="choose-title" className={styles.title}>
          Choose a workspace
        </h1>
        {workspaces.length === 0 ? (
          <EmptyState title="You don't have access to a workspace yet.">
            Ask your Crita contact to add {session.user.email} to your organisation's workspace.
          </EmptyState>
        ) : (
          <ul className={styles.list}>
            {workspaces.map((w) => (
              <li key={w.id}>
                <Link to={`/w/${w.slug}`} className={styles.row}>
                  <span className={styles.name}>{w.name}</span>
                  <span className={styles.role}>{ROLE_LABEL[w.role]}</span>
                  {w.status !== "active" ? <Status tone="warning">{w.status}</Status> : <span />}
                  <ChevronRight size={16} aria-hidden="true" className={styles.chevron} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

/**
 * Workspace layout: a white top bar with the Clario logo and the workspace on the left, Home and
 * the account on the right. Under 720 px the Home link moves into a drawer opened from the menu
 * button. Resolves the workspace from the URL slug against the user's memberships; an unknown
 * slug shows "not found".
 */
import { Home, Menu as MenuIcon, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useParams } from "react-router";

import { Lockup } from "../brand/Wordmark";
import { useRequiredSession } from "../features/auth/hooks";
import { CurrentWorkspaceContext } from "../features/workspace/hooks";
import { setTenantId } from "../lib/api/client";
import { cx } from "../lib/cx";
import styles from "./AppShell.module.css";
import { NotFound } from "./NotFound";
import { UserMenu } from "./UserMenu";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";

export function AppShell() {
  const { workspace: slug } = useParams();
  const session = useRequiredSession();
  const location = useLocation();
  // The drawer remembers the path it was opened on, so any navigation closes it without an effect.
  const [drawerOpenedAt, setDrawerOpenedAt] = useState<string | null>(null);
  const drawerOpen = drawerOpenedAt === location.pathname;
  const setDrawerOpen = (open: boolean) => setDrawerOpenedAt(open ? location.pathname : null);

  const workspace = session.workspaces.find((w) => w.slug === slug);
  const workspaceId = workspace?.id;

  // Selecting a workspace = remembering its id. apiFetch sends it as X-Tenant-Id from now on.
  useEffect(() => {
    if (workspaceId) setTenantId(workspaceId);
  }, [workspaceId]);

  if (!workspace) {
    return (
      <NotFound
        title="Workspace not found"
        message="You may not have access to it, or the address is wrong."
      />
    );
  }
  const base = `/w/${workspace.slug}`;

  return (
    <CurrentWorkspaceContext.Provider value={workspace}>
      <div className={styles.shell} data-drawer={drawerOpen || undefined}>
        <header className={styles.topbar}>
          <div className={styles.inner}>
            <button
              type="button"
              className={styles.menuButton}
              aria-label={drawerOpen ? "Close navigation" : "Open navigation"}
              aria-expanded={drawerOpen}
              aria-controls="primary-navigation"
              onClick={() => setDrawerOpen(!drawerOpen)}
            >
              {drawerOpen ? (
                <X size={20} aria-hidden="true" />
              ) : (
                <MenuIcon size={20} aria-hidden="true" />
              )}
            </button>
            <Link to={base} className={styles.brand} aria-label={`${workspace.name} home`}>
              <Lockup size="sm" />
            </Link>
            <div className={styles.workspace}>
              <WorkspaceSwitcher current={workspace} workspaces={session.workspaces} />
            </div>

            <div className={styles.actions}>
              <nav
                id="primary-navigation"
                className={styles.nav}
                data-open={drawerOpen || undefined}
                aria-label="Primary"
              >
                <ul className={styles.links}>
                  <li>
                    <NavLink to={base} end className={cx(styles.iconLink)} title="Home">
                      <Home size={18} aria-hidden="true" />
                      <span className={styles.linkLabel}>Home</span>
                    </NavLink>
                  </li>
                </ul>
              </nav>
              <UserMenu user={session.user} />
            </div>
          </div>
        </header>
        {drawerOpen ? (
          <div className={styles.scrim} onClick={() => setDrawerOpen(false)} aria-hidden="true" />
        ) : null}

        <main className={styles.main} id="main">
          <div className={styles.content}>
            <Outlet />
          </div>
        </main>
      </div>
    </CurrentWorkspaceContext.Provider>
  );
}

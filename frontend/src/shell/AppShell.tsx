/**
 * Workspace layout (plan §9.3, §27.2): left navigation (232 px, collapses to a top bar + drawer
 * under 900 px), workspace switcher, user menu, and the page outlet. Resolves the workspace from
 * the URL slug against the signed-in user's memberships; unknown slugs show "not found".
 */
import { Home, Menu as MenuIcon, Settings, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useParams } from "react-router";

import { Lockup } from "../brand/Wordmark";
import { useRequiredSession } from "../features/auth/hooks";
import { CurrentWorkspaceContext } from "../features/workspace/hooks";
import { cx } from "../lib/cx";
import styles from "./AppShell.module.css";
import { NotFound } from "./NotFound";
import { SystemsNav } from "./SystemsNav";
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
      <div className={styles.shell}>
        <header className={styles.topbar}>
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
          <Link to={base} className={styles.brandLink} aria-label={`${workspace.name} home`}>
            <Lockup size="sm" />
          </Link>
        </header>

        <nav
          id="primary-navigation"
          className={styles.rail}
          data-open={drawerOpen || undefined}
          aria-label="Primary"
        >
          <Link to={base} className={styles.brand} aria-label={`${workspace.name} home`}>
            <Lockup size="sm" />
          </Link>
          <WorkspaceSwitcher current={workspace} workspaces={session.workspaces} />
          <ul className={styles.nav}>
            <li>
              <NavLink to={base} end className={cx(styles.navItem)}>
                <Home size={16} aria-hidden="true" />
                Home
              </NavLink>
            </li>
          </ul>
          <SystemsNav workspaceId={workspace.id} base={base} />
          <div className={styles.railFooter}>
            <ul className={styles.nav}>
              <li>
                <NavLink to={`${base}/settings`} className={cx(styles.navItem)}>
                  <Settings size={16} aria-hidden="true" />
                  Settings
                </NavLink>
              </li>
            </ul>
            <UserMenu user={session.user} settingsPath={`${base}/settings`} />
          </div>
        </nav>
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

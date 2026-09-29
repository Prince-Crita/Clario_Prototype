/**
 * Workspace layout — "Crita Intelligence" (plan §27.10). One white top bar carries the product:
 * the Clario mark and workspace on the left, the finance pages in the centre (a green dot marks
 * the current one), and on the right Ask Clario (an ink pill), Home, Systems, Settings and the
 * account. Under 1180 px the pages become a menu; under 720 px a slim bar, a drawer and a bottom
 * bar with Ask Clario at its centre.
 * Resolves the workspace from the URL slug against the signed-in user's memberships; unknown
 * slugs show "not found".
 */
import { Home, Menu as MenuIcon, Settings, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useParams } from "react-router";

import { Lockup } from "../brand/Wordmark";
import { useRequiredSession } from "../features/auth/hooks";
import { CurrentWorkspaceContext } from "../features/workspace/hooks";
import { cx } from "../lib/cx";
import { AskClarioEntry, MobileFinanceBar } from "./AskClarioEntry";
import styles from "./AppShell.module.css";
import { FinancePagesNav } from "./FinancePagesNav";
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

            <FinancePagesNav workspaceId={workspace.id} base={base} />

            <div className={styles.actions}>
              <AskClarioEntry workspaceId={workspace.id} base={base} />
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
                <SystemsNav workspaceId={workspace.id} base={base} />
                <ul className={styles.links}>
                  <li>
                    <NavLink
                      to={`${base}/settings`}
                      className={cx(styles.iconLink)}
                      title="Settings"
                    >
                      <Settings size={18} aria-hidden="true" />
                      <span className={styles.linkLabel}>Settings</span>
                    </NavLink>
                  </li>
                </ul>
              </nav>
              <UserMenu user={session.user} settingsPath={`${base}/settings`} />
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
        <MobileFinanceBar
          workspaceId={workspace.id}
          base={base}
          onMore={() => setDrawerOpen(true)}
        />
      </div>
    </CurrentWorkspaceContext.Provider>
  );
}

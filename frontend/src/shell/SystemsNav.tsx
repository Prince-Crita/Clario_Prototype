/** "Systems" group in the left navigation: the workspace's available integrations only. */
import { Database } from "lucide-react";
import { NavLink } from "react-router";

import { useIntegrations } from "../features/integrations/hooks";
import { cx } from "../lib/cx";
import styles from "./AppShell.module.css";

export function SystemsNav({ workspaceId, base }: { workspaceId: string; base: string }) {
  const integrations = useIntegrations(workspaceId);
  const available = (integrations.data ?? []).filter((i) => i.availability === "available");
  if (available.length === 0) return null;
  return (
    <div className={styles.group}>
      <p className={styles.groupLabel} id="systems-nav-label">
        Systems
      </p>
      <ul className={styles.nav} aria-labelledby="systems-nav-label">
        {available.map((i) => (
          <li key={i.key}>
            <NavLink to={`${base}/${i.key}`} className={cx(styles.navItem)}>
              <Database size={16} aria-hidden="true" />
              {i.name}
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

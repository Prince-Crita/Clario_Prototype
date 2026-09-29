/** The workspace's available systems, as compact links in the top bar (a list in the drawer). */
import { LayoutGrid } from "lucide-react";
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
      <ul className={styles.links} aria-labelledby="systems-nav-label">
        {available.map((i) => (
          <li key={i.key}>
            <NavLink to={`${base}/${i.key}`} end className={cx(styles.iconLink)} title={i.name}>
              <LayoutGrid size={18} aria-hidden="true" />
              <span className={styles.linkLabel}>{i.name}</span>
              {i.connection_state === "needs_reauth" ? (
                <span className={styles.attention} aria-label="needs reconnecting" />
              ) : null}
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

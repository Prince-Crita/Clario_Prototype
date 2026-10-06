import { ChevronsUpDown } from "lucide-react";
import { useNavigate } from "react-router";

import { Menu, MenuItem, MenuLabel } from "../design-system/primitives/Menu";
import type { WorkspaceSummary } from "../lib/api/types";
import { ROLE_LABEL } from "../lib/labels";
import styles from "./WorkspaceSwitcher.module.css";

interface WorkspaceSwitcherProps {
  current: WorkspaceSummary;
  workspaces: WorkspaceSummary[];
}

export function WorkspaceSwitcher({ current, workspaces }: WorkspaceSwitcherProps) {
  const navigate = useNavigate();
  const label = (
    <span className={styles.label}>
      <span className={styles.caption}>Workspace</span>
      <span className={styles.name}>{current.name}</span>
      <span className={styles.role}>{ROLE_LABEL[current.role]}</span>
    </span>
  );

  if (workspaces.length < 2) return <div className={styles.static}>{label}</div>;

  return (
    <Menu
      trigger={
        <button
          type="button"
          className={styles.trigger}
          aria-label={`Workspace: ${current.name}. Switch workspace`}
        >
          {label}
          <ChevronsUpDown size={14} aria-hidden="true" className={styles.icon} />
        </button>
      }
    >
      <MenuLabel>Switch workspace</MenuLabel>
      {workspaces.map((w) => (
        <MenuItem
          key={w.id}
          selected={w.id === current.id}
          onSelect={() => navigate(`/w/${w.slug}`)}
        >
          {w.name}
        </MenuItem>
      ))}
    </Menu>
  );
}

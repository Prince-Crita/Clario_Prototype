import { useNavigate } from "react-router";

import { Menu, MenuItem, MenuLabel, MenuSeparator } from "../design-system";
import { useSignOut } from "../features/auth/hooks";
import type { User } from "../lib/api/types";
import styles from "./UserMenu.module.css";

function initials(user: User): string {
  const source = user.full_name.trim() || user.email;
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

export function UserMenu({ user, settingsPath }: { user: User; settingsPath: string }) {
  const navigate = useNavigate();
  const signOut = useSignOut();
  return (
    <Menu
      side="top"
      trigger={
        <button type="button" className={styles.trigger} aria-label={`Account: ${user.email}`}>
          <span className={styles.avatar} aria-hidden="true">
            {initials(user)}
          </span>
          <span className={styles.text}>
            <span className={styles.name}>{user.full_name || user.email}</span>
            <span className={styles.email}>{user.email}</span>
          </span>
        </button>
      }
    >
      <MenuLabel>Signed in as {user.email}</MenuLabel>
      <MenuItem onSelect={() => navigate(`${settingsPath}?tab=account`)}>Account settings</MenuItem>
      <MenuSeparator />
      <MenuItem
        tone="negative"
        onSelect={() => signOut.mutate(undefined, { onSettled: () => navigate("/login") })}
      >
        Sign out
      </MenuItem>
    </Menu>
  );
}

/**
 * The finance reports in the top bar (plan §27.10): quiet text in navigation order, a Crita-green
 * underline on the current page. They carry the period while you are inside the system, so moving
 * between pages keeps your context. Under 1180 px they fold into a page menu, which also lists
 * Clario AI after the six reports (on wide screens the Ask Clario pill is its way in).
 */
import { ChevronDown } from "lucide-react";
import { NavLink, useLocation, useNavigate } from "react-router";

import { Menu, MenuItem, MenuSeparator } from "../design-system";
import { CLARIO, PAGES } from "../features/finance/pages";
import { cx } from "../lib/cx";
import styles from "./AppShell.module.css";
import { parseFinanceRoute, useFinanceSystems } from "./financeRoute";

export function FinancePagesNav({ workspaceId, base }: { workspaceId: string; base: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const route = parseFinanceRoute(location.pathname);
  const systems = useFinanceSystems(workspaceId);
  const system = systems.find((s) => s.key === route?.integration) ?? systems[0];
  if (!system) return <div className={styles.center} />;
  const here = route?.integration === system.key;
  const params = new URLSearchParams(here ? location.search : "");
  for (const name of ["assistant", "c", "q", "send"]) params.delete(name);
  const to = (page: string) => ({
    pathname: `${base}/${system.key}/finance/${page}`,
    search: params.toString(),
  });
  const current = [...PAGES, CLARIO].find((p) => here && p.value === route?.page);

  return (
    <div className={styles.center}>
      <nav className={styles.pages} aria-label="Finance pages">
        <ul>
          {PAGES.map((p) => (
            <li key={p.value}>
              <NavLink to={to(p.value)} className={cx(styles.pageLink)}>
                {p.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className={styles.pageMenu}>
        <Menu
          trigger={
            <button type="button" className={styles.pageMenuTrigger} aria-label="Change page">
              <span>{current?.label ?? "Finance"}</span>
              <ChevronDown size={15} aria-hidden="true" />
            </button>
          }
        >
          {PAGES.map((p) => (
            <MenuItem
              key={p.value}
              selected={current?.value === p.value}
              onSelect={() => void navigate(to(p.value))}
            >
              {p.label}
            </MenuItem>
          ))}
          <MenuSeparator />
          <MenuItem
            selected={current?.value === CLARIO.value}
            onSelect={() => void navigate(to(CLARIO.value))}
          >
            {CLARIO.label}
          </MenuItem>
        </Menu>
      </div>
    </div>
  );
}

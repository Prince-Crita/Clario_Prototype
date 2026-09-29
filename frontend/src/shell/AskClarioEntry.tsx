/**
 * Ask Clario in the top bar and on the phone bar (plan §27.10, §27.11): the way to Clario AI, set
 * apart from the report links as an ink pill carrying Clario's own mark in Crita green. It leads
 * to the Clario AI page (never a popup) and shows as current while you are there.
 */
import { BarChart3, LayoutGrid, MoreHorizontal, WalletCards } from "lucide-react";
import { Link, useLocation } from "react-router";

import { ApertureMark } from "../brand/ApertureMark";
import { cx } from "../lib/cx";
import styles from "./AppShell.module.css";
import { parseFinanceRoute, useAskClario, useFinanceSystems } from "./financeRoute";

export function AskClarioEntry({ workspaceId, base }: { workspaceId: string; base: string }) {
  const ask = useAskClario(workspaceId, base);
  if (!ask.href) return null;
  return (
    <Link
      to={ask.href}
      className={styles.askButton}
      aria-current={ask.active ? "page" : undefined}
      title="Clario AI: understand your business, not just your numbers"
    >
      <span className={styles.askMark} aria-hidden="true">
        <ApertureMark size={16} tone="inverse" />
      </span>
      <span className={styles.askText}>Ask Clario</span>
    </Link>
  );
}

/** Phones, on finance pages: four places and Ask Clario at the centre. */
export function MobileFinanceBar({
  workspaceId,
  base,
  onMore,
}: {
  workspaceId: string;
  base: string;
  onMore: () => void;
}) {
  const location = useLocation();
  const route = parseFinanceRoute(location.pathname);
  const systems = useFinanceSystems(workspaceId);
  const ask = useAskClario(workspaceId, base);
  const system = systems.find((s) => s.key === route?.integration);
  if (!route || !system) return null;
  const params = new URLSearchParams(location.search);
  for (const name of ["c", "q", "send"]) params.delete(name);
  const to = (page: string) => ({
    pathname: `${base}/${system.key}/finance/${page}`,
    search: params.toString(),
  });
  const item = (page: string, label: string, Icon: typeof LayoutGrid) => (
    <Link
      to={to(page)}
      className={styles.barItem}
      aria-current={route.page === page ? "page" : undefined}
    >
      <Icon size={20} aria-hidden="true" />
      <span>{label}</span>
    </Link>
  );
  return (
    <nav className={styles.mobileBar} aria-label="Quick navigation">
      {item("overview", "Overview", LayoutGrid)}
      {item("trends", "Trends", BarChart3)}
      {ask.href ? (
        <Link
          to={ask.href}
          className={cx(styles.barItem, styles.barAsk)}
          aria-current={ask.active ? "page" : undefined}
        >
          <span className={styles.barAskMark} aria-hidden="true">
            <ApertureMark size={20} tone="inverse" />
          </span>
          <span>Ask Clario</span>
        </Link>
      ) : null}
      {item("receivables", "Receivables", WalletCards)}
      <button type="button" className={styles.barItem} onClick={onMore}>
        <MoreHorizontal size={20} aria-hidden="true" />
        <span>More</span>
      </button>
    </nav>
  );
}

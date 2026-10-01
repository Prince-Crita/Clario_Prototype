/**
 * Overview — how the business is performing right now (plan §22.2, §27.12).
 *
 * One story, top to bottom:
 *   How is the business doing?           the six key figures, cash on hand first, in one row
 *   Where is it doing well or poorly?    Business performance
 *   What should the owner consider?      Decision support
 *   What could happen?                   Scenarios
 *
 * Every figure, sentence and recommendation comes from the same server data and the same
 * `intelligence.ts` rules as before; only the presentation is this page's own.
 */
import type { FinanceOverview, FinanceReceivables } from "../../../lib/api/types";
import { useSession } from "../../auth/hooks";
import { KeyFigures } from "../components/KeyFigures";
import { DecisionRows, PerformanceInsights, ScenarioCards } from "../components/OverviewPanels";
import { useFinanceTab } from "../hooks";
import { decisions, insights, signals } from "../intelligence";
import { OVERVIEW } from "../pages";
import { both } from "../query";
import styles from "./overview.module.css";
import { Skeleton } from "../../../design-system";
import { TabBody, type TabProps } from "./TabBody";

/** The Overview's shape while its figures load: the row of six cards, then the tiles below. */
function OverviewSkeleton() {
  return (
    <div className={styles.skeleton}>
      <div className={styles.skeletonCards}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} height={150} radius="md" />
        ))}
      </div>
      <Skeleton width={260} height={30} />
      <div className={styles.skeletonTiles}>
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} height={170} radius="md" />
        ))}
      </div>
    </div>
  );
}

/**
 * "Asha Rao", "asha.rao" → "Asha"; an email falls back to the part before the @. Returns null
 * when there is no name to use, so the greeting simply drops it rather than inventing one.
 */
function firstName(user: { full_name?: string; email?: string } | undefined): string | null {
  const source = user?.full_name?.trim() || user?.email?.split("@")[0] || "";
  const first = source.split(/[\s._-]+/).filter(Boolean)[0] ?? "";
  return first ? first.charAt(0).toUpperCase() + first.slice(1) : null;
}

export function OverviewTab({
  workspaceId,
  connectionId,
  pageHref,
  ask,
  context,
  controls,
}: TabProps) {
  // The session is read, never required: a page must not throw if it has lapsed mid-view.
  const name = firstName(useSession().data?.user);
  const overview = useFinanceTab<FinanceOverview>(workspaceId, connectionId, "overview");
  const receivables = useFinanceTab<FinanceReceivables>(workspaceId, connectionId, "receivables");

  return (
    <div className={styles.canvas} data-canvas="sunken">
      <header className={styles.header}>
        <div className={styles.headTop}>
          <div className={styles.headText}>
            <h1 className={styles.greeting}>
              {name ? (
                <>
                  Welcome back, <span>{name}</span>
                </>
              ) : (
                "Overview"
              )}
            </h1>
            <p className={styles.lede}>{OVERVIEW.lede}</p>
          </div>
          <div className={styles.controls}>{controls}</div>
        </div>
        {/* Whose books, from which system, how fresh, which year: one quiet strip. */}
        <div className={styles.meta}>{context}</div>
      </header>

      <TabBody query={both(overview, receivables)} skeleton={<OverviewSkeleton />}>
        {([o, r]) => (
          <>
            <KeyFigures kpis={o.kpis} ask={ask} />

            <section className={styles.band} aria-labelledby="performance-title">
              <div className={styles.bandHead}>
                <h2 id="performance-title" className={styles.bandTitle}>
                  Business performance
                </h2>
                <p className={styles.bandSub}>
                  Profitability, collections and costs, read from your figures.
                </p>
              </div>
              <PerformanceInsights items={insights(o)} ask={ask} />
            </section>

            <section className={styles.band} aria-labelledby="decisions-title">
              <div className={styles.bandHead}>
                <h2 id="decisions-title" className={styles.bandTitle}>
                  Decision support
                </h2>
                <p className={styles.bandSub}>
                  In order. Each step follows from the figures above; none of it is financial
                  advice.
                </p>
              </div>
              <DecisionRows items={decisions(o, r, signals(o, r))} pageHref={pageHref} ask={ask} />
            </section>

            <section className={styles.band} aria-labelledby="scenarios-title">
              <div className={styles.bandHead}>
                <h2 id="scenarios-title" className={styles.bandTitle}>
                  Scenarios
                </h2>
                <p className={styles.bandSub}>
                  Where things stand, and the levers that would move them — today's figures, not
                  forecasts.
                </p>
                <span className={styles.early}>Early view</span>
              </div>
              <ScenarioCards overview={o} receivables={r} />
            </section>
          </>
        )}
      </TabBody>
    </div>
  );
}

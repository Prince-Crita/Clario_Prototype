/**
 * Clario AI (plan §27.11): what the figures mean, what needs attention and what could be done
 * next, read top to bottom as one flow:
 *   1 Ask Clario        the Finance Assistant conversation (starting questions inside it), beside
 *                       a map of what Clario sees right now (counts of the sections below)
 *   2 Signals           what needs attention, most serious first
 *   3 Decision support  what to consider, in order
 *   4 Scenarios         what could happen: today's levers, not forecasts
 * Signals, decisions and scenarios are the same rules over the same server figures as before
 * (they moved here from the Overview); "Ask Clario" on any of them places the question in the
 * conversation above.
 */
import { ArrowDown } from "lucide-react";

import type { FinanceOverview, FinanceReceivables } from "../../../lib/api/types";
import { DecisionSupport, Scenarios } from "../components/Intelligence";
import { Section } from "../components/Section";
import { Signals } from "../components/Signals";
import { useFinanceTab } from "../hooks";
import { decisions, signals } from "../intelligence";
import { both } from "../query";
import { TabBody, type TabProps } from "./TabBody";
import styles from "./tabs.module.css";

export function ClarioTab({ workspaceId, connectionId, pageHref, ask, chat }: TabProps) {
  const overview = useFinanceTab<FinanceOverview>(workspaceId, connectionId, "overview");
  const receivables = useFinanceTab<FinanceReceivables>(workspaceId, connectionId, "receivables");
  const data = both(overview, receivables);
  const found = data.data ? signals(data.data[0], data.data[1]) : [];
  const high = found.filter((s) => s.severity === "high").length;
  const steps = data.data ? decisions(data.data[0], data.data[1], found) : [];

  return (
    <div className={styles.stack}>
      <div className={styles.askZone} id="ask">
        {chat ? (
          <div className={styles.chat}>{chat}</div>
        ) : (
          <div className={styles.pending}>
            <h2 className={styles.guideTitle}>Ask Clario isn't available for your role</h2>
            <p className={styles.muted}>
              A workspace owner or admin can give you access. Everything Clario sees in your figures
              is below.
            </p>
          </div>
        )}

        <aside className={styles.guide} aria-label="How Clario AI works">
          <nav className={styles.guideBlock} aria-labelledby="clario-sees">
            <h2 id="clario-sees" className={styles.guideTitle}>
              What Clario sees right now
            </h2>
            <ol className={styles.flow}>
              {chat ? (
                <li>
                  <span className={styles.flowHere}>
                    <span className={styles.flowStep}>1</span>
                    <span>
                      <strong>Ask a question</strong>
                      <span className={styles.flowNote}>
                        In plain words. Answers come from your books, with their sources.
                      </span>
                    </span>
                  </span>
                </li>
              ) : null}
              <li>
                <a href="#signals">
                  <span className={styles.flowStep}>2</span>
                  <span>
                    <strong>What needs attention</strong>
                    <span className={styles.flowNote}>
                      {data.data
                        ? found.length
                          ? `${found.length} ${found.length === 1 ? "signal" : "signals"}${high ? ` · ${high} high` : ""}`
                          : "Nothing right now"
                        : "Reading your figures…"}
                    </span>
                  </span>
                  <ArrowDown size={15} aria-hidden="true" />
                </a>
              </li>
              <li>
                <a href="#decisions">
                  <span className={styles.flowStep}>3</span>
                  <span>
                    <strong>What to consider</strong>
                    <span className={styles.flowNote}>
                      {data.data
                        ? steps.length
                          ? `${steps.length} ${steps.length === 1 ? "step" : "steps"}, in order`
                          : "Nothing to act on"
                        : "Reading your figures…"}
                    </span>
                  </span>
                  <ArrowDown size={15} aria-hidden="true" />
                </a>
              </li>
              <li>
                <a href="#scenarios">
                  <span className={styles.flowStep}>4</span>
                  <span>
                    <strong>What could happen</strong>
                    <span className={styles.flowNote}>Risk, where things stand, upside</span>
                  </span>
                  <ArrowDown size={15} aria-hidden="true" />
                </a>
              </li>
            </ol>
          </nav>
        </aside>
      </div>

      <TabBody query={data}>
        {([o, r]) => (
          <>
            <Section
              id="signals"
              eyebrow="2 · What needs attention"
              title="Signals"
              description="Conditions in your books that deserve attention, most serious first: what is happening, why it matters and what to consider."
              aside={
                found.length ? (
                  <span className={styles.count}>
                    {found.length} {found.length === 1 ? "signal" : "signals"}
                    {high ? ` · ${high} high` : ""}
                  </span>
                ) : null
              }
            >
              <Signals items={found} pageHref={pageHref} ask={ask} />
            </Section>

            <Section
              id="decisions"
              eyebrow="3 · What to consider"
              title="Decision support"
              description="In order. Each step follows from the signals and figures above; none of it is financial advice."
            >
              <DecisionSupport items={steps} pageHref={pageHref} ask={ask} />
            </Section>

            <Section
              id="scenarios"
              eyebrow="4 · What could happen"
              title="Scenarios"
              description="Where things stand, and the levers that would move them."
              aside={<span className={styles.early}>Early view</span>}
            >
              <Scenarios overview={o} receivables={r} />
            </Section>
          </>
        )}
      </TabBody>
    </div>
  );
}

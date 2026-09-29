/**
 * Frame for every chart (plan §25, §27.5): title, basis tag, and a "View as table" toggle that
 * renders the same data as an accessible table — for screen readers and for auditability.
 * The chart itself (Recharts, themed with `seriesColour` from ./palette) is passed as children from Phase 8.
 */
import { useId, useState, type ReactNode } from "react";

import { BasisTag, type Basis } from "../primitives/Figure";
import styles from "./ChartFrame.module.css";

interface ChartFrameProps {
  title: string;
  description?: string;
  basis?: Basis;
  window?: string | undefined;
  /** The same data as a table; shown instead of the chart when toggled. */
  table: ReactNode;
  children: ReactNode;
}

export function ChartFrame({
  title,
  description,
  basis,
  window,
  table,
  children,
}: ChartFrameProps) {
  const [asTable, setAsTable] = useState(false);
  const headingId = useId();
  return (
    <section className={styles.frame} aria-labelledby={headingId}>
      <header className={styles.header}>
        <div>
          <h2 id={headingId} className={styles.title}>
            {title}
          </h2>
          {description ? <p className={styles.description}>{description}</p> : null}
        </div>
        <div className={styles.tools}>
          {basis ? <BasisTag basis={basis} window={window} /> : null}
          <button
            type="button"
            className={styles.toggle}
            aria-pressed={asTable}
            onClick={() => setAsTable((v) => !v)}
          >
            {asTable ? "View as chart" : "View as table"}
          </button>
        </div>
      </header>
      <div className={styles.body}>{asTable ? table : children}</div>
    </section>
  );
}

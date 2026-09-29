/**
 * A single figure (plan §27.10): sentence-case label, large tabular figure, basis pill
 * ("Accrual · FY-to-date") and a context line. Negative values render in --negative
 * with a true minus sign (the value string arrives pre-formatted from lib/format).
 */
import type { ReactNode } from "react";

import styles from "./Figure.module.css";

export type Basis = "accrual" | "cash" | "billed" | "balance" | "ledger";

interface FigureProps {
  label: string;
  value: string;
  basis?: Basis;
  window?: string | undefined;
  context?: ReactNode;
  negative?: boolean;
}

export function BasisTag({ basis, window }: { basis: Basis; window?: string | undefined }) {
  return (
    <span className={styles.basis} data-basis={basis}>
      {basis}
      {window ? ` · ${window}` : ""}
    </span>
  );
}

export function Figure({ label, value, basis, window, context, negative }: FigureProps) {
  return (
    <figure className={styles.figure}>
      <figcaption className={styles.label}>{label}</figcaption>
      <p className={styles.value} data-negative={negative || undefined}>
        {value}
      </p>
      {basis ? <BasisTag basis={basis} window={window} /> : null}
      {context ? <p className={styles.context}>{context}</p> : null}
    </figure>
  );
}

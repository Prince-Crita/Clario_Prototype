/** Page header: optional eyebrow, one h1, a quiet meta line, and right-aligned actions. */
import type { ReactNode } from "react";

import styles from "./PageHeader.module.css";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  meta?: ReactNode;
  actions?: ReactNode;
  /** Hairline under the header; turn off when tabs directly follow (they draw their own rule). */
  divider?: boolean;
}

export function PageHeader({ eyebrow, title, meta, actions, divider = true }: PageHeaderProps) {
  return (
    <header className={styles.header} data-divider={divider || undefined}>
      <div className={styles.text}>
        {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
        <h1 className={styles.title}>{title}</h1>
        {meta ? <div className={styles.meta}>{meta}</div> : null}
      </div>
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}

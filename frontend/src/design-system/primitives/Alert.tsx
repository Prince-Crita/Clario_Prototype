/**
 * Inline alert bar (plan §27.3): icon + one sentence + at most one action. Full width, visually
 * distinct from status badges. `negative`/`warning` are announced immediately (role="alert").
 */
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { ReactNode } from "react";

import styles from "./Alert.module.css";

const ICONS = { info: Info, positive: CheckCircle2, warning: AlertTriangle, negative: XCircle };

interface AlertProps {
  tone: keyof typeof ICONS;
  title?: string;
  children: ReactNode;
  action?: ReactNode;
}

export function Alert({ tone, title, children, action }: AlertProps) {
  const Icon = ICONS[tone];
  const urgent = tone === "negative" || tone === "warning";
  return (
    <div className={styles.alert} data-tone={tone} role={urgent ? "alert" : "status"}>
      <Icon className={styles.icon} size={16} strokeWidth={2} aria-hidden="true" />
      <div className={styles.body}>
        {title ? <p className={styles.title}>{title}</p> : null}
        <div>{children}</div>
      </div>
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  );
}

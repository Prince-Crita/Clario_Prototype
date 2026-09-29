/** Status as coloured text + dot — not a pill (plan §27.3). Colour is never the only signal. */
import styles from "./Status.module.css";

interface StatusProps {
  tone: "neutral" | "positive" | "warning" | "negative" | "info";
  children: string;
}

export function Status({ tone, children }: StatusProps) {
  return (
    <span className={styles.status} data-tone={tone}>
      <span className={styles.dot} aria-hidden="true" />
      {children}
    </span>
  );
}

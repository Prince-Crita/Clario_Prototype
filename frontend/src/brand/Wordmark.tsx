/**
 * "Clario" wordmark (plan §28.1): Manrope SemiBold, tightened tracking, and the tittle of the
 * "i" replaced by the lime disc from the Aperture mark. Rendered as text (dotless ı + disc) so it
 * stays crisp at every size; `aria-label` keeps the accessible name "Clario".
 */
import styles from "./Wordmark.module.css";

import { ApertureMark } from "./ApertureMark";

interface WordmarkProps {
  size?: "sm" | "md" | "lg";
  tone?: "default" | "inverse";
}

export function Wordmark({ size = "md", tone = "default" }: WordmarkProps) {
  return (
    <span
      className={styles.wordmark}
      data-size={size}
      data-tone={tone}
      role="img"
      aria-label="Clario"
    >
      <span aria-hidden="true">
        Clar
        <span className={styles.i}>
          ı<span className={styles.tittle} />
        </span>
        o
      </span>
    </span>
  );
}

/** Horizontal lockup: mark + wordmark. */
export function Lockup({ size = "md", tone = "default" }: WordmarkProps) {
  const markSize = { sm: 22, md: 28, lg: 40 }[size];
  return (
    <span className={styles.lockup} data-size={size}>
      <ApertureMark size={markSize} tone={tone} />
      <Wordmark size={size} tone={tone} />
    </span>
  );
}

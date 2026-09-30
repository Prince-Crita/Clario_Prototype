/**
 * "Clario" wordmark (plan §28.1): Manrope SemiBold, tightened tracking, and the tittle of the
 * "i" replaced by the lime disc from the Aperture mark. Rendered as text (dotless ı + disc) so it
 * stays crisp at every size; `aria-label` keeps the accessible name "Clario".
 */
import styles from "./Wordmark.module.css";

import logo from "./logo.png";

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

/**
 * The app logo. Reads its image from `logo.png` in this folder — replace that file (same name)
 * to change the logo everywhere it appears; no code change needed.
 */
export function Lockup({ size = "md" }: WordmarkProps) {
  return <img className={styles.logo} data-size={size} src={logo} alt="Clario" />;
}

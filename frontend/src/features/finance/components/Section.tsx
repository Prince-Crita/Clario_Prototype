/**
 * A chapter of a page (plan §27.9): an optional small-caps eyebrow, a serif title, one line of
 * purpose and an aside, over a strong rule. Chapters are separated by space and rules, not boxes;
 * only content that reads as one object (a table, a statement) gets a surface.
 */
import { ArrowUpRight } from "lucide-react";
import { useId, type ReactNode } from "react";

import styles from "./Section.module.css";

interface SectionProps {
  title: string;
  eyebrow?: string | undefined;
  description?: string | undefined;
  aside?: ReactNode;
  id?: string;
  children: ReactNode;
}

export function Section({ title, eyebrow, description, aside, id, children }: SectionProps) {
  const heading = useId();
  return (
    <section className={styles.section} aria-labelledby={heading} id={id}>
      <header className={styles.head}>
        <div className={styles.text}>
          {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
          <h2 id={heading} className={styles.title}>
            {title}
          </h2>
          {description ? <p className={styles.description}>{description}</p> : null}
        </div>
        {aside ? <div className={styles.aside}>{aside}</div> : null}
      </header>
      {children}
    </section>
  );
}

/** A surface with a hairline: only for content that reads as one object. */
export function Panel({
  children,
  label,
  flush = false,
}: {
  children: ReactNode;
  label?: string;
  flush?: boolean;
}) {
  return (
    <div className={styles.panel} data-flush={flush || undefined} aria-label={label}>
      {children}
    </div>
  );
}

/** "Ask Clario" as a quiet action next to a figure, signal or chart. */
export function AskLink({
  question,
  ask,
  label = "Ask Clario",
}: {
  question: string;
  ask?: ((question: string, send?: boolean) => void) | undefined;
  label?: string;
}) {
  if (!ask) return null;
  return (
    <button
      type="button"
      className={styles.ask}
      onClick={() => ask(question)}
      title={`Ask Clario: “${question}”`}
    >
      {label}
      <ArrowUpRight size={13} aria-hidden="true" />
    </button>
  );
}

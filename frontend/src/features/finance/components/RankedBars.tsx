/**
 * A ranked list with proportional bars (revenue by client, where the money goes, ageing).
 * The list is the content: every value is written out; the bar is decorative and a flag is
 * always spelled out in text, never colour alone (plan §27.5).
 */
import { BasisTag, type Basis } from "../../../design-system";
import { plot } from "../format";
import styles from "./RankedBars.module.css";

export interface RankedRow {
  key: string;
  label: string;
  value: string; // already formatted
  amount: string; // decimal string, for the bar length only
  note?: string | undefined;
  flag?: string | undefined; // e.g. "Overdue ₹23,965"
}

interface RankedBarsProps {
  title: string;
  description?: string;
  basis?: Basis;
  window?: string | undefined;
  rows: RankedRow[];
  empty?: string;
}

export function RankedBars({ title, description, basis, window, rows, empty }: RankedBarsProps) {
  const max = Math.max(0, ...rows.map((r) => plot(r.amount)));
  const id = `ranked-${title.replace(/\W+/g, "-").toLowerCase()}`;
  return (
    <section className={styles.panel} aria-labelledby={id}>
      <header className={styles.header}>
        <div>
          <h2 id={id} className={styles.title}>
            {title}
          </h2>
          {description ? <p className={styles.description}>{description}</p> : null}
        </div>
        {basis ? <BasisTag basis={basis} window={window} /> : null}
      </header>
      {rows.length === 0 ? (
        <p className={styles.empty}>{empty ?? "Nothing to show yet."}</p>
      ) : (
        <ol className={styles.list}>
          {rows.map((row) => (
            <li key={row.key} className={styles.row} data-flagged={row.flag ? true : undefined}>
              <span className={styles.label}>{row.label}</span>
              <span className={styles.value}>{row.value}</span>
              <span className={styles.track} aria-hidden="true">
                <span
                  className={styles.bar}
                  style={{
                    width: `${max > 0 && plot(row.amount) > 0 ? Math.max(0.5, (plot(row.amount) / max) * 100) : 0}%`,
                  }}
                />
              </span>
              {row.flag || row.note ? (
                <span className={styles.meta}>
                  {row.flag ? <span className={styles.flag}>{row.flag}</span> : null}
                  {row.note ? <span>{row.note}</span> : null}
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

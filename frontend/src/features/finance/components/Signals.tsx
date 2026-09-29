/**
 * Signals (plan §27.10): business intelligence as horizontal rows, most serious first. Each one
 * reads WHAT is happening (a headline with the server's own figures), the EVIDENCE, WHY it
 * matters and what to CONSIDER, then where to look and "Ask Clario". Severity is a word in a pill
 * as well as the row's edge colour, never colour alone.
 */
import { ArrowRight } from "lucide-react";
import { Link } from "react-router";

import type { FinanceTab } from "../hooks";
import type { Signal } from "../intelligence";
import { AskLink } from "./Section";
import styles from "./Signals.module.css";

const SEVERITY = { high: "High", medium: "Medium", low: "Low" };

interface SignalsProps {
  items: Signal[];
  pageHref: (tab: FinanceTab) => { pathname: string; search: string };
  ask?: ((question: string, send?: boolean) => void) | undefined;
}

export function Signals({ items, pageHref, ask }: SignalsProps) {
  if (items.length === 0) {
    return (
      <p className={styles.clear}>
        No signals right now: nothing is overdue, and cash, tax and profitability show no warnings.
      </p>
    );
  }
  return (
    <ol className={styles.list}>
      {items.map((s, index) => (
        <li key={s.id} className={styles.signal} data-severity={s.severity}>
          <p className={styles.number} aria-hidden="true">
            {String(index + 1).padStart(2, "0")}
          </p>
          <div className={styles.body}>
            <p className={styles.meta}>
              <span className={styles.category}>{s.category}</span>
              <span className={styles.severity}>
                <span className="visually-hidden">Severity: </span>
                {SEVERITY[s.severity]}
              </span>
            </p>
            <h3 className={styles.headline}>{s.headline}</h3>
            {s.detail ? <p className={styles.detail}>{s.detail}</p> : null}
            {s.items?.length ? (
              <ul className={styles.evidence}>
                {s.items.map((item) => (
                  <li key={item.text}>
                    <span className={styles.itemText}>{item.text}</span>
                    {item.sub ? <span className={styles.itemSub}>{item.sub}</span> : null}
                  </li>
                ))}
                {s.more ? (
                  <li className={styles.more}>
                    and {s.more} more in {s.pageLabel}
                  </li>
                ) : null}
              </ul>
            ) : null}
            <dl className={styles.reason}>
              <div>
                <dt>Why it matters</dt>
                <dd>{s.why}</dd>
              </div>
              <div>
                <dt>Consider</dt>
                <dd>{s.consider}</dd>
              </div>
            </dl>
            <p className={styles.links}>
              <Link to={pageHref(s.page)} className={styles.open}>
                Open {s.pageLabel}
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
              <AskLink ask={ask} question={s.question} />
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

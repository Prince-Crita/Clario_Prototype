/**
 * What needs attention (plan §24.3, §27.3): dense rows grouped as Collections / Tax / Performance,
 * a severity bar on the left edge (with the severity also in text), the key fact first and the
 * date muted. The wording comes from the server, so the assistant says exactly the same.
 */
import { useState } from "react";

import type { ActionItem } from "../../../lib/api/types";
import styles from "./ActionList.module.css";

const GROUPS: { kind: ActionItem["kind"]; title: string }[] = [
  { kind: "overdue_invoice", title: "Collections" },
  { kind: "gst_payable", title: "Tax" },
  { kind: "accrual_loss", title: "Performance" },
];
const SEVERITY = { high: "High priority", medium: "Medium priority", low: "Low priority" };
const VISIBLE = 5; // most urgent first; the rest behind "Show all"

export function ActionList({ items }: { items: ActionItem[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  return (
    <section className={styles.panel} aria-labelledby="actions-title">
      <h2 id="actions-title" className={styles.title}>
        Needs attention
      </h2>
      {items.length === 0 ? (
        <p className={styles.empty}>Nothing needs attention today.</p>
      ) : (
        GROUPS.map(({ kind, title }) => {
          const group = items.filter((i) => i.kind === kind);
          if (group.length === 0) return null;
          const open = expanded.has(kind) || group.length <= VISIBLE;
          const shown = open ? group : group.slice(0, VISIBLE);
          return (
            <div key={kind} className={styles.group}>
              <h3 className={styles.groupTitle}>
                {title} <span className={styles.count}>{group.length}</span>
              </h3>
              <ul className={styles.list}>
                {shown.map((item) => (
                  <li
                    key={`${item.kind}-${item.reference ?? item.title}`}
                    className={styles.item}
                    data-severity={item.severity}
                  >
                    <span className="visually-hidden">{SEVERITY[item.severity]}: </span>
                    <span className={styles.fact}>{item.title}</span>
                    <span className={styles.detail}>{item.detail}</span>
                  </li>
                ))}
              </ul>
              {group.length > VISIBLE ? (
                <button
                  type="button"
                  className={styles.more}
                  aria-expanded={open}
                  onClick={() =>
                    setExpanded((current) => {
                      const next = new Set(current);
                      if (open) next.delete(kind);
                      else next.add(kind);
                      return next;
                    })
                  }
                >
                  {open ? "Show fewer" : `Show all ${group.length}`}
                </button>
              ) : null}
            </div>
          );
        })
      )}
    </section>
  );
}

/**
 * KPI band (plan §27.3): one strip divided by hairlines, not six cards. Each cell: label, 32-px
 * figure, basis tag with its window, and one context line composed from server-provided fields.
 */
import { Figure } from "../../../design-system";
import type { Kpi } from "../../../lib/api/types";
import { isNegative, money, percent } from "../format";
import styles from "./KpiBand.module.css";

function context(kpi: Kpi) {
  const { change } = kpi;
  if (kpi.key === "cash_collected" && kpi.related) {
    return `${percent(kpi.ratio)} of ${money(kpi.related.amount)} ${kpi.related.name}`;
  }
  if (kpi.key === "net_pnl" && kpi.ratio !== null && kpi.ratio !== undefined) {
    return `${percent(kpi.ratio)} margin`;
  }
  if (kpi.key === "receivables" && kpi.count !== null && kpi.count !== undefined) {
    return `${kpi.count} ${kpi.note ?? ""}`.trim();
  }
  if (change && change.percent !== null) {
    const down = isNegative(change.percent);
    // For costs, down is good news: the arrow says the direction, the colour says good or bad.
    return (
      <span className={styles.change} data-tone={down ? "positive" : "negative"}>
        <span aria-hidden="true">{down ? "▼" : "▲"}</span>{" "}
        {percent(change.percent.replace(/^-/, ""))} {down ? "lower" : "higher"} ·{" "}
        <span className={styles.muted}>{change.compared_to.toLowerCase()}</span>
      </span>
    );
  }
  return kpi.note ?? null;
}

export function KpiBand({ kpis }: { kpis: Kpi[] }) {
  return (
    <section className={styles.band} aria-label="Key figures">
      {kpis.map((kpi) => (
        <div key={kpi.key} className={styles.cell}>
          <Figure
            label={kpi.label}
            value={money(kpi.value)}
            basis={kpi.basis}
            window={kpi.window.label}
            negative={isNegative(kpi.value)}
            context={context(kpi)}
          />
        </div>
      ))}
    </section>
  );
}

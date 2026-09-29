/**
 * The P&L as a typeset mini income statement (plan §27.3): Revenue, less COGS, = Gross profit,
 * less Opex, = Net, with rules — like a printed statement, not a banner.
 */
import { BasisTag } from "../../../design-system";
import type { FinanceOverview } from "../../../lib/api/types";
import { isNegative, isZero, money, percent } from "../format";
import styles from "./PnlStatement.module.css";

type Pnl = FinanceOverview["pnl"];

function Line({
  label,
  value,
  kind = "item",
  note,
}: {
  label: string;
  value: string;
  kind?: "item" | "less" | "subtotal" | "total";
  note?: string | undefined;
}) {
  const shown = kind === "less" ? `− ${money(value)}` : money(value);
  return (
    <div className={styles.line} data-kind={kind}>
      <dt>{label}</dt>
      <dd>
        {note ? <span className={styles.note}>{note}</span> : null}
        <span className={styles.amount} data-negative={isNegative(value) || undefined}>
          {shown}
        </span>
      </dd>
    </div>
  );
}

export function PnlStatement({ pnl }: { pnl: Pnl }) {
  const nonOperating = !isZero(pnl.other_income) || !isZero(pnl.other_expenses);
  return (
    <section className={styles.panel} aria-labelledby="pnl-title">
      <header className={styles.header}>
        <h2 id="pnl-title" className={styles.title}>
          Profit and loss
        </h2>
        <BasisTag basis={pnl.basis} window={pnl.window.label} />
      </header>
      <dl className={styles.statement}>
        <Line label="Revenue" value={pnl.revenue} />
        <Line label="Less cost of goods sold" value={pnl.cogs} kind="less" />
        <Line
          label="Gross profit"
          value={pnl.gross_profit}
          kind="subtotal"
          note={pnl.gross_margin !== null ? `${percent(pnl.gross_margin)} margin` : undefined}
        />
        <Line label="Less operating expenses" value={pnl.operating_expenses} kind="less" />
        <Line
          label={isNegative(pnl.net_pnl) ? "Net loss" : "Net profit"}
          value={pnl.net_pnl}
          kind="total"
          note={pnl.net_margin !== null ? `${percent(pnl.net_margin)} margin` : undefined}
        />
      </dl>
      <ul className={styles.footnotes}>
        {pnl.largest_cost ? (
          <li>
            Largest cost: {pnl.largest_cost.name}, {money(pnl.largest_cost.amount)}
          </li>
        ) : null}
        <li>Spent this month so far: {money(pnl.latest_month_spend)} (cash)</li>
        {nonOperating ? (
          <li>
            Not included: other income {money(pnl.other_income)} and other expenses{" "}
            {money(pnl.other_expenses)}
          </li>
        ) : null}
      </ul>
    </section>
  );
}

/**
 * Dense data table (plan §27.3): sticky header, right-aligned numbers, 13-px text, row hover,
 * optional totals row, sticky first column on narrow screens. Not a card.
 */
import type { ReactNode } from "react";

import styles from "./DataTable.module.css";

export interface Column<Row> {
  key: string;
  header: string;
  cell: (row: Row) => ReactNode;
  align?: "start" | "end";
  width?: string;
}

interface DataTableProps<Row> {
  caption: string;
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  totals?: Partial<Record<string, ReactNode>>;
  /** Visually hide the caption when a heading above already names the table. */
  hideCaption?: boolean;
}

export function DataTable<Row>({
  caption,
  columns,
  rows,
  rowKey,
  totals,
  hideCaption,
}: DataTableProps<Row>) {
  return (
    <div className={styles.scroller}>
      <table className={styles.table}>
        <caption className={hideCaption ? "visually-hidden" : styles.caption}>{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                data-align={c.align ?? "start"}
                style={{ width: c.width }}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((c, i) =>
                i === 0 ? (
                  <th key={c.key} scope="row" data-align={c.align ?? "start"}>
                    {c.cell(row)}
                  </th>
                ) : (
                  <td key={c.key} data-align={c.align ?? "start"}>
                    {c.cell(row)}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
        {totals ? (
          <tfoot>
            <tr>
              {columns.map((c, i) =>
                i === 0 ? (
                  <th key={c.key} scope="row">
                    {totals[c.key] ?? "Total"}
                  </th>
                ) : (
                  <td key={c.key} data-align={c.align ?? "start"}>
                    {totals[c.key] ?? null}
                  </td>
                ),
              )}
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}

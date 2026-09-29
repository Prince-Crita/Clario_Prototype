/**
 * The invoice register (plan §22.2, §27.3): all invoices newest first, status as text + dot,
 * overdue days in --negative, a totals row, and "Load more" (server cursor, 50 at a time).
 */
import { useState } from "react";

import { BasisTag, Button, DataTable, Skeleton, Status, type Column } from "../../../design-system";
import { ApiError } from "../../../lib/api/client";
import type { Invoice } from "../../../lib/api/types";
import { dateLabel, money } from "../format";
import { useInvoiceRegister, type InvoiceFilter } from "../hooks";
import styles from "./InvoiceRegister.module.css";

const FILTERS: { value: InvoiceFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unpaid", label: "Unpaid" },
  { value: "overdue", label: "Overdue" },
];

const STATUS: Record<
  Invoice["status"],
  { label: string; tone: "neutral" | "positive" | "warning" | "negative" | "info" }
> = {
  paid: { label: "Paid", tone: "positive" },
  partially_paid: { label: "Part paid", tone: "info" },
  open: { label: "Open", tone: "neutral" },
  overdue: { label: "Overdue", tone: "negative" },
  draft: { label: "Draft", tone: "neutral" },
  void: { label: "Void", tone: "neutral" },
  unknown: { label: "Check in Zoho", tone: "warning" },
};

const COLUMNS: Column<Invoice>[] = [
  {
    key: "number",
    header: "Invoice",
    cell: (i) => <span className={styles.number}>{i.invoice_number}</span>,
  },
  { key: "client", header: "Client", cell: (i) => i.party_name },
  { key: "date", header: "Date", cell: (i) => dateLabel(i.invoice_date) },
  { key: "billed", header: "Billed", align: "end", cell: (i) => money(i.total) },
  {
    key: "balance",
    header: "Balance",
    align: "end",
    cell: (i) =>
      i.status === "paid" ? (
        <span className={styles.muted}>—</span>
      ) : (
        <span data-overdue={i.status === "overdue" || undefined} className={styles.balance}>
          {money(i.balance)}
        </span>
      ),
  },
  {
    key: "status",
    header: "Status",
    cell: (i) => (
      <span className={styles.status}>
        <Status tone={STATUS[i.status].tone}>{STATUS[i.status].label}</Status>
        {i.status === "overdue" ? (
          <span className={styles.days}>
            {i.days_overdue === 1 ? "1 day" : `${i.days_overdue} days`}
          </span>
        ) : null}
      </span>
    ),
  },
];

interface InvoiceRegisterProps {
  workspaceId: string;
  connectionId: string;
  totals: { count: number; billed: string; balance: string };
}

export function InvoiceRegister({ workspaceId, connectionId, totals }: InvoiceRegisterProps) {
  const [filter, setFilter] = useState<InvoiceFilter>("all");
  const register = useInvoiceRegister(workspaceId, connectionId, filter);
  const rows = register.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <section className={styles.panel} aria-labelledby="register-title">
      <header className={styles.header}>
        <div>
          <h2 id="register-title" className={styles.title}>
            Invoice register
          </h2>
          <p className={styles.description}>
            {totals.count} invoices, newest first. Drafts and voids are left out of the totals.
          </p>
        </div>
        <div className={styles.tools}>
          <BasisTag basis="billed" window="all invoices" />
          <div className={styles.filters} role="group" aria-label="Show">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                className={styles.filter}
                aria-pressed={filter === f.value}
                onClick={() => setFilter(f.value)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </header>
      {register.isPending ? (
        <Skeleton height={320} radius="md" />
      ) : register.isError ? (
        <p className={styles.error} role="alert">
          {register.error instanceof ApiError
            ? register.error.detail
            : "The register couldn't load."}
        </p>
      ) : (
        <>
          <DataTable
            caption="Invoice register"
            hideCaption
            columns={COLUMNS}
            rows={rows}
            rowKey={(i) => i.id}
            {...(filter === "all"
              ? {
                  totals: {
                    number: "Total",
                    billed: money(totals.billed),
                    balance: money(totals.balance),
                  },
                }
              : {})}
          />
          {rows.length === 0 ? <p className={styles.muted}>No invoices match.</p> : null}
          {register.hasNextPage ? (
            <div>
              <Button
                size="sm"
                pending={register.isFetchingNextPage}
                pendingLabel="Loading…"
                onClick={() => void register.fetchNextPage()}
              >
                Load more
              </Button>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

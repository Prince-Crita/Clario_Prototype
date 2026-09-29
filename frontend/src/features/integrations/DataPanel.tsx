/**
 * What Clario has imported from a connected system (plan §31): each dataset with its record count,
 * the period it covers and when it was last refreshed; the import in progress; partial failures
 * (the last good data is kept); and "Refresh now" for anyone who can see the connection.
 */
import { RefreshCw } from "lucide-react";

import { Alert, Button, DataTable, Skeleton, Status, type Column } from "../../design-system";
import { ApiError } from "../../lib/api/client";
import type { DatasetStatus, IntegrationTile, SyncStatus } from "../../lib/api/types";
import styles from "./IntegrationPage.module.css";
import { useRefresh, useSyncStatus } from "./sync";

const WHEN = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
});
const MONTH = new Intl.DateTimeFormat("en-IN", { month: "short", year: "numeric" });
const DAY = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const COUNT = new Intl.NumberFormat("en-IN");

function covers(d: DatasetStatus): string {
  if (!d.window_start || !d.window_end) return d.status === "never" ? "—" : "Everything";
  const start = new Date(`${d.window_start}T00:00:00`);
  const end = new Date(`${d.window_end}T00:00:00`);
  if (d.window_start === d.window_end) return `As of ${DAY.format(end)}`;
  return `${MONTH.format(start)} – ${DAY.format(end)}`;
}

const COLUMNS: Column<DatasetStatus>[] = [
  { key: "label", header: "Data", cell: (d) => d.label },
  {
    key: "rows",
    header: "Records",
    align: "end",
    cell: (d) => (d.row_count === null ? "—" : COUNT.format(d.row_count)),
  },
  { key: "covers", header: "Covers", cell: covers },
  {
    key: "updated",
    header: "Updated",
    cell: (d) =>
      d.status === "failed" ? (
        <Status tone="warning">Not refreshed</Status>
      ) : d.last_success_at ? (
        WHEN.format(new Date(d.last_success_at))
      ) : (
        "—"
      ),
  },
];

function progress(status: SyncStatus): string {
  const started = status.run ? new Date(status.run.started_at).getTime() : 0;
  const done = status.datasets.filter(
    (d) => d.last_attempt_at && new Date(d.last_attempt_at).getTime() >= started,
  ).length;
  return `${done} of ${status.datasets.length}`;
}

interface DataPanelProps {
  tile: IntegrationTile;
  workspaceId: string;
  connectionId: string;
}

export function DataPanel({ tile, workspaceId, connectionId }: DataPanelProps) {
  const sync = useSyncStatus(workspaceId, connectionId);
  const refresh = useRefresh(workspaceId, connectionId);
  const status = sync.data;
  const running = status?.state === "running";
  const failed = status?.datasets.filter((d) => d.status === "failed") ?? [];
  const refreshError = refresh.error instanceof ApiError ? refresh.error.detail : null;

  return (
    <section className={`${styles.panel} ${styles.wide}`} aria-labelledby="data-title">
      <div className={styles.panelHead}>
        <div>
          <h2 id="data-title" className={styles.panelTitle}>
            Data in Clario
          </h2>
          <p className={styles.meta} aria-live="polite">
            {!status
              ? "Checking…"
              : running
                ? `Importing from ${tile.name}… ${progress(status)} done`
                : status.as_of
                  ? `Up to date as of ${WHEN.format(new Date(status.as_of))}`
                  : status.run
                    ? "Some data hasn't been imported yet"
                    : "Nothing imported yet"}
          </p>
        </div>
        <Button
          size="sm"
          icon={<RefreshCw size={14} aria-hidden="true" />}
          pending={refresh.isPending || running}
          pendingLabel={running ? "Importing…" : "Starting…"}
          onClick={() => refresh.mutate()}
          disabled={tile.connection_state !== "connected"}
        >
          Refresh now
        </Button>
      </div>
      {refreshError ? <Alert tone="info">{refreshError}</Alert> : null}
      {!running && failed.length > 0 ? (
        <Alert tone="warning" title="Some data couldn't be refreshed">
          {failed.map((d) => d.label).join(", ")} kept the last data Clario imported
          {failed.some((d) => d.last_success_at) ? "" : " (none yet)"}. Try again later; if it keeps
          happening, contact Crita support.
        </Alert>
      ) : null}
      {sync.isPending ? (
        <Skeleton height={220} radius="md" />
      ) : status ? (
        <DataTable
          caption={`Data imported from ${tile.name}`}
          hideCaption
          columns={COLUMNS}
          rows={status.datasets}
          rowKey={(d) => d.key}
        />
      ) : null}
    </section>
  );
}

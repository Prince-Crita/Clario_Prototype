/**
 * /w/:workspace/:integration/finance/:tab — the Finance Command Centre (plan §22, §25).
 *
 * Header: organisation, data-as-of, sync state, Refresh live and a link to the connection.
 * Tabs are real URLs; only the active tab's data is fetched. Opening a tab refreshes stale data
 * in the background; `useSyncWatcher` notices the run and reloads the tabs when it finishes.
 * Loaded lazily (charts are not in the main bundle).
 */
import { MessageSquareText, RefreshCw } from "lucide-react";
import { lazy, Suspense, useRef } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router";

import { Alert, Button, PageHeader, Skeleton, Status, Tabs } from "../../design-system";
import { ApiError } from "../../lib/api/client";
import { fiscalYearLabel } from "../../lib/labels";
import { PANEL_ID, type PanelMode } from "../assistant/panel";
import { useIntegration } from "../integrations/hooks";
import { useRefresh } from "../integrations/sync";
import { useCurrentWorkspace, useWorkspaceDetail } from "../workspace/hooks";
import styles from "./CommandCentre.module.css";
import { stampLabel } from "./format";
import { useSyncWatcher, type FinanceTab } from "./hooks";
import { BalanceSheetTab, GstTab } from "./tabs/LedgerTabs";
import { OverviewTab } from "./tabs/OverviewTab";
import { ReceivablesTab } from "./tabs/ReceivablesTab";
import { TrendsTab } from "./tabs/TrendsTab";

// The panel is its own chunk, fetched the first time someone opens it.
const AssistantPanel = lazy(() => import("../assistant/AssistantPanel"));

const TABS: { value: FinanceTab; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "trends", label: "Trends & Analysis" },
  { value: "balance-sheet", label: "Balance Sheet" },
  { value: "gst", label: "GST" },
  { value: "receivables", label: "Receivables" },
];

export default function CommandCentre() {
  const { integration: key = "", tab = "overview" } = useParams();
  const workspace = useCurrentWorkspace();
  const integration = useIntegration(workspace.id, key);
  const detail = useWorkspaceDetail(workspace.id);
  const overview = `/w/${workspace.slug}/${key}`;

  if (integration.isPending) {
    return (
      <div className={styles.loading} aria-busy="true">
        <Skeleton width="40%" height={28} />
        <Skeleton height={176} radius="md" />
      </div>
    );
  }
  const tile = integration.data;
  const connection = tile?.connection;
  if (!tile || tile.domain !== "finance" || !connection?.account) {
    return <Navigate to={overview} replace />;
  }
  if (!TABS.some((t) => t.value === tab))
    return <Navigate to={`${overview}/finance/overview`} replace />;

  return (
    <Centre
      workspaceId={workspace.id}
      connectionId={connection.id}
      base={overview}
      tab={tab as FinanceTab}
      organisation={connection.account.name}
      system={tile.name}
      domainName={tile.domain_name}
      canAsk={detail.data?.permissions.includes("assistant.use") ?? false}
      fiscalStart={connection.account.fiscal_year_start_month ?? null}
      needsReauth={tile.connection_state === "needs_reauth"}
      canManage={tile.can_manage}
    />
  );
}

interface CentreProps {
  workspaceId: string;
  connectionId: string;
  base: string;
  tab: FinanceTab;
  organisation: string;
  system: string;
  domainName: string;
  canAsk: boolean;
  fiscalStart: number | null;
  needsReauth: boolean;
  canManage: boolean;
}

function Centre(props: CentreProps) {
  const { workspaceId, connectionId, base, tab, organisation, system, needsReauth, canManage } =
    props;
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const askButton = useRef<HTMLButtonElement>(null);
  const requested = search.get("assistant");
  const mode: PanelMode | null =
    props.canAsk && (requested === "open" || requested === "full") ? requested : null;
  const conversationId = mode ? search.get("c") : null;

  /** Panel state lives in the URL (plan §9.3), so a reload or a shared link keeps it. */
  const setPanel = (next: PanelMode | null, conversation: string | null = conversationId) => {
    setSearch(
      (current) => {
        const params = new URLSearchParams(current);
        params.delete("assistant");
        params.delete("c");
        if (next) params.set("assistant", next);
        if (next && conversation) params.set("c", conversation);
        return params;
      },
      { replace: true },
    );
    if (!next) askButton.current?.focus();
  };
  const sync = useSyncWatcher(workspaceId, connectionId);
  const refresh = useRefresh(workspaceId, connectionId);
  const running = sync.data?.state === "running";
  const asOf = sync.data?.as_of;
  const refreshError = refresh.error instanceof ApiError ? refresh.error.detail : null;
  const tabProps = { workspaceId, connectionId };

  return (
    <div className={styles.page}>
      <PageHeader
        eyebrow={`Finance · ${system}`}
        title={organisation}
        divider={false}
        meta={
          <span className={styles.meta}>
            {props.fiscalStart ? (
              <span>Financial year {fiscalYearLabel(props.fiscalStart)}</span>
            ) : null}
            <span aria-live="polite">
              {!sync.data ? null : running ? (
                <Status tone="info">{`Updating from ${system}…`}</Status>
              ) : asOf ? (
                `Data as of ${stampLabel(asOf)}`
              ) : (
                "Not fully imported yet"
              )}
            </span>
          </span>
        }
        actions={
          <>
            <Link to={`${base}/connection`} className={styles.link}>
              Connection
            </Link>
            {props.canAsk ? (
              <Button
                ref={askButton}
                size="sm"
                variant={mode ? "secondary" : "primary"}
                icon={<MessageSquareText size={14} aria-hidden="true" />}
                aria-expanded={mode !== null}
                aria-controls={mode ? PANEL_ID : undefined}
                onClick={() => setPanel(mode ? null : "open")}
              >
                {`Ask ${props.domainName}`}
              </Button>
            ) : null}
            <Button
              size="sm"
              icon={<RefreshCw size={14} aria-hidden="true" />}
              pending={refresh.isPending || running}
              pendingLabel={running ? "Updating…" : "Starting…"}
              disabled={needsReauth}
              onClick={() => refresh.mutate()}
            >
              Refresh live
            </Button>
          </>
        }
      />
      {needsReauth ? (
        <Alert
          tone="warning"
          title={`${system} needs reconnecting`}
          action={<Link to={`${base}/connection`}>{canManage ? "Reconnect" : "Details"}</Link>}
        >
          Clario can't read new data, so these figures stop at the last refresh.
          {canManage ? "" : " Ask a workspace owner or admin to reconnect it."}
        </Alert>
      ) : null}
      {refreshError ? <Alert tone="info">{refreshError}</Alert> : null}
      {!running && sync.data && !asOf ? (
        <Alert tone="info" action={<Link to={`${base}/connection`}>See import status</Link>}>
          Some data hasn't been imported yet, so figures may be incomplete.
        </Alert>
      ) : null}
      <div className={styles.body} data-assistant={mode ?? undefined}>
        {mode !== "full" ? (
          <div className={styles.dashboard}>
            <Tabs
              label="Command Centre sections"
              value={tab}
              onValueChange={(value) =>
                void navigate({ pathname: `${base}/finance/${value}`, search: search.toString() })
              }
              tabs={TABS.map((t) => ({
                value: t.value,
                label: t.label,
                content:
                  t.value === "overview" ? (
                    <OverviewTab {...tabProps} />
                  ) : t.value === "trends" ? (
                    <TrendsTab {...tabProps} />
                  ) : t.value === "receivables" ? (
                    <ReceivablesTab {...tabProps} />
                  ) : t.value === "gst" ? (
                    <GstTab {...tabProps} />
                  ) : (
                    <BalanceSheetTab {...tabProps} />
                  ),
              }))}
            />
          </div>
        ) : null}
        {mode ? (
          <>
            <button
              type="button"
              className={styles.scrim}
              aria-hidden="true"
              tabIndex={-1}
              onClick={() => setPanel(null)}
            />
            <Suspense fallback={<div className={styles.panelLoading} aria-busy="true" />}>
              <AssistantPanel
                workspaceId={workspaceId}
                connectionId={connectionId}
                system={system}
                organisation={organisation}
                domainName={props.domainName}
                mode={mode}
                conversationId={conversationId}
                onConversationChange={(id) => setPanel(mode, id)}
                onModeChange={(next) => setPanel(next)}
                needsReauth={needsReauth}
                canManage={canManage}
                connectionHref={`${base}/connection`}
              />
            </Suspense>
          </>
        ) : null}
      </div>
    </div>
  );
}

/**
 * /w/:workspace/:integration/finance/:page — the Finance Command Centre, "Crita Intelligence"
 * (plan §22, §25, §27.10).
 *
 * The top bar (in the shell) carries the six reports and Ask Clario, which leads to the Clario AI
 * page (finance/clario): the Finance Assistant conversation with Signals, Decision support and
 * Scenarios. Each page opens with a compact header: the organisation and sync state, the page
 * title and its question, then the date, period and Sync on the right. Every report has an Ask
 * Clario box (a card on the Overview, a strip elsewhere); asking there goes to Clario AI with the
 * question. Pages are real URLs that keep the period and conversation; only the active page's
 * data is fetched. Opening a page refreshes stale data in the background;
 * `useSyncWatcher` notices the run and reloads the pages when it finishes. Loaded lazily.
 */
import { RefreshCw } from "lucide-react";
import { lazy, Suspense } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router";

import { Alert, Button, Skeleton } from "../../design-system";
import { ApiError } from "../../lib/api/client";
import { fiscalYearLabel } from "../../lib/labels";
import { useIntegration } from "../integrations/hooks";
import { useRefresh } from "../integrations/sync";
import { useCurrentWorkspace, useWorkspaceDetail } from "../workspace/hooks";
import { AskBar } from "./AskBar";
import styles from "./CommandCentre.module.css";
import { stampLabel } from "./format";
import { useSyncWatcher, type FinanceTab } from "./hooks";
import { CLARIO, OVERVIEW, PAGES } from "./pages";
import { isMonthKey, isPeriodKey, resolvePeriod, type PeriodKey } from "./period";
import { PeriodPicker } from "./PeriodPicker";
import { ClarioTab } from "./tabs/ClarioTab";
import { BalanceSheetTab, GstTab } from "./tabs/LedgerTabs";
import { OverviewTab } from "./tabs/OverviewTab";
import { PayablesTab } from "./tabs/PayablesTab";
import { ReceivablesTab } from "./tabs/ReceivablesTab";
import type { TabProps } from "./tabs/TabBody";
import { TrendsTab } from "./tabs/TrendsTab";

// The conversation is its own chunk, fetched the first time someone opens Clario AI.
const AssistantPanel = lazy(() => import("../assistant/AssistantPanel"));

const DATELINE = new Intl.DateTimeFormat("en-IN", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

export default function CommandCentre() {
  const { integration: key = "", tab = "overview" } = useParams();
  const workspace = useCurrentWorkspace();
  const integration = useIntegration(workspace.id, key);
  const detail = useWorkspaceDetail(workspace.id);
  const overview = `/w/${workspace.slug}/${key}`;

  if (integration.isPending) {
    return (
      <div className={styles.loading} aria-busy="true">
        <Skeleton width="30%" height={26} />
        <Skeleton height={176} radius="md" />
      </div>
    );
  }
  const tile = integration.data;
  const connection = tile?.connection;
  if (!tile || tile.domain !== "finance" || !connection?.account) {
    return <Navigate to={overview} replace />;
  }
  if (tab !== CLARIO.value && !PAGES.some((t) => t.value === tab))
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
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const onClario = tab === CLARIO.value;
  const conversationId = onClario ? search.get("c") : null;
  const page = onClario ? CLARIO : (PAGES.find((p) => p.value === tab) ?? OVERVIEW);

  // ---------------------------------------------------------------- period (URL state)
  const today = new Date();
  const periodKey = search.get("period");
  const from = search.get("from");
  const to = search.get("to");
  const period = resolvePeriod(
    isPeriodKey(periodKey) ? periodKey : "all",
    today,
    props.fiscalStart ?? 4,
    isMonthKey(from) && isMonthKey(to) ? { from, to } : null,
  );
  const setPeriod = (key: PeriodKey, custom?: { from: string; to: string }) =>
    setSearch(
      (current) => {
        const params = new URLSearchParams(current);
        for (const name of ["period", "from", "to"]) params.delete(name);
        if (key !== "all") params.set("period", key);
        if (key === "custom" && custom) {
          params.set("from", custom.from);
          params.set("to", custom.to);
        }
        return params;
      },
      { replace: true },
    );

  /** The conversation lives in the URL (plan §9.3), so a reload or a shared link keeps it. */
  const clarioSearch = (conversation: string | null, question?: string, send = false) => {
    const params = new URLSearchParams(search);
    for (const name of ["assistant", "c", "q", "send"]) params.delete(name);
    if (conversation) params.set("c", conversation);
    if (question) params.set("q", question);
    if (question && send) params.set("send", "1");
    return params;
  };
  const setConversation = (id: string | null) => setSearch(clarioSearch(id), { replace: true });
  /**
   * Ask Clario with `question` in a new conversation; `send` asks it at once (typed into an Ask
   * box), otherwise it is placed in the box to review. From a report this goes to Clario AI; on
   * Clario AI it fills the conversation at the top of the page.
   */
  const ask = props.canAsk
    ? (question: string, send = false) => {
        const params = clarioSearch(null, question, send);
        if (onClario) {
          setSearch(params, { replace: true });
          document.getElementById("ask")?.scrollIntoView({ behavior: "smooth", block: "start" });
        } else {
          void navigate({ pathname: `${base}/finance/${CLARIO.value}`, search: params.toString() });
        }
      }
    : undefined;

  const pageHref = (value: FinanceTab) => ({
    pathname: `${base}/finance/${value}`,
    search: clarioSearch(value === CLARIO.value ? conversationId : null).toString(),
  });

  const sync = useSyncWatcher(workspaceId, connectionId);
  const refresh = useRefresh(workspaceId, connectionId);
  const running = sync.data?.state === "running";
  const asOf = sync.data?.as_of;
  const refreshError = refresh.error instanceof ApiError ? refresh.error.detail : null;
  const tabProps: TabProps = {
    workspaceId,
    connectionId,
    period,
    pageHref,
    ask,
    askCard: ask ? (
      <AskBar organisation={organisation} prompts={page.prompts} onAsk={ask} variant="card" />
    ) : null,
    chat: props.canAsk ? (
      <Suspense fallback={<div className={styles.panelLoading} aria-busy="true" />}>
        <AssistantPanel
          workspaceId={workspaceId}
          connectionId={connectionId}
          system={system}
          organisation={organisation}
          domainName={props.domainName}
          conversationId={conversationId}
          suggestions={CLARIO.prompts}
          prefill={search.get("q")}
          autoSend={search.get("send") === "1"}
          onConversationChange={setConversation}
          needsReauth={needsReauth}
          canManage={canManage}
          connectionHref={`${base}/connection`}
        />
      </Suspense>
    ) : null,
  };

  // Links from before Clario AI was a page (`?assistant=open`) land on it, conversation kept.
  if (search.has("assistant")) {
    const params = new URLSearchParams(search);
    params.delete("assistant");
    return (
      <Navigate
        to={{ pathname: `${base}/finance/${CLARIO.value}`, search: params.toString() }}
        replace
      />
    );
  }

  const state = (tone: string, text: string) => (
    <span className={styles.state} data-tone={tone}>
      <span className={styles.dot} aria-hidden="true" />
      {text}
    </span>
  );
  const status = needsReauth
    ? state("warning", "Reconnect needed")
    : !sync.data
      ? null
      : running
        ? state("info", `Updating from ${system}…`)
        : asOf
          ? state("positive", `Synced ${stampLabel(asOf)}`)
          : state("neutral", "Not fully imported yet");

  return (
    <div className={styles.page}>
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
      <div className={styles.dashboard}>
        <header className={styles.header}>
          <div className={styles.headText}>
            <p className={styles.context} aria-live="polite">
              <span className={styles.org}>{organisation}</span>
              <span>{system}</span>
              {status}
              {props.fiscalStart ? (
                <span>Financial year {fiscalYearLabel(props.fiscalStart)}</span>
              ) : null}
              <Link to={`${base}/connection`} className={styles.link}>
                Connection
              </Link>
            </p>
            <h1 className={styles.title}>{page.label}</h1>
            <p className={styles.lede}>{page.lede}</p>
          </div>
          <div className={styles.tools}>
            <span className={styles.today}>{DATELINE.format(today)}</span>
            <div className={styles.controls}>
              {onClario ? null : (
                <PeriodPicker period={period} today={today} onChange={setPeriod} />
              )}
              <Button
                size="sm"
                variant="secondary"
                className={styles.sync}
                icon={<RefreshCw size={15} aria-hidden="true" />}
                pending={refresh.isPending || running}
                pendingLabel={running ? "Updating…" : "Starting…"}
                disabled={needsReauth}
                onClick={() => refresh.mutate()}
                title={`Refresh from ${system}`}
              >
                Sync
              </Button>
            </div>
          </div>
        </header>
        {ask && tab !== "overview" && !onClario ? (
          <AskBar organisation={organisation} prompts={page.prompts} onAsk={ask} />
        ) : null}
        {tab === "overview" ? (
          <OverviewTab {...tabProps} />
        ) : tab === "trends" ? (
          <TrendsTab {...tabProps} />
        ) : tab === "payables" ? (
          <PayablesTab {...tabProps} />
        ) : tab === "gst" ? (
          <GstTab {...tabProps} />
        ) : tab === "receivables" ? (
          <ReceivablesTab {...tabProps} />
        ) : tab === "balance-sheet" ? (
          <BalanceSheetTab {...tabProps} />
        ) : (
          <ClarioTab {...tabProps} />
        )}
      </div>
    </div>
  );
}

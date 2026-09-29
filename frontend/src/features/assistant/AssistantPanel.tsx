/**
 * The assistant panel (plan §26): a right-hand panel inside a domain dashboard, expandable to full
 * width, with the conversation list for that module. Not a separate chat app.
 *
 * URL state lives with the dashboard (`?assistant=open|full&c=:conversationId`). A conversation is
 * created with its first question, so none is left empty. Failure states: provider down (the
 * question is kept and can be asked again), the AI usage limit (with the provider's own reset
 * time, counted down), not configured, the assistant unreachable, sending too quickly, connection
 * needing reauthorisation, and a conversation that no longer exists.
 */
import { History, Maximize2, Minimize2, SquarePen, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router";

import { Alert, Button, Skeleton, Status } from "../../design-system";
import { ApiError } from "../../lib/api/client";
import styles from "./AssistantPanel.module.css";
import { Composer } from "./Composer";
import { ConversationList } from "./ConversationList";
import {
  isLimitReached,
  isStoredFailure,
  useAsk,
  useAssistantInfo,
  useConversation,
} from "./hooks";
import { PANEL_ID, type PanelMode } from "./panel";
import { Transcript } from "./Transcript";
import { clockTime, formatWait, useCountdown } from "./usage";

export interface AssistantPanelProps {
  workspaceId: string;
  connectionId: string;
  /** "Zoho Books" */
  system: string;
  organisation: string;
  /** "Finance" */
  domainName: string;
  mode: PanelMode;
  conversationId: string | null;
  onConversationChange: (id: string | null) => void;
  onModeChange: (mode: PanelMode | null) => void;
  needsReauth: boolean;
  canManage: boolean;
  connectionHref: string;
}

export default function AssistantPanel(props: AssistantPanelProps) {
  const { workspaceId, connectionId, system, organisation, mode, conversationId } = props;
  const { onConversationChange, onModeChange } = props;
  const info = useAssistantInfo(workspaceId, connectionId);
  const conversation = useConversation(workspaceId, connectionId, conversationId);
  const ask = useAsk(workspaceId, connectionId);
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState<ApiError | null>(null);
  const [showList, setShowList] = useState(false);
  const composer = useRef<HTMLTextAreaElement>(null);

  const name = info.data?.display_name ?? `${props.domainName} Assistant`;
  const status = info.data?.status;
  const unreachable = info.isError; // e.g. a server without the assistant routes: never "Not Found"
  const limited = status?.state === "limit_reached";
  const refreshInfo = info.refetch;
  const recheck = useCallback(() => void refreshInfo(), [refreshInfo]);
  const left = useCountdown(limited ? status.resets_in_seconds : null, info.dataUpdatedAt, recheck);
  const wait = left !== null && left > 0 ? formatWait(left) : null;
  // After a limit, the server reports "unconfirmed" until a real answer gets through: say so
  // rather than showing "Available".
  const [limitSeen, setLimitSeen] = useState(false);
  if (limited && !limitSeen) setLimitSeen(true);
  if (status?.state === "available" && limitSeen) setLimitSeen(false);
  const recheckPending = limitSeen && status?.state === "unconfirmed";
  const available = info.data?.available !== false && !unreachable && !limited;
  const full = mode === "full";
  const listVisible = full || showList;
  const missing =
    conversation.error instanceof ApiError && conversation.error.status === 404 && !ask.isPending;

  useEffect(() => {
    if (!info.isPending) composer.current?.focus({ preventScroll: true }); // disabled until info loads
  }, [info.isPending]);

  const submit = (text: string) => {
    const content = text.trim();
    if (!content || ask.isPending) return;
    setDraft("");
    setNotice(null);
    ask.mutate(
      { conversationId, content, onCreated: (id) => onConversationChange(id) },
      {
        onError: (error) => {
          if (!isStoredFailure(error)) setDraft((current) => current || content);
          setNotice(error instanceof ApiError ? error : null);
        },
      },
    );
  };

  const startNew = () => {
    onConversationChange(null);
    setShowList(false);
    setNotice(null);
    composer.current?.focus({ preventScroll: true });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    if (showList && !full) setShowList(false);
    else onModeChange(null);
  };

  const messages = conversationId ? (conversation.data?.messages ?? []) : [];
  const pendingQuestion = ask.isPending ? (ask.variables?.content ?? null) : null;
  const empty = !messages.length && !pendingQuestion;
  const loadingConversation = conversationId !== null && conversation.isPending && !ask.isPending;
  // A stored failure is shown in the transcript and the usage limit in its own alert; anything
  // else is a notice above the box.
  const shownNotice = notice && !isStoredFailure(notice) && !isLimitReached(notice) ? notice : null;
  const usage = unreachable ? (
    <Status tone="negative">Can't be reached</Status>
  ) : status?.state === "limit_reached" ? (
    <Status tone="warning">Usage limit reached</Status>
  ) : status?.state === "not_configured" ? (
    <Status tone="neutral">Not set up</Status>
  ) : status?.state === "available" ? (
    <Status tone="positive">Available</Status>
  ) : null; // unconfirmed: nothing claims availability until a real answer

  return (
    <aside
      id={PANEL_ID}
      className={styles.panel}
      data-mode={mode}
      aria-label={name}
      onKeyDown={onKeyDown}
    >
      <header className={styles.header}>
        <div className={styles.heading}>
          <h2 className={styles.title}>{name}</h2>
          <p className={styles.subtitle}>
            {organisation} · {system}
          </p>
          {usage ? <p className={styles.usage}>{usage}</p> : null}
        </div>
        <div className={styles.tools}>
          {!full ? (
            <button
              type="button"
              className={styles.iconButton}
              aria-label="Your conversations"
              aria-pressed={showList}
              title="Your conversations"
              onClick={() => setShowList((shown) => !shown)}
            >
              <History size={16} aria-hidden="true" />
            </button>
          ) : null}
          <button
            type="button"
            className={styles.iconButton}
            aria-label="New conversation"
            title="New conversation"
            onClick={startNew}
          >
            <SquarePen size={16} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={`${styles.iconButton} ${styles.expand}`}
            aria-label={full ? "Show beside the dashboard" : "Expand to full width"}
            title={full ? "Show beside the dashboard" : "Expand to full width"}
            onClick={() => onModeChange(full ? "open" : "full")}
          >
            {full ? (
              <Minimize2 size={16} aria-hidden="true" />
            ) : (
              <Maximize2 size={16} aria-hidden="true" />
            )}
          </button>
          <button
            type="button"
            className={styles.iconButton}
            aria-label={`Close ${name}`}
            title="Close"
            onClick={() => onModeChange(null)}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className={styles.body} data-list={listVisible || undefined}>
        {listVisible ? (
          <div className={styles.listColumn}>
            <ConversationList
              workspaceId={workspaceId}
              connectionId={connectionId}
              activeId={conversationId}
              onOpen={(id) => {
                onConversationChange(id);
                setShowList(false);
                setNotice(null);
              }}
              onDeleted={(id) => {
                if (id === conversationId) onConversationChange(null);
              }}
            />
          </div>
        ) : null}

        {!listVisible || full ? (
          <div className={styles.chat}>
            {props.needsReauth ? (
              <Alert
                tone="warning"
                action={
                  props.canManage ? <Link to={props.connectionHref}>Reconnect</Link> : undefined
                }
              >
                {system} needs reconnecting, so answers use figures up to the last refresh.
                {props.canManage ? "" : " Ask a workspace owner or admin to reconnect it."}
              </Alert>
            ) : null}
            {unreachable ? (
              <Alert
                tone="negative"
                action={
                  <Button size="sm" variant="secondary" onClick={recheck}>
                    Try again
                  </Button>
                }
              >
                The {name} can't be reached right now. Your dashboard is unaffected.
              </Alert>
            ) : limited ? (
              <Alert tone="warning" title="AI usage limit reached">
                {wait && left !== null ? (
                  <>
                    <span aria-hidden="true">Available again in {wait}.</span>
                    <span className="visually-hidden">
                      Available again at{" "}
                      {clockTime(info.dataUpdatedAt, status.resets_in_seconds ?? 0)}.
                    </span>
                  </>
                ) : (
                  "Try again shortly."
                )}{" "}
                Your dashboard data is unaffected.
              </Alert>
            ) : recheckPending ? (
              <Alert tone="info">
                The usage limit should have reset. Your next question will confirm it.
              </Alert>
            ) : info.data?.available === false ? (
              <Alert tone="info">
                The {name} isn't set up on this server yet. Your dashboard is unaffected.
              </Alert>
            ) : null}

            {info.isPending || loadingConversation ? (
              <div className={styles.loading} aria-busy="true">
                <Skeleton height={32} />
                <Skeleton width="80%" />
                <Skeleton width="60%" />
              </div>
            ) : missing ? (
              <Alert
                tone="info"
                action={
                  <Button size="sm" variant="ghost" onClick={startNew}>
                    Start a new one
                  </Button>
                }
              >
                This conversation is no longer available.
              </Alert>
            ) : empty ? (
              available ? (
                <div className={styles.intro}>
                  <p>
                    Ask about {organisation}'s {props.domainName.toLowerCase()} in {system}. Answers
                    use the same figures as this dashboard.
                  </p>
                  {info.data?.suggested_questions.length ? (
                    <ul className={styles.suggestions} aria-label="Suggested questions">
                      {info.data.suggested_questions.map((question) => (
                        <li key={question}>
                          <button
                            type="button"
                            className={styles.suggestion}
                            onClick={() => submit(question)}
                          >
                            {question}
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null
            ) : (
              <Transcript
                assistantName={name}
                system={system}
                messages={messages}
                pendingQuestion={pendingQuestion}
                onAskAgain={submit}
              />
            )}

            {shownNotice ? (
              <Alert tone={shownNotice.status === 429 ? "info" : "warning"}>
                {shownNotice.detail}
              </Alert>
            ) : null}
            <Composer
              ref={composer}
              label={`Ask the ${name}`}
              value={draft}
              onChange={setDraft}
              onSubmit={submit}
              pending={ask.isPending}
              disabled={!available || info.isPending}
              placeholder={wait ? `Available again in ${wait}` : undefined}
            />
          </div>
        ) : null}
      </div>
    </aside>
  );
}

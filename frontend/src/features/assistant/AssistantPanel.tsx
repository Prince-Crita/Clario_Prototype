/**
 * The Finance Assistant conversation (plan §26, §27.11): the centre of the Clario AI page, with
 * the conversation list for that module behind "Your conversations". Never a popup.
 *
 * URL state lives with the page (`/finance/clario?c=:conversationId&q=…`). A conversation is
 * created with its first question, so none is left empty. Failure states: provider down (the
 * question is kept and can be asked again), the AI usage limit (with the provider's own reset
 * time, counted down), not configured, the assistant unreachable, sending too quickly, connection
 * needing reauthorisation, and a conversation that no longer exists.
 */
import { History, SquarePen } from "lucide-react";
import {
  useCallback,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
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
import { PANEL_ID } from "./panel";
import { ApertureMark } from "../../brand/ApertureMark";
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
  conversationId: string | null;
  /** A question to place in the box, ready to review and send (e.g. from a signal). */
  prefill?: string | null | undefined;
  /** Questions to start an empty conversation with (else the server's suggestions). */
  suggestions?: string[] | undefined;
  /** Send the prefill at once: the user typed it into the Ask Clario command line. */
  autoSend?: boolean | undefined;
  onConversationChange: (id: string | null) => void;
  needsReauth: boolean;
  canManage: boolean;
  connectionHref: string;
}

export default function AssistantPanel(props: AssistantPanelProps) {
  const { workspaceId, connectionId, system, organisation, conversationId } = props;
  const { onConversationChange } = props;
  const info = useAssistantInfo(workspaceId, connectionId);
  const conversation = useConversation(workspaceId, connectionId, conversationId);
  const ask = useAsk(workspaceId, connectionId);
  const [draft, setDraft] = useState(props.prefill ?? "");
  // A new prefill (e.g. "Ask Clario" on another signal) replaces the box's text; never auto-sent.
  const [placed, setPlaced] = useState(props.prefill ?? null);
  if (props.prefill && props.prefill !== placed) {
    setPlaced(props.prefill);
    setDraft(props.prefill);
  }
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
  const listVisible = showList;
  const missing =
    conversation.error instanceof ApiError && conversation.error.status === 404 && !ask.isPending;

  // Clario AI is for asking: the box has focus once it is ready (disabled until info loads).
  useEffect(() => {
    if (!info.isPending) composer.current?.focus({ preventScroll: true });
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

  // A question submitted from a page's Ask box is asked once, when Clario is ready.
  const sent = useRef<string | null>(null);
  const sendNow =
    props.autoSend && props.prefill && available && !info.isPending ? props.prefill : null;
  const sendPrefill = useEffectEvent((question: string) => submit(question));
  useEffect(() => {
    if (!sendNow || sent.current === sendNow) return;
    sent.current = sendNow;
    sendPrefill(sendNow);
  }, [sendNow]);

  const startNew = () => {
    onConversationChange(null);
    setShowList(false);
    setNotice(null);
    composer.current?.focus({ preventScroll: true });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Escape") return;
    if (!showList) return;
    event.stopPropagation();
    setShowList(false);
  };

  const suggestions = props.suggestions ?? info.data?.suggested_questions ?? [];
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
    <section
      id={PANEL_ID}
      className={styles.panel}
      data-mode="page"
      aria-label={name}
      onKeyDown={onKeyDown}
    >
      <header className={styles.header}>
        <div className={styles.heading}>
          <span className={styles.brandMark} aria-hidden="true">
            <ApertureMark size={22} tone="inverse" />
          </span>
          <div className={styles.headingText}>
            <h2 className={styles.title}>Ask Clario</h2>
            <p className={styles.tagline}>Understand your business, not just your numbers.</p>
          </div>
        </div>
        <div className={styles.tools}>
          <button
            type="button"
            className={styles.textButton}
            aria-label="Your conversations"
            aria-pressed={showList}
            title="Your conversations"
            onClick={() => setShowList((shown) => !shown)}
          >
            <History size={16} aria-hidden="true" />
            <span>History</span>
          </button>
          <button
            type="button"
            className={styles.textButton}
            aria-label="New conversation"
            title="New conversation"
            onClick={startNew}
          >
            <SquarePen size={16} aria-hidden="true" />
            <span>New</span>
          </button>
        </div>
      </header>

      <div className={styles.context}>
        <p className={styles.subtitle}>
          {name} · {organisation} · {system}
        </p>
        {usage ? <p className={styles.usage}>{usage}</p> : null}
      </div>
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

        {!listVisible ? (
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
                    Ask about {organisation}'s {props.domainName.toLowerCase()} in {system}, in
                    plain words: performance, cash, customers, costs or what to focus on. Answers
                    use the same figures as your reports and show where they come from.
                  </p>
                  {suggestions.length ? (
                    <ul className={styles.suggestions} aria-label="Suggested questions">
                      {suggestions.map((question) => (
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
    </section>
  );
}

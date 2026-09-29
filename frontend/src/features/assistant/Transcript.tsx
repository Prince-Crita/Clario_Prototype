/**
 * The conversation (plan §26): each question, then its answer and a source line
 * ("Based on Receivables · data as of 25 Sept, 3:56 pm"). Answers are a markdown subset with no raw
 * HTML and no links; figures are shown exactly as the server wrote them (never re-formatted).
 */
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";

import { Button } from "../../design-system";
import type { ChatMessage } from "../../lib/api/types";
import { stampLabel } from "../finance/format";
import styles from "./AssistantPanel.module.css";

const ALLOWED = ["p", "strong", "em", "ul", "ol", "li", "code", "br"];

export function Answer({ text }: { text: string }) {
  return (
    <div className={styles.prose}>
      <Markdown allowedElements={ALLOWED} unwrapDisallowed skipHtml>
        {text}
      </Markdown>
    </div>
  );
}

export function SourceLine({ sources, asOf }: { sources: string[]; asOf: string | null }) {
  if (!sources.length) return null;
  return (
    <p className={styles.source}>
      Based on {sources.join(", ")}
      {asOf ? ` · data as of ${stampLabel(asOf)}` : ""}
    </p>
  );
}

/** Honest progress: answers are not streamed yet, so this names the system being read. */
function Progress({ system }: { system: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), 10_000);
    return () => window.clearTimeout(timer);
  }, []);
  return (
    <p className={styles.progress} role="status">
      <span className={styles.pulse} aria-hidden="true" />
      {slow
        ? "Still working. Answers take longer when the assistant is busy."
        : `Checking ${system}…`}
    </p>
  );
}

interface TranscriptProps {
  assistantName: string;
  system: string;
  messages: ChatMessage[];
  pendingQuestion: string | null;
  onAskAgain: (question: string) => void;
}

export function Transcript(props: TranscriptProps) {
  const { assistantName, system, messages, pendingQuestion, onAskAgain } = props;
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages.length, pendingQuestion]);

  const lastFailed = messages.at(-1)?.status === "failed" ? messages.length - 1 : -1;
  return (
    <div className={styles.transcript} role="log" aria-label="Conversation">
      {messages.map((message, index) =>
        message.role === "user" ? (
          <div key={message.id} className={styles.question}>
            <span className="visually-hidden">You asked: </span>
            {message.content}
          </div>
        ) : message.status === "failed" ? (
          <div key={message.id} className={styles.failed}>
            <p>This question wasn't answered: the assistant was temporarily unavailable.</p>
            {index === lastFailed && !pendingQuestion && messages[index - 1]?.role === "user" ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => onAskAgain(messages[index - 1]?.content ?? "")}
              >
                Ask again
              </Button>
            ) : null}
          </div>
        ) : (
          <div key={message.id} className={styles.answer}>
            <span className="visually-hidden">{assistantName}: </span>
            <Answer text={message.content} />
            <SourceLine sources={message.sources ?? []} asOf={message.as_of ?? null} />
          </div>
        ),
      )}
      {pendingQuestion ? (
        <>
          <div className={styles.question}>
            <span className="visually-hidden">You asked: </span>
            {pendingQuestion}
          </div>
          <Progress system={system} />
        </>
      ) : null}
      <div ref={end} />
    </div>
  );
}

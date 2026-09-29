/** Your earlier conversations with this assistant (private to you), newest first. */
import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Alert, Button, Skeleton } from "../../design-system";
import { ApiError } from "../../lib/api/client";
import { stampLabel } from "../finance/format";
import styles from "./AssistantPanel.module.css";
import { useConversations, useDeleteConversation } from "./hooks";

interface ConversationListProps {
  workspaceId: string;
  connectionId: string;
  activeId: string | null;
  onOpen: (id: string) => void;
  onDeleted: (id: string) => void;
}

export function ConversationList(props: ConversationListProps) {
  const { workspaceId, connectionId, activeId, onOpen, onDeleted } = props;
  const list = useConversations(workspaceId, connectionId, true);
  const remove = useDeleteConversation(workspaceId, connectionId);
  const [confirming, setConfirming] = useState<string | null>(null);

  if (list.isPending) {
    return (
      <div className={styles.listLoading} aria-busy="true">
        <Skeleton height={36} />
        <Skeleton height={36} />
        <Skeleton height={36} />
      </div>
    );
  }
  if (list.isError) {
    return <Alert tone="negative">Your conversations couldn't be loaded. Try again shortly.</Alert>;
  }
  if (!list.data.length) {
    return <p className={styles.listEmpty}>No conversations yet. Questions you ask appear here.</p>;
  }
  const failure = remove.error instanceof ApiError ? remove.error.detail : null;

  return (
    <nav aria-label="Your conversations" className={styles.list}>
      {failure ? <Alert tone="negative">{failure}</Alert> : null}
      <ul>
        {list.data.map((conversation) => {
          const title = conversation.title ?? "Untitled conversation";
          const when = conversation.last_message_at ?? conversation.created_at;
          return (
            <li key={conversation.id} className={styles.listItem}>
              {confirming === conversation.id ? (
                <div className={styles.confirm} role="group" aria-label={`Delete “${title}”`}>
                  <span>Delete this conversation?</span>
                  <Button
                    size="sm"
                    variant="danger"
                    pending={remove.isPending}
                    pendingLabel="Deleting…"
                    onClick={() =>
                      remove.mutate(conversation.id, {
                        onSuccess: () => {
                          setConfirming(null);
                          onDeleted(conversation.id);
                        },
                      })
                    }
                  >
                    Delete
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>
                    Cancel
                  </Button>
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    className={styles.listRow}
                    aria-current={conversation.id === activeId ? "true" : undefined}
                    onClick={() => onOpen(conversation.id)}
                  >
                    <span className={styles.listTitle}>{title}</span>
                    <span className={styles.listDate}>{stampLabel(when)}</span>
                  </button>
                  <button
                    type="button"
                    className={styles.iconButton}
                    aria-label={`Delete “${title}”`}
                    title="Delete"
                    onClick={() => setConfirming(conversation.id)}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </button>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/**
 * Server state for a connection's assistant (plan §26). The panel is domain-neutral: the server
 * picks the assistant from the connection, so Inventory or CRM dashboards reuse it unchanged.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import { ApiError, apiFetch } from "../../lib/api/client";
import type {
  AssistantInfo,
  ChatReply,
  ConversationDetail,
  ConversationSummary,
} from "../../lib/api/types";

const base = (workspaceId: string, connectionId: string) =>
  `/workspaces/${workspaceId}/connections/${connectionId}/assistant`;
export const assistantKey = (workspaceId: string, connectionId: string) =>
  ["workspace", workspaceId, "connections", connectionId, "assistant"] as const;
const listKey = (w: string, c: string) => [...assistantKey(w, c), "conversations"] as const;
const detailKey = (w: string, c: string, id: string) =>
  [...assistantKey(w, c), "conversation", id] as const;

export function useAssistantInfo(workspaceId: string, connectionId: string) {
  return useQuery({
    queryKey: [...assistantKey(workspaceId, connectionId), "info"],
    queryFn: () => apiFetch<AssistantInfo>(base(workspaceId, connectionId)),
  });
}

export function useConversations(workspaceId: string, connectionId: string, enabled: boolean) {
  return useQuery({
    queryKey: listKey(workspaceId, connectionId),
    queryFn: async () =>
      (
        await apiFetch<{ conversations: ConversationSummary[] }>(
          `${base(workspaceId, connectionId)}/conversations`,
        )
      ).conversations,
    enabled,
  });
}

export function useConversation(workspaceId: string, connectionId: string, id: string | null) {
  return useQuery({
    queryKey: detailKey(workspaceId, connectionId, id ?? ""),
    queryFn: () =>
      apiFetch<ConversationDetail>(`${base(workspaceId, connectionId)}/conversations/${id}`),
    enabled: id !== null,
  });
}

export interface AskVariables {
  conversationId: string | null;
  content: string;
  /** Called once a new conversation exists (before its first answer arrives). */
  onCreated?: (id: string) => void;
}

/** The AI provider's usage limit is reached (the reply carries the reset time). */
export const LIMIT_REACHED = "assistant.limit_reached";
export const isLimitReached = (error: unknown): boolean =>
  error instanceof ApiError && error.code === LIMIT_REACHED;

/** A question that failed but was stored (the server keeps it with a failed answer). */
export const isStoredFailure = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 503 && error.code !== "assistant.not_configured";

/** Ask a question, starting a conversation first when there is none (so none is left empty). */
export function useAsk(workspaceId: string, connectionId: string) {
  const queryClient = useQueryClient();
  const root = base(workspaceId, connectionId);
  const created = useRef<string | null>(null);
  return useMutation({
    mutationFn: async ({ conversationId, content, onCreated }: AskVariables) => {
      let id = conversationId;
      created.current = null;
      if (id === null) {
        const summary = await apiFetch<ConversationSummary>(`${root}/conversations`, {
          method: "POST",
        });
        id = summary.id;
        created.current = id;
        queryClient.setQueryData<ConversationDetail>(detailKey(workspaceId, connectionId, id), {
          ...summary,
          messages: [],
        });
        onCreated?.(id);
      }
      const reply = await apiFetch<ChatReply>(`${root}/conversations/${id}/messages`, {
        method: "POST",
        body: { content },
      });
      return { id, reply };
    },
    onSuccess: async ({ id, reply }) => {
      const key = detailKey(workspaceId, connectionId, id);
      await queryClient.cancelQueries({ queryKey: key }); // an older read must not win
      queryClient.setQueryData<ConversationDetail>(key, (old) => ({
        ...reply.conversation,
        messages: [...(old?.messages ?? []), reply.user_message, reply.assistant_message],
      }));
      void queryClient.invalidateQueries({ queryKey: listKey(workspaceId, connectionId) });
    },
    onError: (error, { conversationId }) => {
      if (isLimitReached(error)) {
        // The server now knows the reset time: reload the status line from it.
        void queryClient.invalidateQueries({
          queryKey: [...assistantKey(workspaceId, connectionId), "info"],
        });
      }
      const id = conversationId ?? created.current;
      if (id && isStoredFailure(error)) {
        void queryClient.invalidateQueries({ queryKey: detailKey(workspaceId, connectionId, id) });
        void queryClient.invalidateQueries({ queryKey: listKey(workspaceId, connectionId) });
      }
    },
  });
}

export function useDeleteConversation(workspaceId: string, connectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<undefined>(`${base(workspaceId, connectionId)}/conversations/${id}`, {
        method: "DELETE",
      }),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: detailKey(workspaceId, connectionId, id) });
      void queryClient.invalidateQueries({ queryKey: listKey(workspaceId, connectionId) });
    },
  });
}

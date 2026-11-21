import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import { chatApi, MESSAGE_PAGE_SIZE } from "@/features/chat/api";
import { chatKeys } from "@/features/chat/query-keys";
import {
  addLocal,
  combine,
  EMPTY_THREAD,
  maxSeq,
  mergeMessages,
  mergePage,
  minSeq,
  removeLocal,
  setLocalState,
  type Thread,
} from "@/features/chat/thread";
import type {
  Attachment,
  ConversationListParams,
  ConversationSummary,
  Paged,
} from "@/features/chat/types";
import { toUserFacingError } from "@/lib/error-handling";
import { useRealtimeSend } from "@/lib/realtime/provider";

/** Lists refresh on a slow timer as a safety net; real-time events refresh them sooner. */
const LIST_SAFETY_REFRESH_MS = 60_000;

export function useConversations(params: ConversationListParams) {
  return useQuery({
    queryKey: chatKeys.list(params),
    queryFn: ({ signal }) => chatApi.list(params, signal),
    placeholderData: keepPreviousData,
    refetchInterval: LIST_SAFETY_REFRESH_MS,
  });
}

export function useConversation(id: string) {
  return useQuery({
    queryKey: chatKeys.conversation(id),
    queryFn: ({ signal }) => chatApi.get(id, signal),
  });
}

export function useUnreadTotals(enabled = true) {
  return useQuery({
    queryKey: chatKeys.unread(),
    queryFn: ({ signal }) => chatApi.unread(signal),
    enabled,
    refetchInterval: LIST_SAFETY_REFRESH_MS,
  });
}

/**
 * The message history of one conversation. The first load fetches the latest page. Every
 * refetch after that (reconnect, gap, window focus) merges instead of replacing: it reloads the
 * latest page (fresh statuses) and walks forward from the last known seq if more than a page
 * was missed. Older pages and unsent local messages are never lost.
 */
export function useThread(conversationId: string) {
  const queryClient = useQueryClient();
  const key = chatKeys.messages(conversationId);
  return useQuery({
    queryKey: key,
    queryFn: async ({ signal }): Promise<Thread> => {
      // Read the cache after each response, not before the request: a message pushed or sent
      // while the request was in flight must survive the merge.
      const current = () => queryClient.getQueryData<Thread>(key);
      const known = maxSeq(current());
      const latest = await chatApi.messages(conversationId, {}, signal);
      let thread = mergePage(current(), latest);
      const oldestLatest = latest.messages[0]?.seq;
      if (known > 0 && oldestLatest !== undefined && oldestLatest > known + 1) {
        // More than a page was missed: walk forward from what we had.
        let after = known;
        for (;;) {
          const page = await chatApi.messages(conversationId, { after_seq: after }, signal);
          thread = mergePage(thread, page);
          const next = maxSeq(thread);
          if (page.messages.length < MESSAGE_PAGE_SIZE || next >= oldestLatest) break;
          after = next;
        }
      }
      return combine(thread, current());
    },
    // Real-time events keep it current; refetching on focus is the fallback.
    staleTime: 30_000,
  });
}

export function useLoadOlder(conversationId: string) {
  const queryClient = useQueryClient();
  const key = chatKeys.messages(conversationId);
  return useMutation({
    mutationFn: async () => {
      const before = minSeq(queryClient.getQueryData<Thread>(key));
      if (before === null) return null;
      return chatApi.messages(conversationId, { before_seq: before });
    },
    onSuccess: (page) => {
      if (!page) return;
      queryClient.setQueryData<Thread>(key, (current) => mergePage(current, page, true));
    },
  });
}

function refreshLists(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
  void queryClient.invalidateQueries({ queryKey: chatKeys.unread() });
}

interface SendVariables {
  clientMessageId: string;
  body: string | null;
  attachments: Attachment[];
}

function newClientId(): string {
  return crypto.randomUUID();
}

/**
 * Optimistic send. The message shows at once as "Sending"; a failure keeps it on screen as
 * "Failed" with a retry that reuses the same client_message_id, so the server stores it once
 * no matter how many attempts reach it.
 */
export function useSendMessage(conversationId: string, senderId: string) {
  const queryClient = useQueryClient();
  const key = chatKeys.messages(conversationId);
  const mutation = useMutation({
    mutationFn: (variables: SendVariables) =>
      chatApi.send(conversationId, {
        client_message_id: variables.clientMessageId,
        ...(variables.body ? { body: variables.body } : {}),
        ...(variables.attachments.length
          ? { attachment_ids: variables.attachments.map((a) => a.id) }
          : {}),
      }),
    onMutate: (variables) => {
      queryClient.setQueryData<Thread>(key, (current) => {
        const thread = current ?? EMPTY_THREAD;
        const exists = thread.messages.some(
          (m) => m.local && m.client_message_id === variables.clientMessageId,
        );
        return exists
          ? setLocalState(thread, variables.clientMessageId, "pending")
          : addLocal(thread, {
              clientMessageId: variables.clientMessageId,
              conversationId,
              senderId,
              body: variables.body,
              attachments: variables.attachments,
              createdAt: new Date().toISOString(),
            });
      });
    },
    onSuccess: (message) => {
      queryClient.setQueryData<Thread>(key, (current) =>
        mergeMessages(current ?? EMPTY_THREAD, [message]),
      );
      refreshLists(queryClient);
    },
    onError: (error, variables) => {
      queryClient.setQueryData<Thread>(key, (current) =>
        setLocalState(
          current ?? EMPTY_THREAD,
          variables.clientMessageId,
          "failed",
          toUserFacingError(error).message,
        ),
      );
    },
  });

  const send = useCallback(
    (body: string, attachments: Attachment[] = []) => {
      const text = body.trim();
      if (!text && attachments.length === 0) return;
      mutation.mutate({ clientMessageId: newClientId(), body: text || null, attachments });
    },
    [mutation],
  );

  const retry = useCallback(
    (clientMessageId: string) => {
      const local = queryClient
        .getQueryData<Thread>(key)
        ?.messages.find((m) => m.local && m.client_message_id === clientMessageId);
      if (!local) return;
      mutation.mutate({ clientMessageId, body: local.body, attachments: local.attachments });
    },
    [mutation, queryClient, key],
  );

  const discard = useCallback(
    (clientMessageId: string) =>
      queryClient.setQueryData<Thread>(key, (current) =>
        removeLocal(current ?? EMPTY_THREAD, clientMessageId),
      ),
    [queryClient, key],
  );

  return { send, retry, discard, isSending: mutation.isPending };
}

export function useMarkRead(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (upToSeq: number) => chatApi.markRead(conversationId, upToSeq),
    onSuccess: (state) => {
      queryClient.setQueryData<Thread>(chatKeys.messages(conversationId), (current) =>
        current
          ? { ...current, lastReadSeq: Math.max(current.lastReadSeq, state.last_read_seq) }
          : current,
      );
      queryClient.setQueriesData<Paged<ConversationSummary>>(
        { queryKey: chatKeys.lists() },
        (page) =>
          page
            ? {
                ...page,
                data: page.data.map((c) =>
                  c.id === conversationId ? { ...c, unread_count: state.unread_count } : c,
                ),
              }
            : page,
      );
      void queryClient.invalidateQueries({ queryKey: chatKeys.unread() });
    },
  });
}

export function useSetArchived(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (archived: boolean) => chatApi.setArchived(conversationId, archived),
    onSuccess: (summary) => {
      queryClient.setQueryData(chatKeys.conversation(conversationId), summary);
      refreshLists(queryClient);
    },
  });
}

export function useOpenConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => chatApi.open(userId),
    onSuccess: (summary) => queryClient.setQueryData(chatKeys.conversation(summary.id), summary),
  });
}

export function useUploadAttachment(conversationId: string) {
  return useMutation({ mutationFn: (file: File) => chatApi.upload(conversationId, file) });
}

const TYPING_EVERY_MS = 2000;

/** Throttled typing signal over the socket. Silently does nothing while disconnected. */
export function useTypingSignal(conversationId: string): () => void {
  const send = useRealtimeSend();
  const last = useRef(0);
  return useCallback(() => {
    const now = Date.now();
    if (now - last.current < TYPING_EVERY_MS) return;
    last.current = now;
    send({ type: "typing", conversation_id: conversationId });
  }, [send, conversationId]);
}

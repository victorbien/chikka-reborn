import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import { smsApi } from "@/features/sms/api";
import { smsKeys } from "@/features/sms/query-keys";
import type { SmsMessage, SmsTarget, SmsThread } from "@/features/sms/types";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const LIST_SAFETY_REFRESH_MS = 60_000;
export const QUOTE_DEBOUNCE_MS = 300;

export function useSmsStatus() {
  return useQuery({
    queryKey: smsKeys.status(),
    queryFn: ({ signal }) => smsApi.status(signal),
    staleTime: 30_000,
  });
}

export function useCountries() {
  return useQuery({
    queryKey: smsKeys.countries(),
    queryFn: ({ signal }) => smsApi.countries(signal),
    staleTime: 5 * 60_000,
  });
}

export function useSmsConversations() {
  return useQuery({
    queryKey: smsKeys.lists(),
    queryFn: ({ signal }) => smsApi.conversations(signal),
    refetchInterval: LIST_SAFETY_REFRESH_MS,
  });
}

export function useSmsThread(conversationId: string) {
  return useQuery({
    queryKey: smsKeys.messages(conversationId),
    queryFn: ({ signal }) => smsApi.messages(conversationId, undefined, signal),
    staleTime: 30_000,
  });
}

/** Insert or replace by id; a stale status never overwrites a newer one. */
export function upsertMessage(thread: SmsThread | undefined, message: SmsMessage): SmsThread {
  const current = thread ?? { messages: [], has_more_before: false, last_read_seq: 0 };
  const existing = current.messages.find((m) => m.id === message.id);
  if (existing && existing.status_version > message.status_version) return current;
  const rest = current.messages.filter((m) => m.id !== message.id);
  return { ...current, messages: [...rest, message].sort((a, b) => a.seq - b.seq) };
}

export function useLoadOlderSms(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const thread = queryClient.getQueryData<SmsThread>(smsKeys.messages(conversationId));
      const before = thread?.messages[0]?.seq;
      return before === undefined ? null : smsApi.messages(conversationId, before);
    },
    onSuccess: (page) => {
      if (!page) return;
      queryClient.setQueryData<SmsThread>(smsKeys.messages(conversationId), (current) => {
        let merged: SmsThread = current ?? {
          messages: [],
          has_more_before: false,
          last_read_seq: 0,
        };
        for (const message of page.messages) merged = upsertMessage(merged, message);
        return { ...merged, has_more_before: page.has_more_before };
      });
    },
  });
}

/** The server's estimate for the message as typed. Debounced; the previous answer stays on
 *  screen while a new one loads, so the panel does not flicker. */
export function useQuote(target: SmsTarget | null, body: string) {
  const debounced = useDebouncedValue(body, QUOTE_DEBOUNCE_MS);
  const stableTarget = useDebouncedValue(target, QUOTE_DEBOUNCE_MS);
  return useQuery({
    queryKey: smsKeys.quote(stableTarget, debounced),
    queryFn: ({ signal }) => smsApi.quote(stableTarget as SmsTarget, debounced, signal),
    enabled: stableTarget !== null,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useSetConsent(target: SmsTarget | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (decision: "granted" | "withdrawn") => {
      if (!target) throw new Error("No recipient");
      return smsApi.setConsent(target, decision);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...smsKeys.all, "quote"] });
    },
  });
}

function refresh(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: smsKeys.lists() });
}

/**
 * One idempotency key per user intent: the same recipient and text reuse the key, so a double
 * click or a retry after a dropped connection can never send twice. Changing the text starts a
 * new intent with a new key.
 */
function useIntentKey() {
  const ref = useRef<{ signature: string; key: string } | null>(null);
  const keyFor = useCallback((signature: string) => {
    if (ref.current?.signature !== signature) {
      ref.current = { signature, key: crypto.randomUUID() };
    }
    return ref.current.key;
  }, []);
  const clear = useCallback(() => {
    ref.current = null;
  }, []);
  return { keyFor, clear };
}

export function useSendSms(target: SmsTarget | null) {
  const queryClient = useQueryClient();
  const intent = useIntentKey();
  return useMutation({
    mutationFn: (body: string) => {
      if (!target) throw new Error("No recipient");
      return smsApi.send(target, body, intent.keyFor(JSON.stringify([target, body])));
    },
    onSuccess: (message) => {
      intent.clear();
      queryClient.setQueryData<SmsThread>(smsKeys.messages(message.conversation_id), (current) =>
        current ? upsertMessage(current, message) : current,
      );
      refresh(queryClient);
    },
  });
}

export function useRetrySms() {
  const queryClient = useQueryClient();
  const intent = useIntentKey();
  return useMutation({
    mutationFn: (messageId: string) => smsApi.retry(messageId, intent.keyFor(messageId)),
    onSuccess: (message) => {
      intent.clear();
      queryClient.setQueryData<SmsThread>(smsKeys.messages(message.conversation_id), (current) =>
        current ? upsertMessage(current, message) : current,
      );
      refresh(queryClient);
    },
  });
}

export function useMarkSmsRead(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (upToSeq: number) => smsApi.markRead(conversationId, upToSeq),
    onSuccess: (state) => {
      queryClient.setQueryData<SmsThread>(smsKeys.messages(conversationId), (current) =>
        current
          ? { ...current, last_read_seq: Math.max(current.last_read_seq, state.last_read_seq) }
          : current,
      );
      refresh(queryClient);
    },
  });
}

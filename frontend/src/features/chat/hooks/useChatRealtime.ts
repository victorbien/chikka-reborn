import { useQueryClient } from "@tanstack/react-query";
import { chatKeys } from "@/features/chat/query-keys";
import { applyStatus, isGap, mergeMessages, type Thread } from "@/features/chat/thread";
import { typingStore } from "@/features/chat/typing-store";
import type { ServerMessage, StatusChange } from "@/features/chat/types";
import type { ServerEvent } from "@/lib/realtime/client";
import { useRealtimeEvents, useRealtimeSend } from "@/lib/realtime/provider";

function isMessage(value: unknown): value is ServerMessage {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ServerMessage).id === "string" &&
    typeof (value as ServerMessage).seq === "number" &&
    typeof (value as ServerMessage).conversation_id === "string"
  );
}

function isStatusChange(value: unknown): value is StatusChange {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as StatusChange).message_id === "string" &&
    typeof (value as StatusChange).status_version === "number"
  );
}

/**
 * Applies server events to the Query cache (no parallel store). Mounted once in the signed-in
 * layout so messages are received, and acknowledged, on every page.
 *
 * - `ready` (connect or reconnect): everything chat-related is resynced from REST.
 * - `message.created`: merged into the open thread; a jump in seq triggers a resync. Incoming
 *   messages are acknowledged, which is what lets the sender see "Delivered". The ack says the
 *   app received it, never that the person read it.
 */
export function useChatRealtime(): void {
  const queryClient = useQueryClient();
  const send = useRealtimeSend();

  useRealtimeEvents((event: ServerEvent) => {
    const data = (event.data ?? {}) as Record<string, unknown>;
    switch (event.type) {
      case "ready":
        void queryClient.invalidateQueries({ queryKey: chatKeys.all });
        return;
      case "message.created": {
        const message = data.message;
        if (!isMessage(message)) return;
        const key = chatKeys.messages(message.conversation_id);
        const thread = queryClient.getQueryData<Thread>(key);
        if (thread) {
          const gap = isGap(thread, message.seq);
          queryClient.setQueryData<Thread>(key, mergeMessages(thread, [message]));
          if (gap) void queryClient.invalidateQueries({ queryKey: key });
        }
        if (!message.is_mine) {
          typingStore.clear(message.conversation_id);
          send({ type: "ack", message_ids: [message.id] });
        }
        void queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
        void queryClient.invalidateQueries({ queryKey: chatKeys.unread() });
        return;
      }
      case "message.status_changed": {
        if (!isStatusChange(data)) return;
        queryClient.setQueryData<Thread>(chatKeys.messages(data.conversation_id), (current) =>
          current ? applyStatus(current, data) : current,
        );
        void queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
        return;
      }
      case "conversation.read":
      case "conversation.updated":
        void queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
        void queryClient.invalidateQueries({ queryKey: chatKeys.unread() });
        if (event.conversation_id) {
          void queryClient.invalidateQueries({
            queryKey: chatKeys.conversation(event.conversation_id),
          });
        }
        return;
      case "typing":
        if (event.conversation_id && typeof data.user_id === "string") {
          typingStore.set(event.conversation_id, data.user_id);
        }
        return;
      default:
        return;
    }
  });
}

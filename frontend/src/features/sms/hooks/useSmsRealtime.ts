import { useQueryClient } from "@tanstack/react-query";
import { upsertMessage } from "@/features/sms/hooks/useSms";
import { smsKeys } from "@/features/sms/query-keys";
import type { SmsMessage, SmsThread } from "@/features/sms/types";
import type { ServerEvent } from "@/lib/realtime/client";
import { useRealtimeEvents } from "@/lib/realtime/provider";

function isSmsMessage(value: unknown): value is SmsMessage {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as SmsMessage).id === "string" &&
    typeof (value as SmsMessage).seq === "number" &&
    typeof (value as SmsMessage).status_version === "number"
  );
}

/** Applies SMS events to the Query cache. Status updates always arrive through here or a REST
 *  refetch; nothing in the UI invents "delivered". */
export function useSmsRealtime(): void {
  const queryClient = useQueryClient();
  useRealtimeEvents((event: ServerEvent) => {
    const data = (event.data ?? {}) as Record<string, unknown>;
    switch (event.type) {
      case "ready":
        void queryClient.invalidateQueries({ queryKey: smsKeys.all });
        return;
      case "sms.message.created":
      case "sms.message.updated": {
        const message = data.message;
        if (!isSmsMessage(message)) return;
        queryClient.setQueryData<SmsThread>(smsKeys.messages(message.conversation_id), (current) =>
          current ? upsertMessage(current, message) : current,
        );
        void queryClient.invalidateQueries({ queryKey: smsKeys.lists() });
        return;
      }
      case "sms.conversation.read":
        void queryClient.invalidateQueries({ queryKey: smsKeys.lists() });
        return;
      default:
        return;
    }
  });
}

import { useChatRealtime } from "@/features/chat/hooks/useChatRealtime";
import { useSmsRealtime } from "@/features/sms/hooks/useSmsRealtime";

/** Renders nothing. Keeps the chat cache in step with real-time events on every page. */
export function ChatRealtimeBridge() {
  useChatRealtime();
  useSmsRealtime();
  return null;
}

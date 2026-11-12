import { useChatRealtime } from "@/features/chat/hooks/useChatRealtime";

/** Renders nothing. Keeps the chat cache in step with real-time events on every page. */
export function ChatRealtimeBridge() {
  useChatRealtime();
  return null;
}

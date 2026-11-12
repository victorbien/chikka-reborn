import type { ConversationListParams } from "@/features/chat/types";

export const chatKeys = {
  all: ["chat"] as const,
  lists: () => [...chatKeys.all, "list"] as const,
  list: (params: ConversationListParams) => [...chatKeys.lists(), params] as const,
  conversation: (id: string) => [...chatKeys.all, "conversation", id] as const,
  messagesAll: () => [...chatKeys.all, "messages"] as const,
  messages: (id: string) => [...chatKeys.messagesAll(), id] as const,
  unread: () => [...chatKeys.all, "unread"] as const,
};

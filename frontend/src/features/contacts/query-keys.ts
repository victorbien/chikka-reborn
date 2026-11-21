import type { ContactListParams } from "@/features/contacts/types";

export const contactKeys = {
  all: ["contacts"] as const,
  lists: () => [...contactKeys.all, "list"] as const,
  list: (params: ContactListParams) => [...contactKeys.lists(), params] as const,
  detail: (id: string) => [...contactKeys.all, "detail", id] as const,
  search: (query: string) => [...contactKeys.all, "search", query] as const,
  requests: (direction: "incoming" | "outgoing", page: number) =>
    [...contactKeys.all, "requests", direction, page] as const,
  requestsAll: () => [...contactKeys.all, "requests"] as const,
  groups: () => [...contactKeys.all, "groups"] as const,
  blocks: () => [...contactKeys.all, "blocks"] as const,
  recent: () => [...contactKeys.all, "recent"] as const,
  recentConversations: () => [...contactKeys.all, "recent-conversations"] as const,
};

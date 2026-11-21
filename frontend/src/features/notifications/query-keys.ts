export const notificationKeys = {
  all: ["notifications"] as const,
  unread: () => [...notificationKeys.all, "unread"] as const,
  feed: (page: number, unreadOnly: boolean) =>
    [...notificationKeys.all, "feed", page, unreadOnly] as const,
  preferences: () => [...notificationKeys.all, "preferences"] as const,
};

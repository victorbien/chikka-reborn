export const authKeys = {
  all: ["auth"] as const,
  sessions: () => [...authKeys.all, "sessions"] as const,
};

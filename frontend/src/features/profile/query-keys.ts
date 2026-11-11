export const profileKeys = {
  all: ["profile"] as const,
  me: () => [...profileKeys.all, "me"] as const,
  phone: () => [...profileKeys.all, "phone"] as const,
  simulatedInbox: () => [...profileKeys.all, "phone", "simulated-inbox"] as const,
  presence: () => [...profileKeys.all, "presence"] as const,
};

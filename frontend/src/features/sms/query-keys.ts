import type { SmsTarget } from "@/features/sms/types";

export const smsKeys = {
  all: ["sms"] as const,
  status: () => [...smsKeys.all, "status"] as const,
  countries: () => [...smsKeys.all, "countries"] as const,
  lists: () => [...smsKeys.all, "list"] as const,
  messages: (conversationId: string) => [...smsKeys.all, "messages", conversationId] as const,
  quote: (target: SmsTarget | null, body: string) =>
    [...smsKeys.all, "quote", target, body] as const,
  admin: () => [...smsKeys.all, "admin"] as const,
};

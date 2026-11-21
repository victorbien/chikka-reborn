import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type {
  ConsentState,
  Country,
  Paged,
  Quote,
  SmsConversation,
  SmsMessage,
  SmsMode,
  SmsTarget,
  SmsThread,
} from "@/features/sms/types";

const BASE = "/api/v1/sms";
export const SMS_PAGE_SIZE = 50;

/** The wire form of a recipient. Local numbers need the country the user picked. */
export function recipientPayload(target: SmsTarget): Record<string, string> {
  switch (target.kind) {
    case "conversation":
      return { conversation_id: target.conversationId };
    case "contact":
      return { contact_id: target.contactId };
    case "number":
      return { to: target.to.trim(), country_code: target.countryCode };
  }
}

export function createSmsApi(client: ApiClient = apiClient) {
  return {
    status: (signal?: AbortSignal) =>
      client.get<Envelope<SmsMode>>(`${BASE}/status`, { signal }).then(unwrap),
    countries: (signal?: AbortSignal) =>
      client.get<Envelope<Country[]>>(`${BASE}/countries`, { signal }).then(unwrap),
    quote: (target: SmsTarget, body: string, signal?: AbortSignal) =>
      client
        .post<Envelope<Quote>>(`${BASE}/quote`, { ...recipientPayload(target), body }, { signal })
        .then(unwrap),
    setConsent: (target: SmsTarget, decision: "granted" | "withdrawn") =>
      client
        .put<Envelope<ConsentState>>(`${BASE}/consents`, { ...recipientPayload(target), decision })
        .then(unwrap),
    send: (target: SmsTarget, body: string, idempotencyKey: string) =>
      client
        .post<Envelope<SmsMessage>>(
          `${BASE}/messages`,
          { ...recipientPayload(target), body, confirmed: true },
          { idempotencyKey },
        )
        .then(unwrap),
    retry: (messageId: string, idempotencyKey: string) =>
      client
        .post<Envelope<SmsMessage>>(
          `${BASE}/messages/${messageId}/retry`,
          { confirmed: true },
          { idempotencyKey },
        )
        .then(unwrap),
    conversations: (signal?: AbortSignal) =>
      client.get<Paged<SmsConversation>>(`${BASE}/conversations`, {
        signal,
        query: { page_size: 30 },
      }),
    messages: (conversationId: string, beforeSeq?: number, signal?: AbortSignal) =>
      client
        .get<Envelope<SmsThread>>(`${BASE}/conversations/${conversationId}/messages`, {
          signal,
          query: { before_seq: beforeSeq, limit: SMS_PAGE_SIZE },
        })
        .then(unwrap),
    markRead: (conversationId: string, upToSeq: number) =>
      client
        .post<Envelope<{ conversation_id: string; last_read_seq: number; unread_count: number }>>(
          `${BASE}/conversations/${conversationId}/read`,
          { up_to_seq: upToSeq },
        )
        .then(unwrap),
  };
}

export const smsApi = createSmsApi();

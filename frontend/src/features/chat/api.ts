import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type {
  Attachment,
  ConversationListParams,
  ConversationSummary,
  MessagePage,
  Paged,
  ReadState,
  ServerMessage,
  UnreadTotals,
} from "@/features/chat/types";

const BASE = "/api/v1/conversations";
export const CONVERSATION_PAGE_SIZE = 30;
export const MESSAGE_PAGE_SIZE = 50;

export interface SendPayload {
  client_message_id: string;
  body?: string;
  attachment_ids?: string[];
}

export function createChatApi(client: ApiClient = apiClient) {
  return {
    list: (params: ConversationListParams, signal?: AbortSignal) =>
      client.get<Paged<ConversationSummary>>(BASE, {
        signal,
        query: {
          archived: params.archived,
          q: params.q.trim() || undefined,
          page_size: CONVERSATION_PAGE_SIZE,
        },
      }),
    open: (userId: string) =>
      client.post<Envelope<ConversationSummary>>(BASE, { user_id: userId }).then(unwrap),
    get: (id: string, signal?: AbortSignal) =>
      client.get<Envelope<ConversationSummary>>(`${BASE}/${id}`, { signal }).then(unwrap),
    setArchived: (id: string, isArchived: boolean) =>
      client
        .patch<Envelope<ConversationSummary>>(`${BASE}/${id}`, { is_archived: isArchived })
        .then(unwrap),
    unread: (signal?: AbortSignal) =>
      client.get<Envelope<UnreadTotals>>(`${BASE}/unread`, { signal }).then(unwrap),
    messages: (
      id: string,
      cursor: { before_seq?: number; after_seq?: number },
      signal?: AbortSignal,
    ) =>
      client
        .get<Envelope<MessagePage>>(`${BASE}/${id}/messages`, {
          signal,
          query: { ...cursor, limit: MESSAGE_PAGE_SIZE },
        })
        .then(unwrap),
    send: (id: string, payload: SendPayload) =>
      client.post<Envelope<ServerMessage>>(`${BASE}/${id}/messages`, payload).then(unwrap),
    markRead: (id: string, upToSeq: number) =>
      client.post<Envelope<ReadState>>(`${BASE}/${id}/read`, { up_to_seq: upToSeq }).then(unwrap),
    upload: (id: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return client.post<Envelope<Attachment>>(`${BASE}/${id}/attachments`, form).then(unwrap);
    },
  };
}

export const chatApi = createChatApi();

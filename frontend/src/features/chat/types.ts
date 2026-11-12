/** Mirrors backend/app/modules/chat/schemas.py. */
import type { PresenceStatus } from "@/lib/types";

export type ServerMessageStatus = "sent" | "delivered" | "read";
/** What the sender sees. "pending" and "failed" exist only on this device. */
export type ChatMessageStatus = "pending" | "failed" | ServerMessageStatus;

export interface Participant {
  user_id: string;
  username: string | null;
  display_name: string;
  avatar_url: string | null;
  presence: PresenceStatus;
  is_contact: boolean;
}

export interface Attachment {
  id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  url: string | null;
}

export interface ServerMessage {
  id: string;
  conversation_id: string;
  seq: number;
  sender_user_id: string;
  is_mine: boolean;
  body: string | null;
  attachments: Attachment[];
  created_at: string;
  edited_at: string | null;
  client_message_id: string | null;
  status: ServerMessageStatus | null;
  status_version: number | null;
  delivered_at: string | null;
  read_at: string | null;
}

/** A message in the cache: from the server, or a local one not stored yet. */
export interface ChatMessage extends Omit<ServerMessage, "status"> {
  status: ChatMessageStatus | null;
  /** Local messages have no server id or seq yet. */
  local?: {
    state: "pending" | "failed";
    error?: string;
    attachmentIds: string[];
  };
}

export interface MessagePage {
  messages: ServerMessage[];
  has_more_before: boolean;
  last_read_seq: number;
  peer_read_seq: number | null;
}

export interface LastMessage {
  id: string;
  seq: number;
  is_mine: boolean;
  preview: string;
  has_attachments: boolean;
  created_at: string;
  status: ServerMessageStatus | null;
}

export interface ConversationSummary {
  id: string;
  conversation_type: "chikka";
  participant: Participant;
  last_message: LastMessage | null;
  last_message_at: string | null;
  unread_count: number;
  is_archived: boolean;
  is_muted: boolean;
  can_send: boolean;
  cannot_send_reason: string | null;
}

export interface ReadState {
  conversation_id: string;
  last_read_seq: number;
  unread_count: number;
}

export interface UnreadTotals {
  unread_messages: number;
  unread_conversations: number;
}

export interface StatusChange {
  message_id: string;
  conversation_id: string;
  status: ServerMessageStatus;
  status_version: number;
  delivered_at: string | null;
  read_at: string | null;
}

export interface ConversationListParams {
  archived: boolean;
  q: string;
}

export interface Paged<T> {
  data: T[];
  pagination: {
    total: number;
    page: number;
    page_size: number;
    has_next: boolean;
    has_prev: boolean;
  };
  request_id: string;
}

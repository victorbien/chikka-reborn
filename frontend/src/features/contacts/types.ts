/** Mirrors backend/app/modules/contacts/schemas.py. */
import type { PresenceStatus } from "@/lib/types";

export type ContactFilter = "all" | "online" | "offline" | "favourites" | "group";
export type Relationship = "none" | "contact" | "request_sent" | "request_received";

export interface Pagination {
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface Paged<T> {
  data: T[];
  pagination: Pagination;
  request_id: string;
}

export interface PersonCard {
  user_id: string;
  username: string | null;
  display_name: string;
  avatar_url: string | null;
}

export interface SearchPerson extends PersonCard {
  relationship: Relationship;
  contact_id: string | null;
  request_id: string | null;
}

export interface ContactSummary {
  id: string;
  contact_type: "chikka" | "sms";
  user_id: string | null;
  username: string | null;
  display_name: string;
  nickname: string | null;
  avatar_url: string | null;
  status_message: string | null;
  presence: PresenceStatus;
  last_seen_at: string | null;
  is_favourite: boolean;
  group_ids: string[];
  masked_phone: string | null;
}

export interface ContactDetail extends ContactSummary {
  bio: string | null;
  country_code: string | null;
  added_at: string;
}

export interface SearchResult {
  contacts: ContactSummary[];
  people: SearchPerson[];
}

export interface ContactRequestItem {
  id: string;
  direction: "incoming" | "outgoing";
  person: PersonCard;
  note: string | null;
  created_at: string;
  expires_at: string;
}

/** The same whether the request was created or silently ignored. */
export interface RequestSent {
  status: "sent" | "contacts";
}

export interface ContactGroup {
  id: string;
  name: string;
  color: string | null;
  position: number;
  member_count: number;
}

export interface BlockItem {
  user_id: string;
  person: PersonCard;
  blocked_at: string;
}

export interface RecentContact {
  contact: ContactSummary;
  conversation_id: string;
  last_message_at: string;
}

export interface RecentConversation {
  conversation_id: string;
  conversation_type: "chikka" | "sms";
  contact_id: string | null;
  user_id: string | null;
  display_name: string;
  avatar_url: string | null;
  masked_phone: string | null;
  is_contact: boolean;
  last_message_at: string | null;
}

export interface ContactListParams {
  filter: ContactFilter;
  groupId?: string;
  page: number;
}

/** Mirrors backend/app/modules/sms/schemas.py. */

export type SmsMessageStatus =
  "queued" | "retrying" | "accepted" | "sent" | "delivered" | "undelivered" | "failed" | "received";

export type Availability = "available" | "simulation_only" | "unavailable";
export type Replies = "supported" | "unverified" | "unsupported";
export type DeliveryConfirmation = "confirmed" | "pending" | "unconfirmed" | "not_applicable";

export interface SmsMode {
  mode: "simulation" | "live";
  provider: string;
  is_simulated: boolean;
  outbound_paused: boolean;
  sender_verified: boolean;
  notice: string;
}

export interface Country {
  country_code: string;
  country_name: string;
  dial_code: number;
  availability: Availability;
  unavailable_reason: string | null;
  outbound: string;
  replies: Replies;
  registered_sender_required: boolean;
  registered_sender_status: string;
  content_restrictions: string | null;
  consent_required: boolean;
  credits_per_segment: number | null;
  max_segments: number;
  verified: boolean;
  notes: string | null;
}

/** How the recipient is named. The server resolves it; the client never sends user ids. */
export type SmsTarget =
  | { kind: "conversation"; conversationId: string }
  | { kind: "contact"; contactId: string }
  | { kind: "number"; to: string; countryCode: string };

export interface Quote {
  recipient: {
    masked_phone: string;
    country_code: string;
    country_name: string | null;
    number_type: string;
    contact_id: string | null;
    display_name: string | null;
    conversation_id: string | null;
  };
  mode: "simulation" | "live";
  is_simulated: boolean;
  availability: Availability;
  replies: Replies;
  warnings: string[];
  segment: {
    encoding: "gsm7" | "ucs2";
    characters: number;
    units: number;
    segments: number;
    per_segment: number;
    remaining_in_segment: number;
    max_segments: number;
    too_long: boolean;
  };
  cost: {
    units: number | null;
    credits: number | null;
    source: "configured" | "demo_default" | "unavailable";
    estimated: true;
  };
  consent: { required: boolean; granted: boolean; notice_version: string };
  recipient_opted_out: boolean;
  blockers: { code: string; message: string }[];
  can_send: boolean;
}

export interface SmsDelivery {
  attempt_number: number;
  provider: string | null;
  accepted_at: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  next_attempt_at: string | null;
  confirmation: DeliveryConfirmation;
}

export interface SmsFailure {
  code: string | null;
  reason: string;
  is_permanent: boolean;
  may_have_been_delivered: boolean;
}

export interface SmsMessage {
  id: string;
  conversation_id: string;
  seq: number;
  direction: "outbound" | "inbound";
  is_mine: boolean;
  body: string | null;
  status: SmsMessageStatus;
  status_version: number;
  is_simulated: boolean;
  encoding: string | null;
  char_count: number | null;
  segment_count: number | null;
  created_at: string;
  client_message_id: string | null;
  delivery: SmsDelivery | null;
  failure: SmsFailure | null;
  can_retry: boolean;
  attempt_count: number;
}

export interface SmsConversation {
  id: string;
  masked_phone: string;
  country_code: string | null;
  display_name: string | null;
  contact_id: string | null;
  last_message_preview: string | null;
  last_message_direction: "outbound" | "inbound" | null;
  last_message_status: SmsMessageStatus | null;
  last_message_at: string | null;
  last_is_simulated: boolean;
  unread_count: number;
  is_archived: boolean;
  is_muted: boolean;
  replies: Replies;
}

export interface SmsThread {
  messages: SmsMessage[];
  has_more_before: boolean;
  last_read_seq: number;
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

export interface ConsentState {
  required: boolean;
  granted: boolean;
  notice_version: string;
}

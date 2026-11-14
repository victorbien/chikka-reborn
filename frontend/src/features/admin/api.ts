import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type { Paged } from "@/features/sms/types";

const BASE = "/api/v1/admin";

export interface SmsModeStats {
  sent: number;
  received: number;
  delivered: number;
  failed: number;
  undelivered: number;
  in_progress: number;
  delivery_success_rate: number | null;
}

export interface Dashboard {
  generated_at: string;
  users: {
    total_registered: number;
    active_accounts: number;
    pending_verification: number;
    suspended: number;
    administrators: number;
    active_last_24h: number;
    active_last_7d: number;
    active_last_30d: number;
  };
  conversations: { total: number; chikka: number; sms: number };
  messages: { chikka_messages_sent: number };
  sms: { live: SmsModeStats; simulated: SmsModeStats };
  ai: {
    total_requests: number;
    last_24h: number;
    failed_requests: number;
    input_tokens: number;
    output_tokens: number;
  };
  credits: {
    ledger_type: "live" | "demo";
    transactions: number;
    units_granted: number;
    units_deducted: number;
    units_refunded: number;
    units_adjusted: number;
  }[];
}

export type AccountStatus = "pending_verification" | "active" | "suspended" | "deleted";

export interface AdminUserRow {
  id: string;
  username: string | null;
  display_name: string | null;
  masked_email: string | null;
  role: "user" | "admin";
  status: AccountStatus;
  country_code: string | null;
  created_at: string;
  last_seen_at: string | null;
  suspended_at: string | null;
}

export interface AdminUserDetail extends AdminUserRow {
  masked_verified_phone: string | null;
  ai_enabled: boolean;
  deletion_requested_at: string | null;
  activity: {
    chikka_messages_sent: number;
    sms_sent: number;
    sms_received: number;
    conversations: number;
    ai_requests: number;
    open_reports_against: number;
    active_sessions: number;
  };
  credits: { ledger_type: string; balance_units: number; reserved_units: number }[];
}

export const RESTRICTION_REASONS = ["abuse", "spam", "fraud", "security", "other"] as const;
export type RestrictionReason = (typeof RESTRICTION_REASONS)[number];

export interface UsersQuery {
  q?: string;
  status?: AccountStatus;
  page?: number;
}

export interface SmsMessageRow {
  id: string;
  direction: "outbound" | "inbound";
  status: string;
  is_simulated: boolean;
  created_at: string;
  masked_phone: string | null;
  user_id: string | null;
  segment_count: number | null;
  attempts: number;
  provider_message_id: string | null;
  failure_class: string | null;
  failure_code: string | null;
  failure_reason: string | null;
}

export interface DeliveryAttempt {
  attempt_number: number;
  status: string;
  provider_message_id: string | null;
  is_simulated: boolean;
  failure_class: string | null;
  failure_code: string | null;
  failure_reason: string | null;
  is_permanent: boolean | null;
  started_at: string | null;
  next_attempt_at: string | null;
  terminal_at: string | null;
  events: {
    source: string;
    provider_status: string | null;
    normalised_status: string;
    applied: boolean;
    ignore_reason: string | null;
    received_at: string;
  }[];
}

export interface SmsMessageDetail extends SmsMessageRow {
  attempts_history: DeliveryAttempt[];
}

export interface SmsQuery {
  direction: "outbound" | "inbound";
  status?: string;
  page?: number;
}

export interface ProviderOverview {
  health: {
    health: "healthy" | "degraded" | "paused" | "unavailable";
    reasons: string[];
    mode: "simulation" | "live" | null;
    running_provider: string | null;
    active_provider: string | null;
    credentials_configured: boolean;
    outbound_paused: boolean;
    dispatch_paused_by_configuration_error: boolean;
    queue_depth: number;
    delivery_success_rate_24h: number | null;
    webhook_failures_24h: number;
    webhook_signature_rejections_24h: number;
  };
  configuration: {
    app_env: string;
    sms_provider_mode: string;
    sms_live_confirmed: boolean;
    sms_worker_enabled: boolean;
    ai_provider_mode: string;
    ai_provider_configured: boolean;
    email_provider_mode: string;
  };
  capabilities: {
    country_code: string;
    country_name: string;
    outbound_support: string;
    inbound_support: string;
    registered_sender_required: boolean;
    registered_sender_status: string;
    verified: boolean;
  }[];
}

export interface AiMetrics {
  window_days: number;
  total_requests: number;
  failed_requests: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  features: {
    feature: string;
    requests: number;
    failures: number;
    accepted: number;
    average_latency_ms: number | null;
    input_tokens: number;
    output_tokens: number;
  }[];
  errors: { outcome: string; error_code: string | null; count: number }[];
  daily: { day: string; requests: number }[];
}

export interface AuditLogRow {
  id: string;
  created_at: string;
  category: string;
  action: string;
  outcome: "success" | "denied" | "failure";
  actor_id: string | null;
  actor_role: string | null;
  target_type: string | null;
  target_id: string | null;
  request_id: string | null;
}

export interface AuditQuery {
  outcome?: "success" | "denied" | "failure";
  action?: string;
  page?: number;
}

export function createAdminApi(client: ApiClient = apiClient) {
  return {
    dashboard: (signal?: AbortSignal) =>
      client.get<Envelope<Dashboard>>(`${BASE}/dashboard`, { signal }).then(unwrap),
    users: (query: UsersQuery, signal?: AbortSignal) =>
      client.get<Paged<AdminUserRow>>(`${BASE}/users`, { query: { ...query }, signal }),
    user: (id: string, signal?: AbortSignal) =>
      client.get<Envelope<AdminUserDetail>>(`${BASE}/users/${id}`, { signal }).then(unwrap),
    restrict: (id: string, reason: RestrictionReason) =>
      client
        .post<Envelope<AdminUserRow>>(`${BASE}/users/${id}/restrict`, { reason_code: reason })
        .then(unwrap),
    reinstate: (id: string) =>
      client.post<Envelope<AdminUserRow>>(`${BASE}/users/${id}/reinstate`).then(unwrap),
    smsMessages: (query: SmsQuery, signal?: AbortSignal) =>
      client.get<Paged<SmsMessageRow>>(`${BASE}/sms/messages`, { query: { ...query }, signal }),
    smsMessage: (id: string, signal?: AbortSignal) =>
      client.get<Envelope<SmsMessageDetail>>(`${BASE}/sms/messages/${id}`, { signal }).then(unwrap),
    providers: (signal?: AbortSignal) =>
      client.get<Envelope<ProviderOverview>>(`${BASE}/providers/overview`, { signal }).then(unwrap),
    aiMetrics: (signal?: AbortSignal) =>
      client.get<Envelope<AiMetrics>>(`${BASE}/ai/metrics`, { signal }).then(unwrap),
    auditLogs: (query: AuditQuery, signal?: AbortSignal) =>
      client.get<Paged<AuditLogRow>>(`${BASE}/audit-logs`, { query: { ...query }, signal }),
  };
}

export const adminApi = createAdminApi();

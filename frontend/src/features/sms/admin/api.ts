import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type { Paged } from "@/features/sms/types";

const BASE = "/api/v1/admin/sms";

export interface AdminProvider {
  id: string;
  provider: string;
  display_name: string;
  mode: "simulation" | "live";
  is_active: boolean;
  is_running: boolean;
  /** Only whether credentials exist. The values and their names never reach the browser. */
  credentials_configured: boolean;
  sender_registration_status: string;
  webhook_path: string | null;
  max_retry_attempts: number;
  retry_base_seconds: number;
  retry_cap_seconds: number;
  retry_multiplier: number;
  sender_numbers: string[];
  live_confirmed_at: string | null;
  live_confirmed_environment: string | null;
}

export interface AdminCapability {
  country_code: string;
  country_name: string;
  dial_code: number;
  version: number;
  outbound_support: string;
  inbound_support: string;
  registered_sender_required: boolean;
  registered_sender_status: string;
  price_units_per_segment: number | null;
  supported_number_types: string[];
  consent_required: boolean;
  content_restrictions: string | null;
  verified: boolean;
}

export interface Monitoring {
  mode: "simulation" | "live";
  provider: string;
  outbound_paused: boolean;
  dispatch_paused_by_configuration_error: boolean;
  queue_depth: number;
  last_24h: { status: string; is_simulated: boolean; total: number }[];
  delivery_rate: number | null;
  failure_rate: number | null;
  unrouted_inbound: number;
  webhook_processing_failures: number;
  webhook_orphaned: number;
  webhook_signature_rejections: number;
  opt_outs: number;
  recent_failures: {
    message_id: string;
    created_at: string;
    status: string;
    is_simulated: boolean;
    attempts: number;
    failure_class: string | null;
    failure_code: string | null;
    reason: string;
    masked_recipient: string;
  }[];
}

export interface UnroutedInbound {
  id: string;
  received_at: string;
  is_simulated: boolean;
  masked_sender: string;
  masked_platform_number: string;
  retained_until: string;
}

export interface RetrySettings {
  max_retry_attempts: number;
  retry_base_seconds: number;
  retry_cap_seconds: number;
}

export function createAdminSmsApi(client: ApiClient = apiClient) {
  return {
    providers: (signal?: AbortSignal) =>
      client.get<Envelope<AdminProvider[]>>(`${BASE}/providers`, { signal }).then(unwrap),
    updateProvider: (id: string, settings: RetrySettings) =>
      client.patch<Envelope<AdminProvider[]>>(`${BASE}/providers/${id}`, settings).then(unwrap),
    activate: (id: string, confirmEnvironment: string) =>
      client
        .post<Envelope<AdminProvider[]>>(`${BASE}/providers/${id}/activate`, {
          confirm_environment: confirmEnvironment,
        })
        .then(unwrap),
    setPaused: (paused: boolean) =>
      client.put<Envelope<{ paused: boolean }>>(`${BASE}/outbound-paused`, { paused }).then(unwrap),
    capabilities: (signal?: AbortSignal) =>
      client.get<Envelope<AdminCapability[]>>(`${BASE}/capabilities`, { signal }).then(unwrap),
    monitoring: (signal?: AbortSignal) =>
      client.get<Envelope<Monitoring>>(`${BASE}/monitoring`, { signal }).then(unwrap),
    unrouted: (signal?: AbortSignal) =>
      client.get<Paged<UnroutedInbound>>(`${BASE}/inbound/unrouted`, { signal }),
    simulateInbound: (payload: {
      from_phone: string;
      to_number: string;
      body: string;
      replay_id?: string;
    }) =>
      client
        .post<Envelope<{ duplicate: boolean; routing_result: string | null }>>(
          `${BASE}/simulate/inbound`,
          payload,
        )
        .then(unwrap),
  };
}

export const adminSmsApi = createAdminSmsApi();

/** Error envelope returned by every failing API response. */
export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody;
  request_id: string;
}

/** Shape of GET /api/v1/health. */
export interface HealthStatus {
  status: "ok" | "degraded";
  service: string;
  version: string;
  environment: string;
  sms_mode: "simulation" | "live";
  database: "ok" | "unavailable" | "not_configured";
  request_id: string;
}

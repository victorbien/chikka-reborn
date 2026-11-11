import type { ApiErrorEnvelope } from "@/types/api";

export type ApiErrorKind = "network" | "http" | "invalid_response";

/** Typed error thrown by the API client for every failure path. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string;
  readonly requestId: string | null;
  readonly details: Record<string, unknown>;

  constructor(options: {
    kind: ApiErrorKind;
    message: string;
    status?: number | null;
    code?: string;
    requestId?: string | null;
    details?: Record<string, unknown>;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.kind = options.kind;
    this.status = options.status ?? null;
    this.code = options.code ?? "unknown_error";
    this.requestId = options.requestId ?? null;
    this.details = options.details ?? {};
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Narrow an unknown JSON body to the documented error envelope. */
export function parseErrorEnvelope(body: unknown): ApiErrorEnvelope | null {
  if (!isRecord(body) || !isRecord(body.error)) return null;
  const { code, message, details } = body.error;
  if (typeof code !== "string" || typeof message !== "string") return null;
  return {
    error: { code, message, details: isRecord(details) ? details : {} },
    request_id: typeof body.request_id === "string" ? body.request_id : "",
  };
}

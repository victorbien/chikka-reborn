import { env } from "@/lib/env";
import { ApiError, parseErrorEnvelope } from "@/lib/api/errors";

export type TokenProvider = () => string | null | Promise<string | null>;

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  /** Required by callers that send SMS; sent as the Idempotency-Key header. */
  idempotencyKey?: string;
  signal?: AbortSignal;
}

export interface ApiClientConfig {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

/**
 * The only place the frontend talks HTTP to the backend. It adds the auth header,
 * parses the error envelope and surfaces the request_id. Components never call fetch.
 */
export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private tokenProvider: TokenProvider = () => null;

  constructor(config: ApiClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, "");
    this.fetchImpl = config.fetchImpl ?? ((input, init) => fetch(input, init));
  }

  setTokenProvider(provider: TokenProvider): void {
    this.tokenProvider = provider;
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const url = this.buildUrl(path, options.query);
    const headers: Record<string, string> = { Accept: "application/json" };

    const token = await this.tokenProvider();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
    if (options.body !== undefined) headers["Content-Type"] = "application/json";

    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        method: options.method ?? "GET",
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: options.signal,
      });
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
      throw new ApiError({
        kind: "network",
        message: "Could not reach the server. Check your connection and try again.",
        code: "network_error",
      });
    }

    const body = await this.readJson(response);

    if (!response.ok) {
      const envelope = parseErrorEnvelope(body);
      throw new ApiError({
        kind: "http",
        status: response.status,
        message: envelope?.error.message ?? `The server responded with status ${response.status}.`,
        code: envelope?.error.code ?? "http_error",
        requestId: envelope?.request_id || response.headers.get("X-Request-ID"),
        details: envelope?.error.details,
      });
    }

    if (body === undefined) {
      throw new ApiError({
        kind: "invalid_response",
        status: response.status,
        message: "The server returned a response that could not be read.",
        code: "invalid_response",
        requestId: response.headers.get("X-Request-ID"),
      });
    }
    return body as T;
  }

  get<T>(path: string, options: Omit<RequestOptions, "method" | "body"> = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "GET" });
  }

  private buildUrl(path: string, query?: RequestOptions["query"]): string {
    const url = new URL(`${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`);
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
    return url.toString();
  }

  private async readJson(response: Response): Promise<unknown> {
    try {
      return (await response.json()) as unknown;
    } catch {
      return undefined;
    }
  }
}

export const apiClient = new ApiClient({ baseUrl: env.VITE_API_BASE_URL });

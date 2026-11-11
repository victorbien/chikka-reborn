import { env } from "@/lib/env";
import { ApiError, parseErrorEnvelope } from "@/lib/api/errors";

export type TokenProvider = () => string | null | Promise<string | null>;

export interface AuthHandlers {
  /** Current access token (memory only), or null when signed out. */
  getToken: TokenProvider;
  /** Exchange the refresh cookie for a new access token. Resolves null when that fails. */
  refresh: () => Promise<string | null>;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, string | number | boolean | undefined>;
  /** JSON-serialisable value, or FormData for uploads. */
  body?: unknown;
  headers?: Record<string, string>;
  /** Required by callers that send SMS; sent as the Idempotency-Key header. */
  idempotencyKey?: string;
  signal?: AbortSignal;
  /** Auth endpoints themselves must not trigger a refresh-and-retry. */
  skipAuthRefresh?: boolean;
}

export interface ApiClientConfig {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

/** 401 codes that mean "get a new access token", as opposed to "wrong password". */
const REFRESHABLE_CODES = new Set(["token_expired", "session_revoked", "not_authenticated"]);

/**
 * The only place the frontend talks HTTP to the backend. It adds the auth header, sends the
 * refresh cookie, parses the error envelope and surfaces the request_id. Components never
 * call fetch.
 */
export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private handlers: AuthHandlers = { getToken: () => null, refresh: async () => null };

  constructor(config: ApiClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, "");
    this.fetchImpl = config.fetchImpl ?? ((input, init) => fetch(input, init));
  }

  setTokenProvider(provider: TokenProvider): void {
    this.handlers = { ...this.handlers, getToken: provider };
  }

  setAuthHandlers(handlers: AuthHandlers): void {
    this.handlers = handlers;
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const token = await this.handlers.getToken();
    try {
      return await this.send<T>(path, options, token);
    } catch (error) {
      if (
        options.skipAuthRefresh ||
        !token ||
        !(error instanceof ApiError) ||
        error.status !== 401 ||
        !REFRESHABLE_CODES.has(error.code)
      ) {
        throw error;
      }
      const fresh = await this.handlers.refresh();
      if (!fresh) throw error;
      return this.send<T>(path, options, fresh);
    }
  }

  get<T>(path: string, options: Omit<RequestOptions, "method" | "body"> = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "GET" });
  }

  post<T>(path: string, body?: unknown, options: Omit<RequestOptions, "method" | "body"> = {}) {
    return this.request<T>(path, { ...options, method: "POST", body });
  }

  patch<T>(path: string, body?: unknown, options: Omit<RequestOptions, "method" | "body"> = {}) {
    return this.request<T>(path, { ...options, method: "PATCH", body });
  }

  put<T>(path: string, body?: unknown, options: Omit<RequestOptions, "method" | "body"> = {}) {
    return this.request<T>(path, { ...options, method: "PUT", body });
  }

  delete<T>(path: string, body?: unknown, options: Omit<RequestOptions, "method" | "body"> = {}) {
    return this.request<T>(path, { ...options, method: "DELETE", body });
  }

  private async send<T>(path: string, options: RequestOptions, token: string | null): Promise<T> {
    const url = this.buildUrl(path, options.query);
    const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

    let body: BodyInit | undefined;
    if (options.body instanceof FormData) {
      body = options.body; // the browser sets the multipart boundary
    } else if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }

    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        method: options.method ?? "GET",
        headers,
        body,
        signal: options.signal,
        // Sends the httpOnly refresh cookie to the auth endpoints; the API allows only
        // explicit origins, so this never reaches other sites.
        credentials: "include",
      });
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
      throw new ApiError({
        kind: "network",
        message: "Could not reach the server. Check your connection and try again.",
        code: "network_error",
      });
    }

    if (response.status === 204) return undefined as T;

    const parsed = await this.readJson(response);

    if (!response.ok) {
      const envelope = parseErrorEnvelope(parsed);
      throw new ApiError({
        kind: "http",
        status: response.status,
        message: envelope?.error.message ?? `The server responded with status ${response.status}.`,
        code: envelope?.error.code ?? "http_error",
        requestId: envelope?.request_id || response.headers.get("X-Request-ID"),
        details: envelope?.error.details,
      });
    }

    if (parsed === undefined) {
      throw new ApiError({
        kind: "invalid_response",
        status: response.status,
        message: "The server returned a response that could not be read.",
        code: "invalid_response",
        requestId: response.headers.get("X-Request-ID"),
      });
    }
    return parsed as T;
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

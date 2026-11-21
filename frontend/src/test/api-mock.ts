import { vi } from "vitest";
import type { Profile } from "@/features/profile/types";

/** Test-only fetch router. Every call is recorded; unknown routes answer 404. */
export interface MockRequest {
  method: string;
  path: string;
  /** Query string including the leading "?", or "". */
  search: string;
  body: unknown;
  headers: Record<string, string>;
  credentials: RequestCredentials | undefined;
}

export interface MockReply {
  status?: number;
  body?: unknown;
}

export type MockHandler = MockReply | ((request: MockRequest) => MockReply | Promise<MockReply>);

export function ok<T>(data: T): MockReply {
  return { status: 200, body: { data, request_id: "req-test" } };
}

export function fail(
  status: number,
  code: string,
  message = "Request failed.",
  details: Record<string, unknown> = {},
): MockReply {
  return { status, body: { error: { code, message, details }, request_id: "req-fail" } };
}

export const TOKENS = { access_token: "access-1", token_type: "bearer", expires_in: 3600 };

export function mockApi(routes: Record<string, MockHandler>) {
  const calls: MockRequest[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    const method = init?.method ?? "GET";
    const rawBody = init?.body;
    const request: MockRequest = {
      method,
      path: url.pathname,
      search: url.search,
      body: typeof rawBody === "string" ? (JSON.parse(rawBody) as unknown) : rawBody,
      headers: { ...(init?.headers as Record<string, string> | undefined) },
      credentials: init?.credentials,
    };
    calls.push(request);
    const handler = routes[`${method} ${url.pathname}`];
    const reply = handler
      ? typeof handler === "function"
        ? await handler(request)
        : handler
      : fail(404, "not_found", "Resource not found.");
    const status = reply.status ?? 200;
    return new Response(status === 204 ? null : JSON.stringify(reply.body ?? {}), {
      status,
      headers: { "Content-Type": "application/json", "X-Request-ID": "req-test" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    calls,
    callsTo: (method: string, path: string) =>
      calls.filter((call) => call.method === method && call.path === path),
  };
}

/** Fictional profile data only. */
export function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: "00000000-0000-4000-8000-000000000001",
    username: "marites_s",
    display_name: "Marites Santos",
    email: "marites@example.com",
    email_verified: true,
    avatar_url: null,
    bio: null,
    status_message: null,
    country_code: "PH",
    language: "en",
    time_zone: "Asia/Manila",
    theme: "system",
    ui_mode: "modern",
    presence_preference: "online",
    role: "user",
    status: "active",
    onboarding_completed: true,
    phone: null,
    created_at: "2026-11-01T00:00:00Z",
    updated_at: "2026-11-01T00:00:00Z",
    ...overrides,
  };
}

/** Routes every signed-in screen needs: session restore, profile, presence. */
export function signedInRoutes(profile: Profile = makeProfile()): Record<string, MockHandler> {
  return {
    "POST /api/v1/auth/refresh": ok(TOKENS),
    "GET /api/v1/users/me": ok(profile),
    "POST /api/v1/users/me/presence/heartbeat": ok({
      status: "online",
      preference: profile.presence_preference,
      last_seen_at: "2026-11-11T00:00:00Z",
    }),
    "GET /api/v1/health": {
      status: 200,
      body: {
        status: "ok",
        service: "chikka-reborn-api",
        version: "0.1.0",
        environment: "test",
        sms_mode: "simulation",
        database: "ok",
        request_id: "req-1",
      },
    },
  };
}

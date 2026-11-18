import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { API, FAKE, PASSWORD, SERVICE_KEY } from "./stack";

/** A user created through the API. Fictional data only. */
export interface TestUser {
  email: string;
  username: string;
  displayName: string;
  userId: string;
  accessToken: string;
}

let counter = 0;
export function uniqueName(prefix: string): string {
  counter += 1;
  return `${prefix}${Date.now().toString(36)}${counter}`.toLowerCase().slice(0, 20);
}

/** A fictional Philippine mobile number (+63 917 ...), unique per call. */
export function fictionalMobile(): string {
  counter += 1;
  return `+63917${String((Date.now() + counter) % 10_000_000).padStart(7, "0")}`;
}

export async function resetRateLimits(request: APIRequestContext): Promise<void> {
  const response = await request.post(`${FAKE}/__reset_rate_limits`, {
    headers: { apikey: SERVICE_KEY },
  });
  expect(response.status()).toBe(204);
}

export async function emailToken(
  request: APIRequestContext,
  email: string,
  kind: "signup" | "recovery" = "signup",
): Promise<string> {
  const response = await request.get(`${FAKE}/__outbox`, { params: { to: email } });
  const emails = (await response.json()) as { kind: string; token_hash: string }[];
  const match = emails.filter((item) => item.kind === kind).at(-1);
  if (!match) throw new Error(`no ${kind} email for ${email}`);
  return match.token_hash;
}

export function bearer(user: TestUser): Record<string, string> {
  return { Authorization: `Bearer ${user.accessToken}` };
}

/**
 * Registers, confirms the email and (by default) finishes the profile through the API. The
 * refresh cookie lands in `request`'s cookie jar, so passing `page.request` also signs the
 * browser in on its next page load.
 */
export async function createUser(
  request: APIRequestContext,
  label: string,
  options: { onboard?: boolean; uiMode?: "modern" | "classic" } = {},
): Promise<TestUser> {
  const username = uniqueName(label);
  const email = `${username}@example.com`;
  const displayName = `${label[0]?.toUpperCase() ?? "T"}${label.slice(1)} Tester`;
  const registered = await request.post(`${API}/api/v1/auth/register`, {
    data: { email, display_name: displayName, password: PASSWORD, accept_terms: true },
  });
  expect(registered.status(), await registered.text()).toBe(202);
  const verified = await request.post(`${API}/api/v1/auth/verify-email`, {
    data: { token_hash: await emailToken(request, email) },
  });
  expect(verified.status(), await verified.text()).toBe(200);
  const accessToken = ((await verified.json()) as { data: { access_token: string } }).data
    .access_token;
  const user: TestUser = { email, username, displayName, userId: "", accessToken };
  if (options.onboard ?? true) {
    const onboarded = await request.post(`${API}/api/v1/users/me/onboarding`, {
      headers: bearer(user),
      data: {
        username,
        display_name: displayName,
        country_code: "PH",
        language: "en",
        time_zone: "Asia/Manila",
        ui_mode: options.uiMode ?? "modern",
      },
    });
    expect(onboarded.status(), await onboarded.text()).toBe(200);
  }
  const me = await request.get(`${API}/api/v1/users/me`, { headers: bearer(user) });
  user.userId = ((await me.json()) as { data: { id: string } }).data.id;
  return user;
}

export async function promoteToAdmin(request: APIRequestContext, user: TestUser): Promise<void> {
  const response = await request.post(`${FAKE}/__promote_admin`, {
    params: { email: user.email },
    headers: { apikey: SERVICE_KEY },
  });
  expect(response.status()).toBe(204);
}

/** Makes `a` and `b` accepted contacts of each other. */
export async function befriend(
  request: APIRequestContext,
  a: TestUser,
  b: TestUser,
): Promise<void> {
  const sent = await request.post(`${API}/api/v1/contacts/requests`, {
    headers: bearer(a),
    data: { user_id: b.userId, note: null },
  });
  expect(sent.status(), await sent.text()).toBeLessThan(300);
  const incoming = await request.get(`${API}/api/v1/contacts/requests`, {
    headers: bearer(b),
    params: { direction: "incoming", page: "1", page_size: "20" },
  });
  const requestId = ((await incoming.json()) as { data: { id: string }[] }).data[0]?.id;
  const accepted = await request.post(`${API}/api/v1/contacts/requests/${requestId}/accept`, {
    headers: bearer(b),
    data: {},
  });
  expect(accepted.status(), await accepted.text()).toBe(200);
}

/** Verifies a mobile number through the simulated inbox (no real SMS is involved). */
export async function verifyPhone(
  request: APIRequestContext,
  user: TestUser,
  mobile: string = fictionalMobile(),
): Promise<string> {
  const started = await request.post(`${API}/api/v1/users/me/phone`, {
    headers: bearer(user),
    data: { phone_number: mobile },
  });
  expect(started.status(), await started.text()).toBeLessThan(300);
  const inbox = await request.get(`${API}/api/v1/users/me/phone/simulated-inbox`, {
    headers: bearer(user),
  });
  const items = ((await inbox.json()) as { data: { body: string }[] }).data;
  const code = /\b(\d{6})\b/.exec(items[0]?.body ?? "")?.[1];
  expect(code, "simulated inbox should hold a 6-digit code").toBeDefined();
  const confirmed = await request.post(`${API}/api/v1/users/me/phone/verify`, {
    headers: bearer(user),
    data: { phone_number: mobile, code },
  });
  expect(confirmed.status(), await confirmed.text()).toBe(200);
  return mobile;
}

/** Signs a user into the browser: the login response sets the refresh cookie in the page's jar. */
export async function signInBrowser(page: Page, user: TestUser, path = "/"): Promise<void> {
  const login = await page.request.post(`${API}/api/v1/auth/login`, {
    data: { email: user.email, password: PASSWORD },
  });
  expect(login.status(), await login.text()).toBe(200);
  await page.goto(path);
}

export async function apiGet<T>(
  request: APIRequestContext,
  user: TestUser,
  path: string,
  params?: Record<string, string>,
): Promise<T> {
  const response = await request.get(`${API}${path}`, { headers: bearer(user), params });
  expect(response.status(), `${path}: ${await response.text()}`).toBeLessThan(300);
  return (await response.json()) as T;
}

export async function apiPost(
  request: APIRequestContext,
  user: TestUser,
  path: string,
  data: unknown,
  headers: Record<string, string> = {},
) {
  return request.post(`${API}${path}`, { headers: { ...bearer(user), ...headers }, data });
}

export async function apiPut(
  request: APIRequestContext,
  user: TestUser,
  path: string,
  data: unknown,
) {
  return request.put(`${API}${path}`, { headers: bearer(user), data });
}

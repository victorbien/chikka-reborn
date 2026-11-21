/** Shared by the live journey tests: browser-like clients that talk to a real backend. */
import { createAdminApi } from "@/features/admin/api";
import { createAdminSmsApi } from "@/features/sms/admin/api";
import { createAiApi } from "@/features/ai/api";
import { createAuthApi } from "@/features/auth/api";
import { createChatApi } from "@/features/chat/api";
import { createContactsApi } from "@/features/contacts/api";
import { createCreditsApi } from "@/features/credits/api";
import { createNotificationsApi } from "@/features/notifications/api";
import { createProfileApi } from "@/features/profile/api";
import { createSmsApi } from "@/features/sms/api";
import { ApiClient } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";
import { SessionStore } from "@/lib/auth/session";
import { RealtimeClient, realtimeUrl, type ServerEvent } from "@/lib/realtime/client";

export const API = process.env.LIVE_API_URL;
export const FAKE = process.env.LIVE_FAKE_SUPABASE_URL;
export const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";
export const PASSWORD = "Correct-Horse-7";

/** Minimal browser-like cookie jar: honours Path and deletion (Max-Age=0). */
function cookieFetch(): typeof fetch {
  const jar = new Map<string, { value: string; path: string }>();
  return async (input, init) => {
    const url = new URL(String(input));
    const headers = new Headers(init?.headers);
    const cookies = [...jar.entries()]
      .filter(([, c]) => url.pathname.startsWith(c.path))
      .map(([name, c]) => `${name}=${c.value}`);
    if (cookies.length && init?.credentials === "include")
      headers.set("Cookie", cookies.join("; "));
    const response = await fetch(url, { ...init, headers });
    for (const raw of response.headers.getSetCookie()) {
      const [pair = "", ...attributes] = raw.split(";").map((part) => part.trim());
      const [name = "", value = ""] = pair.split("=");
      const path = attributes.find((a) => a.toLowerCase().startsWith("path="))?.slice(5) ?? "/";
      const expired =
        attributes.some((a) => /^max-age=0$/i.test(a)) || value === "" || value === '""';
      if (expired) jar.delete(name);
      else jar.set(name, { value, path });
    }
    return response;
  };
}

export async function emailToken(to: string, kind: "signup" | "recovery"): Promise<string> {
  const response = await fetch(`${FAKE}/__outbox?to=${encodeURIComponent(to)}`);
  const emails = (await response.json()) as { kind: string; token_hash: string }[];
  const match = emails.filter((e) => e.kind === kind).at(-1);
  if (!match) throw new Error(`no ${kind} email for ${to}`);
  return match.token_hash;
}

export async function errorOf(promise: Promise<unknown>) {
  try {
    await promise;
  } catch (error) {
    if (isApiError(error)) return error;
    throw error;
  }
  throw new Error("expected the request to fail");
}

export async function until<T>(
  read: () => Promise<T | null | undefined | false>,
  what: string,
  timeoutMs = 15_000,
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const value = await read();
    if (value) return value;
    if (Date.now() > deadline) throw new Error(`timed out waiting for ${what}`);
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}

let counter = 0;
export function uniqueName(prefix: string): string {
  counter += 1;
  return `${prefix}${Date.now().toString(36)}${counter}`;
}

/** A signed-in browser: its own cookies, session and one client per feature API. */
export interface Person {
  email: string;
  username: string;
  displayName: string;
  userId: string;
  session: SessionStore;
  auth: ReturnType<typeof createAuthApi>;
  profile: ReturnType<typeof createProfileApi>;
  contacts: ReturnType<typeof createContactsApi>;
  chat: ReturnType<typeof createChatApi>;
  sms: ReturnType<typeof createSmsApi>;
  ai: ReturnType<typeof createAiApi>;
  credits: ReturnType<typeof createCreditsApi>;
  notifications: ReturnType<typeof createNotificationsApi>;
  admin: ReturnType<typeof createAdminApi>;
  adminSms: ReturnType<typeof createAdminSmsApi>;
  client: ApiClient;
  /** Opens the real-time socket the way the app does and collects every event. */
  listen: () => Promise<{ events: ServerEvent[]; stop: () => void }>;
}

export function newBrowser(): Omit<Person, "email" | "username" | "displayName" | "userId"> {
  const client = new ApiClient({ baseUrl: API ?? "", fetchImpl: cookieFetch() });
  const session = new SessionStore();
  session.attach(client);
  return {
    session,
    client,
    auth: createAuthApi(client),
    profile: createProfileApi(client),
    contacts: createContactsApi(client),
    chat: createChatApi(client),
    sms: createSmsApi(client),
    ai: createAiApi(client),
    credits: createCreditsApi(client),
    notifications: createNotificationsApi(client),
    admin: createAdminApi(client),
    adminSms: createAdminSmsApi(client),
    listen: async () => {
      const events: ServerEvent[] = [];
      const socket = new RealtimeClient({
        url: realtimeUrl(API ?? ""),
        getToken: () => session.getSnapshot().accessToken,
        refreshToken: () => session.refresh(),
      });
      socket.subscribe((event) => events.push(event));
      socket.start();
      await until(async () => socket.getStatus() === "open", "the real-time socket to open");
      return { events, stop: () => socket.stop() };
    },
  };
}

/** Registers, confirms the email link and finishes the profile, as a new user would. */
export async function signUp(label: string): Promise<Person> {
  const browser = newBrowser();
  const username = uniqueName(label).toLowerCase().slice(0, 20);
  const email = `${username}@example.com`;
  const displayName = `${label} Tester`;
  await browser.auth.register({
    email,
    display_name: displayName,
    password: PASSWORD,
    accept_terms: true,
  });
  const tokens = await browser.auth.verifyEmail(await emailToken(email, "signup"));
  browser.session.signIn(tokens);
  await browser.profile.completeOnboarding({
    username,
    display_name: displayName,
    country_code: "PH",
    language: "en",
    time_zone: "Asia/Manila",
    ui_mode: "modern",
  });
  const me = await browser.profile.getMe();
  return { ...browser, email, username, displayName, userId: me.id };
}

export async function promoteToAdmin(person: Person): Promise<void> {
  const response = await fetch(
    `${FAKE}/__promote_admin?email=${encodeURIComponent(person.email)}`,
    {
      method: "POST",
      headers: { apikey: SERVICE_KEY },
    },
  );
  if (response.status !== 204) throw new Error(`promotion failed: ${response.status}`);
}

let adminPromise: Promise<Person> | null = null;
/** One administrator for the whole run: registration is limited to 10 per hour per address. */
export function sharedAdmin(): Promise<Person> {
  adminPromise ??= signUp("root").then(async (person) => {
    await promoteToAdmin(person);
    return person;
  });
  return adminPromise;
}

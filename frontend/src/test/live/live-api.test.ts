// @vitest-environment node
/**
 * End-to-end check of the frontend service layer against a running backend.
 * Started by scripts/e2e-local.ps1 (PGlite + fake Supabase + uvicorn). Skipped otherwise.
 * Uses fictional data only; SMS runs in simulation mode.
 */
import { describe, expect, it } from "vitest";
import { createAuthApi } from "@/features/auth/api";
import { createProfileApi } from "@/features/profile/api";
import { ApiClient } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";
import { SessionStore } from "@/lib/auth/session";

const API = process.env.LIVE_API_URL;
const FAKE = process.env.LIVE_FAKE_SUPABASE_URL;

// 1x1 PNG
const PNG = Uint8Array.from(
  atob(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  ),
  (c) => c.charCodeAt(0),
);

/** Minimal browser-like cookie jar: honours Path and deletion (Max-Age=0). */
function cookieFetch() {
  const jar = new Map<string, { value: string; path: string }>();
  const fetchImpl: typeof fetch = async (input, init) => {
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
  return { fetchImpl, jar };
}

async function emailToken(to: string, kind: "signup" | "recovery"): Promise<string> {
  const response = await fetch(`${FAKE}/__outbox?to=${encodeURIComponent(to)}`);
  const emails = (await response.json()) as { kind: string; token_hash: string }[];
  const match = emails.filter((e) => e.kind === kind).at(-1);
  if (!match) throw new Error(`no ${kind} email for ${to}`);
  return match.token_hash;
}

async function errorOf(promise: Promise<unknown>) {
  try {
    await promise;
  } catch (error) {
    if (isApiError(error)) return error;
    throw error;
  }
  throw new Error("expected the request to fail");
}

describe.skipIf(!API || !FAKE)("live API: authentication and user management", () => {
  const email = `live-${Date.now()}@example.com`;
  const password = "Correct-Horse-7";
  const newPassword = "Brand-New-Pass-2";
  const { fetchImpl, jar } = cookieFetch();
  const client = new ApiClient({ baseUrl: API ?? "", fetchImpl });
  const session = new SessionStore();
  session.attach(client);
  const auth = createAuthApi(client);
  const profile = createProfileApi(client);

  it("serves health and the API documentation", async () => {
    const health = await fetch(`${API}/api/v1/health`).then((r) => r.json());
    expect(health).toMatchObject({ status: "ok", sms_mode: "simulation", database: "ok" });
    expect((await fetch(`${API}/docs`)).status).toBe(200);
  });

  it("registers, refuses sign-in until the email is confirmed, then verifies", async () => {
    const registered = await auth.register({
      email,
      display_name: "Live Tester",
      password,
      accept_terms: true,
    });
    expect(registered.message).toMatch(/confirm/i);

    const unverified = await errorOf(auth.login({ email, password }));
    expect(unverified.code).toBe("email_not_verified");

    const tokens = await auth.verifyEmail(await emailToken(email, "signup"));
    session.signIn(tokens);
    expect(jar.has("chikka_refresh")).toBe(true);
    const me = await profile.getMe();
    expect(me).toMatchObject({
      email,
      status: "active",
      email_verified: true,
      onboarding_completed: false,
    });
  });

  it("rejects wrong credentials identically for known and unknown emails", async () => {
    const known = await errorOf(auth.login({ email, password: "Wrong-Pass-1" }));
    const unknown = await errorOf(
      auth.login({ email: `nobody-${Date.now()}@example.com`, password: "Wrong-Pass-1" }),
    );
    expect([known.status, known.code, known.message]).toEqual([
      unknown.status,
      unknown.code,
      unknown.message,
    ]);
    expect(known.status).toBe(401);
  });

  it("completes onboarding and edits the profile", async () => {
    const onboarded = await profile.completeOnboarding({
      username: `live_${Date.now() % 1_000_000}`,
      display_name: "Live Tester",
      country_code: "PH",
      language: "fil",
      time_zone: "Asia/Manila",
      ui_mode: "classic",
    });
    expect(onboarded.onboarding_completed).toBe(true);
    const updated = await profile.updateMe({ bio: "Testing <b>live</b>", theme: "dark" });
    expect(updated).toMatchObject({ bio: "Testing live", theme: "dark", ui_mode: "classic" });
    const invalid = await errorOf(profile.updateMe({ country_code: "ZZ" }));
    expect(invalid.status).toBe(422);
  });

  it("uploads a photo, keeps presence alive and lists sessions", async () => {
    const upload = await profile.uploadAvatar(new File([PNG], "me.png", { type: "image/png" }));
    expect(upload.avatar_url).toContain("/storage/v1/object/sign/avatars/");
    const presence = await profile.heartbeat(false);
    expect(presence.status).toBe("online");
    const sessions = await auth.listSessions();
    expect(sessions.filter((s) => s.current)).toHaveLength(1);
  });

  it("verifies a mobile number with a SIMULATED code", async () => {
    const number = `+63917${String(Date.now()).slice(-7)}`;
    const started = await profile.startPhone(number);
    expect(started.verification_mode).toBe("simulated");
    const [message] = await profile.simulatedInbox();
    expect(message?.label).toBe("SIMULATED");
    const code = /code is (\d{6})/.exec(message?.body ?? "")?.[1] ?? "";
    const status = await profile.confirmPhone(number, code);
    expect(status).toMatchObject({ verified: true, verification_mode: "simulated" });
  });

  it("renews the access token from the httpOnly cookie", async () => {
    const before = session.getSnapshot().accessToken;
    const renewed = await session.refresh();
    expect(renewed).toBeTruthy();
    expect(renewed).not.toBe(before);
    expect((await profile.getMe()).email).toBe(email);
  });

  it("resets the password and ends every existing session", async () => {
    await auth.requestPasswordReset(email);
    await auth.confirmPasswordReset(await emailToken(email, "recovery"), newPassword, newPassword);
    // The old access token is revoked; the client's one refresh attempt also fails.
    const revoked = await errorOf(profile.getMe());
    expect(revoked.status).toBe(401);
    expect(session.getSnapshot().status).toBe("signed-out");

    expect((await errorOf(auth.login({ email, password }))).code).toBe("invalid_credentials");
    session.signIn(await auth.login({ email, password: newPassword }));
    expect((await profile.getMe()).email).toBe(email);
  });

  it("signs out and the token stops working at once", async () => {
    await auth.logout("local");
    const after = await errorOf(profile.getMe());
    expect(after.status).toBe(401);
    session.signOut();
  });

  it("deletes the account after re-authentication", async () => {
    session.signIn(await auth.login({ email, password: newPassword }));
    const wrong = await errorOf(auth.deleteAccount("Wrong-Pass-1"));
    expect(wrong.code).toBe("reauthentication_failed");

    const deleted = await auth.deleteAccount(newPassword);
    expect(deleted.deleted_at).toBeTruthy();
    expect((await errorOf(profile.getMe())).status).toBe(401);
    expect((await errorOf(auth.login({ email, password: newPassword }))).code).toBe(
      "invalid_credentials",
    );
  });
});

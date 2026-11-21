import { API, PASSWORD } from "./support/stack";
import { bearer, createUser, uniqueName } from "./support/api";
import { decodeClaims, signJwt, unsignedJwt, webhookSignature } from "./support/forge";
import { browserUser, newPerson } from "./support/people";
import { expect, test } from "./support/fixtures";

const PROTECTED = [
  "/api/v1/users/me",
  "/api/v1/contacts",
  "/api/v1/conversations",
  "/api/v1/sms/conversations",
  "/api/v1/notifications",
  "/api/v1/credits",
  "/api/v1/ai/status",
  "/api/v1/admin/dashboard",
];

// A real PNG signature followed by padding: valid type, but over the 2 MB avatar limit.
const PNG_HEAD = Buffer.from("89504e470d0a1a0a", "hex");
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

test.describe("unauthorised access", () => {
  test("every protected endpoint refuses anonymous, malformed, unsigned and wrongly signed tokens", async ({
    request,
  }) => {
    const user = await createUser(request, "tok");
    const claims = decodeClaims(user.accessToken);
    const variants: Record<string, Record<string, string>> = {
      anonymous: {},
      garbage: { Authorization: "Bearer not-a-token" },
      "wrong scheme": { Authorization: `Basic ${user.accessToken}` },
      "alg none": { Authorization: `Bearer ${unsignedJwt(claims)}` },
      "wrong secret": {
        Authorization: `Bearer ${signJwt(claims, "a-different-secret-of-at-least-32-bytes!!")}`,
      },
      expired: {
        Authorization: `Bearer ${signJwt({ ...claims, exp: Math.floor(Date.now() / 1000) - 60 })}`,
      },
    };
    for (const [label, headers] of Object.entries(variants)) {
      for (const path of PROTECTED) {
        const response = await request.get(`${API}${path}`, { headers });
        expect(response.status(), `${label} -> ${path}`).toBe(401);
        const body = (await response.json()) as { error?: { code: string }; request_id?: string };
        expect(body.error?.code, `${label} -> ${path}`).toBeTruthy();
        expect(await response.text()).not.toMatch(/Traceback|File ".*\.py"/);
      }
    }
  });

  test("signed-out visitors are sent to sign-in from every private page", async ({ page }) => {
    for (const path of [
      "/messages",
      "/contacts",
      "/sms",
      "/credits",
      "/admin",
      "/settings/profile",
    ]) {
      await page.goto(path);
      await expect(page, path).toHaveURL(/\/auth\/sign-in/);
      await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
    }
  });
});

test.describe("cross-user data access", () => {
  test("another person cannot read a contact, conversation, notification or SMS thread", async ({
    browser,
    page,
  }) => {
    const ana = await browserUser(page, "xua");
    const ben = await newPerson(browser, "xub");
    const eve = await newPerson(browser, "xue");
    await ana.befriend(ben.user);

    const contacts = await ana.api.get<{ data: { id: string }[] }>("/api/v1/contacts");
    const contactId = contacts.data[0]?.id ?? "";
    const opened = await ana.api.post("/api/v1/conversations", { user_id: ben.user.userId });
    const conversationId = ((await opened.json()) as { data: { id: string } }).data.id;
    await ana.api.post(`/api/v1/conversations/${conversationId}/messages`, {
      client_message_id: crypto.randomUUID(),
      body: "for Ben only",
    });
    const feed = await ben.api.get<{ data: { id: string }[] }>("/api/v1/notifications");
    const notificationId = feed.data[0]?.id ?? "";

    await ana.verifyPhone();
    const sent = await ana.api.post(
      "/api/v1/sms/messages",
      { to: "+639181234567", country_code: "PH", body: "private sms", confirmed: true },
      { "Idempotency-Key": crypto.randomUUID() },
    );
    // Consent is required first, so grant it and send again.
    await ana.api.put("/api/v1/sms/consents", {
      to: "+639181234567",
      country_code: "PH",
      decision: "granted",
    });
    const sms = await ana.api.post(
      "/api/v1/sms/messages",
      { to: "+639181234567", country_code: "PH", body: "private sms", confirmed: true },
      { "Idempotency-Key": crypto.randomUUID() },
    );
    expect(sent.status()).toBeGreaterThanOrEqual(400);
    expect(sms.status(), await sms.text()).toBeLessThan(300);
    const smsConversation = ((await sms.json()) as { data: { conversation_id: string } }).data
      .conversation_id;

    const hidden = [403, 404];
    const get = (path: string) => page.request.get(`${API}${path}`, { headers: bearer(eve.user) });
    expect(hidden).toContain((await get(`/api/v1/contacts/${contactId}`)).status());
    expect(hidden).toContain((await get(`/api/v1/conversations/${conversationId}`)).status());
    expect(hidden).toContain(
      (await get(`/api/v1/conversations/${conversationId}/messages`)).status(),
    );
    expect(hidden).toContain(
      (await get(`/api/v1/sms/conversations/${smsConversation}/messages`)).status(),
    );
    const read = await eve.api.post(`/api/v1/notifications/${notificationId}/read`, {});
    expect(hidden).toContain(read.status());

    // Lists are scoped to the caller, so Eve sees none of it.
    for (const path of [
      "/api/v1/contacts",
      "/api/v1/conversations",
      "/api/v1/sms/conversations",
      "/api/v1/notifications",
    ]) {
      const body = await eve.api.get<{ data: unknown[] }>(path);
      expect(JSON.stringify(body.data), path).not.toContain("for Ben only");
      expect(body.data, path).toHaveLength(0);
    }
    // Ben's own notification still works for Ben.
    expect(
      (await ben.api.post(`/api/v1/notifications/${notificationId}/read`, {})).status(),
    ).toBeLessThan(300);
  });
});

test.describe("role escalation", () => {
  test("a normal user cannot become an administrator by asking, or by editing their token", async ({
    request,
  }) => {
    const user = await createUser(request, "esc");
    const adminOnly = `${API}/api/v1/admin/dashboard`;
    expect((await request.get(adminOnly, { headers: bearer(user) })).status()).toBe(403);

    // Asking: the profile update ignores or rejects a role field.
    const patch = await request.patch(`${API}/api/v1/users/me`, {
      headers: bearer(user),
      data: { role: "admin", display_name: "Sneaky" },
    });
    expect(patch.status()).toBeLessThan(500);
    const me = (await (
      await request.get(`${API}/api/v1/users/me`, { headers: bearer(user) })
    ).json()) as {
      data: { role: string };
    };
    expect(me.data.role).toBe("user");

    // Editing: a token signed with the real secret that claims admin is still not trusted,
    // because the role is read from the database on every request.
    const claims = decodeClaims(user.accessToken);
    const forged = signJwt({
      ...claims,
      role: "admin",
      user_role: "admin",
      app_metadata: { role: "admin" },
    });
    const response = await request.get(adminOnly, {
      headers: { Authorization: `Bearer ${forged}` },
    });
    expect(response.status()).toBe(403);
    const asAdmin = await request.post(`${API}/api/v1/admin/sms/simulate/inbound`, {
      headers: { Authorization: `Bearer ${forged}` },
      data: { from_phone: "+639175550123", body: "x", to_number: null, replay_id: null },
    });
    expect(asAdmin.status()).toBe(403);
  });

  test("a token for someone else's session cannot be built by changing the subject", async ({
    request,
  }) => {
    const [ana, ben] = [await createUser(request, "sba"), await createUser(request, "sbb")];
    const claims = decodeClaims(ana.accessToken);
    // Wrong signature (the attacker lacks the secret): rejected outright.
    const swapped = signJwt(
      { ...claims, sub: ben.userId },
      "attacker-secret-attacker-secret-attacker",
    );
    const response = await request.get(`${API}/api/v1/users/me`, {
      headers: { Authorization: `Bearer ${swapped}` },
    });
    expect(response.status()).toBe(401);
  });
});

test.describe("webhook forgery", () => {
  const url = `${API}/api/v1/webhooks/mock/inbound`;
  const event = (id: string) =>
    JSON.stringify({
      kind: "inbound",
      event_id: id,
      from: "+639175550123",
      to: "+639175550124",
      body: "forged reply",
      received_at: new Date().toISOString(),
    });
  const post = (
    request: import("@playwright/test").APIRequestContext,
    body: string,
    headers: Record<string, string>,
  ) =>
    request.post(url, {
      data: Buffer.from(body),
      headers: { "content-type": "application/json", ...headers },
    });

  test("unsigned, wrongly signed, tampered and stale webhooks are rejected", async ({
    request,
  }) => {
    const body = event(`E2E-FORGE-${uniqueName("w")}`);
    const now = String(Math.floor(Date.now() / 1000));

    const unsigned = await post(request, body, {});
    expect([401, 403]).toContain(unsigned.status());

    const wrong = await post(request, body, {
      "x-mock-timestamp": now,
      "x-mock-signature": "0".repeat(64),
    });
    expect([401, 403]).toContain(wrong.status());

    const tampered = await post(request, body.replace("forged reply", "tampered"), {
      "x-mock-timestamp": now,
      "x-mock-signature": webhookSignature(now, body),
    });
    expect([401, 403]).toContain(tampered.status());

    const old = String(Math.floor(Date.now() / 1000) - 3600);
    const stale = await post(request, body, {
      "x-mock-timestamp": old,
      "x-mock-signature": webhookSignature(old, body),
    });
    expect([401, 403]).toContain(stale.status());

    // The same endpoint on another provider is not served at all.
    const twilio = await request.post(`${API}/api/v1/webhooks/twilio/inbound`, {
      data: "From=%2B1",
    });
    expect(twilio.status()).toBe(404);
    // No stack trace or internals leak from a rejected webhook.
    expect(await wrong.text()).not.toMatch(/Traceback|secret/i);
  });

  test("a correctly signed webhook is accepted once and a replay is harmless", async ({
    request,
  }) => {
    const body = event(`E2E-OK-${uniqueName("w")}`);
    const now = String(Math.floor(Date.now() / 1000));
    const headers = { "x-mock-timestamp": now, "x-mock-signature": webhookSignature(now, body) };
    const first = await post(request, body, headers);
    expect(first.status(), await first.text()).toBeLessThan(300);
    const replay = await post(request, body, headers);
    expect(replay.status()).toBeLessThan(300);
  });
});

test.describe("rate limits", () => {
  test("repeated wrong passwords lock the account, with Retry-After", async ({ request }) => {
    const user = await createUser(request, "lock");
    const attempt = (password: string) =>
      request.post(`${API}/api/v1/auth/login`, { data: { email: user.email, password } });
    for (let i = 0; i < 5; i += 1) {
      expect((await attempt("Wrong-Password-1")).status()).toBeLessThan(429);
    }
    const locked = await attempt(PASSWORD);
    expect(locked.status()).toBe(429);
    expect(Number(locked.headers()["retry-after"])).toBeGreaterThan(0);
    expect(((await locked.json()) as { error: { code: string } }).error.code).toBeTruthy();
  });

  test("sign-up is limited per address", async ({ request }) => {
    const statuses: number[] = [];
    for (let i = 0; i < 12; i += 1) {
      const name = uniqueName("flood");
      const response = await request.post(`${API}/api/v1/auth/register`, {
        data: {
          email: `${name}@example.com`,
          display_name: "Flood",
          password: PASSWORD,
          accept_terms: true,
        },
      });
      statuses.push(response.status());
      if (response.status() === 429) {
        expect(Number(response.headers()["retry-after"])).toBeGreaterThan(0);
        break;
      }
    }
    expect(statuses.at(-1)).toBe(429);
    expect(statuses.filter((s) => s === 202).length).toBeLessThanOrEqual(10);
  });
});

test.describe("sensitive data exposure", () => {
  test("responses never carry password data or tokens beyond the access token", async ({
    page,
  }) => {
    const user = await createUser(page.request, "exp");
    const me = await page.request.get(`${API}/api/v1/users/me`, { headers: bearer(user) });
    const text = await me.text();
    expect(text).not.toMatch(/password|hash|refresh_token|service_role|secret/i);

    const login = await page.request.post(`${API}/api/v1/auth/login`, {
      data: { email: user.email, password: PASSWORD },
    });
    const loginBody = await login.text();
    expect(loginBody).not.toContain("refresh_token");
    expect(loginBody).not.toContain(PASSWORD);

    const cookie = (await page.context().cookies()).find((c) => c.name === "chikka_refresh");
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.sameSite).toBe("Lax");
    expect(cookie?.path).toBe("/api/v1/auth");

    // Another person's profile as seen by a stranger does not expose email or phone.
    const stranger = await createUser(page.request, "str");
    const search = await page.request.get(`${API}/api/v1/contacts/search`, {
      headers: bearer(stranger),
      params: { q: user.username },
    });
    expect(await search.text()).not.toContain(user.email);
  });

  test("errors use one safe envelope and an unknown origin is not allowed by CORS", async ({
    request,
  }) => {
    const missing = await request.get(`${API}/api/v1/does-not-exist`);
    expect(missing.status()).toBe(404);
    const body = await missing.text();
    expect(body).not.toMatch(/Traceback|\.py"|sqlalchemy|asyncpg/i);

    const preflight = await request.fetch(`${API}/api/v1/auth/refresh`, {
      method: "OPTIONS",
      headers: {
        Origin: "https://evil.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-chikka-csrf,content-type",
      },
    });
    expect(preflight.headers()["access-control-allow-origin"]).not.toBe("https://evil.example");
  });
});

test.describe("invalid input", () => {
  test("malformed, oversize and hostile input is rejected cleanly", async ({ request }) => {
    const user = await createUser(request, "inp");
    const headers = { ...bearer(user), "content-type": "application/json" };

    const badJson = await request.post(`${API}/api/v1/conversations`, {
      headers,
      data: "{not json",
    });
    expect(badJson.status()).toBe(422);
    expect(((await badJson.json()) as { error: { code: string } }).error.code).toBeTruthy();

    const wrongType = await request.post(`${API}/api/v1/contacts/requests`, {
      headers,
      data: { user_id: 12345 },
    });
    expect(wrongType.status()).toBe(422);

    const badPhone = await request.post(`${API}/api/v1/users/me/phone`, {
      headers,
      data: { phone_number: "12; DROP TABLE" },
    });
    expect(badPhone.status()).toBe(422);

    const badEmail = await request.post(`${API}/api/v1/auth/register`, {
      data: { email: "not-an-email", display_name: "X", password: PASSWORD, accept_terms: true },
    });
    expect(badEmail.status()).toBe(422);

    const noTerms = await request.post(`${API}/api/v1/auth/register`, {
      data: {
        email: "terms@example.com",
        display_name: "X",
        password: PASSWORD,
        accept_terms: false,
      },
    });
    expect(noTerms.status()).toBe(422);

    // Injection strings are treated as plain text everywhere they are accepted.
    for (const q of [
      "' OR 1=1 --",
      '"; DROP TABLE profiles; --',
      "%",
      "\u0000",
      "a".repeat(5000),
    ]) {
      const response = await request.get(`${API}/api/v1/contacts/search`, {
        headers: bearer(user),
        params: { q },
      });
      expect(response.status(), q.slice(0, 12)).toBeLessThan(500);
    }
    const stillThere = await request.get(`${API}/api/v1/users/me`, { headers: bearer(user) });
    expect(stillThere.status()).toBe(200);
  });

  test("chat rejects an empty and an over-long message", async ({ browser, page }) => {
    const ana = await browserUser(page, "val");
    const ben = await newPerson(browser, "vlb");
    await ana.befriend(ben.user);
    const opened = await ana.api.post("/api/v1/conversations", { user_id: ben.user.userId });
    const id = ((await opened.json()) as { data: { id: string } }).data.id;
    const send = (body: string) =>
      ana.api.post(`/api/v1/conversations/${id}/messages`, {
        client_message_id: crypto.randomUUID(),
        body,
      });
    expect((await send("")).status()).toBe(422);
    expect((await send("   ")).status()).toBe(422);
    expect((await send("x".repeat(50_000))).status()).toBe(422);
    expect((await send("fine")).status()).toBeLessThan(300);
  });
});

test.describe("file upload restrictions", () => {
  test("avatars accept images only, up to 2 MB, and reject disguised files", async ({
    request,
  }) => {
    const user = await createUser(request, "upl");
    const upload = (name: string, mimeType: string, buffer: Buffer) =>
      request.post(`${API}/api/v1/users/me/avatar`, {
        headers: bearer(user),
        multipart: { avatar: { name, mimeType, buffer } },
      });

    expect((await upload("a.png", "image/png", TINY_PNG)).status()).toBeLessThan(300);

    const rejected: [string, string, Buffer][] = [
      ["notes.txt", "text/plain", Buffer.from("plain text")],
      [
        "script.svg",
        "image/svg+xml",
        Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'),
      ],
      ["evil.png", "image/png", Buffer.from("MZ\x90\x00 this is not an image")],
      ["empty.png", "image/png", Buffer.alloc(0)],
      ["huge.png", "image/png", Buffer.concat([PNG_HEAD, Buffer.alloc(2 * 1024 * 1024 + 10)])],
    ];
    for (const [name, mime, data] of rejected) {
      const response = await upload(name, mime, data);
      expect(response.status(), name).toBeGreaterThanOrEqual(400);
      expect(response.status(), name).toBeLessThan(500);
    }
  });

  test("chat attachments reject executables and oversize files", async ({ browser, page }) => {
    const ana = await browserUser(page, "att");
    const ben = await newPerson(browser, "atb");
    await ana.befriend(ben.user);
    const opened = await ana.api.post("/api/v1/conversations", { user_id: ben.user.userId });
    const id = ((await opened.json()) as { data: { id: string } }).data.id;
    const upload = (name: string, mimeType: string, buffer: Buffer) =>
      page.request.post(`${API}/api/v1/conversations/${id}/attachments`, {
        headers: bearer(ana.user),
        multipart: { file: { name, mimeType, buffer } },
      });

    expect((await upload("ok.png", "image/png", TINY_PNG)).status()).toBeLessThan(300);
    for (const [name, mime, data] of [
      ["run.exe", "application/octet-stream", Buffer.from("MZ\x90\x00")],
      ["page.html", "text/html", Buffer.from("<script>alert(1)</script>")],
      ["fake.pdf", "application/pdf", Buffer.from("not really a pdf")],
      ["huge.png", "image/png", Buffer.concat([PNG_HEAD, Buffer.alloc(10 * 1024 * 1024 + 10)])],
    ] as [string, string, Buffer][]) {
      const response = await upload(name, mime, data);
      expect(response.status(), name).toBeGreaterThanOrEqual(400);
      expect(response.status(), name).toBeLessThan(500);
    }
  });
});

test.describe("session handling", () => {
  test("refresh needs the CSRF header, and logging out ends the session everywhere", async ({
    page,
  }) => {
    const user = await createUser(page.request, "ses");
    const refresh = (headers: Record<string, string> = {}) =>
      page.request.post(`${API}/api/v1/auth/refresh`, { headers });

    expect((await refresh()).status()).toBe(403);
    const ok = await refresh({ "X-Chikka-CSRF": "1" });
    expect(ok.status(), await ok.text()).toBe(200);
    const token = ((await ok.json()) as { data: { access_token: string } }).data.access_token;
    expect(
      (
        await page.request.get(`${API}/api/v1/users/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
      ).status(),
    ).toBe(200);

    const out = await page.request.post(`${API}/api/v1/auth/logout`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { scope: "global" },
    });
    expect(out.status()).toBe(204);
    expect(
      (
        await page.request.get(`${API}/api/v1/users/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
      ).status(),
    ).toBe(401);
    expect([400, 401, 403]).toContain((await refresh({ "X-Chikka-CSRF": "1" })).status());
    expect(user.userId).not.toBe("");
  });

  test("signing out of other devices ends only the other devices", async ({ browser, page }) => {
    const user = await createUser(page.request, "dev");
    const other = await browser.newContext();
    const login = await other.request.post(`${API}/api/v1/auth/login`, {
      data: { email: user.email, password: PASSWORD },
    });
    expect(login.status()).toBe(200);

    const mine = await page.request.post(`${API}/api/v1/auth/refresh`, {
      headers: { "X-Chikka-CSRF": "1" },
    });
    const token = ((await mine.json()) as { data: { access_token: string } }).data.access_token;
    const revoke = await page.request.post(`${API}/api/v1/auth/sessions/revoke-others`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {},
    });
    expect(revoke.status(), await revoke.text()).toBeLessThan(300);

    expect(
      (
        await other.request.post(`${API}/api/v1/auth/refresh`, {
          headers: { "X-Chikka-CSRF": "1" },
        })
      ).status(),
    ).toBeGreaterThanOrEqual(400);
    expect(
      (
        await page.request.post(`${API}/api/v1/auth/refresh`, { headers: { "X-Chikka-CSRF": "1" } })
      ).status(),
    ).toBe(200);
    await other.close();
  });

  test("a browser whose session was revoked elsewhere is returned to sign-in", async ({
    browser,
    page,
  }) => {
    const user = await createUser(page.request, "rvk");
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();

    const other = await browser.newContext();
    const login = await other.request.post(`${API}/api/v1/auth/login`, {
      data: { email: user.email, password: PASSWORD },
    });
    const token = ((await login.json()) as { data: { access_token: string } }).data.access_token;
    await other.request.post(`${API}/api/v1/auth/logout`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { scope: "global" },
    });
    await other.close();

    await page.reload();
    await expect(page).toHaveURL(/\/auth\/sign-in/);
  });
});

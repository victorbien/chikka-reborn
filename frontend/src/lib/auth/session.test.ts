import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "@/lib/api/client";
import { SessionStore } from "@/lib/auth/session";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const tokens = (token: string) =>
  json(200, {
    data: { access_token: token, token_type: "bearer", expires_in: 60 },
    request_id: "r",
  });
const expired = () =>
  json(401, { error: { code: "token_expired", message: "expired", details: {} }, request_id: "r" });

function setup(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  const fetchImpl = vi.fn<typeof fetch>(async (input, init) => handler(String(input), init));
  const client = new ApiClient({ baseUrl: "http://api.test", fetchImpl });
  const store = new SessionStore();
  store.attach(client);
  return { client, store, fetchImpl };
}

describe("SessionStore", () => {
  it("starts unknown, then signs in from the refresh cookie", async () => {
    const { store, fetchImpl } = setup(() => tokens("t1"));
    expect(store.getSnapshot().status).toBe("unknown");
    await expect(store.refresh()).resolves.toBe("t1");
    expect(store.getSnapshot()).toEqual({ status: "signed-in", accessToken: "t1" });
    const init = fetchImpl.mock.calls[0]?.[1];
    expect((init?.headers as Record<string, string>)["X-Chikka-CSRF"]).toBe("1");
    expect(init?.credentials).toBe("include");
  });

  it("signs out when the refresh fails", async () => {
    const { store } = setup(() =>
      json(401, { error: { code: "not_authenticated", message: "x" }, request_id: "r" }),
    );
    await expect(store.refresh()).resolves.toBeNull();
    expect(store.getSnapshot().status).toBe("signed-out");
  });

  it("shares one refresh between concurrent callers", async () => {
    const { store, fetchImpl } = setup(() => tokens("t1"));
    await Promise.all([store.refresh(), store.refresh(), store.refresh()]);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("notifies subscribers only on real changes", () => {
    const { store } = setup(() => tokens("t1"));
    const listener = vi.fn();
    store.subscribe(listener);
    store.signOut();
    store.signOut();
    expect(listener).toHaveBeenCalledTimes(1);
  });
});

describe("ApiClient with a session", () => {
  it("retries once with a fresh token after an expired-token 401", async () => {
    let dataCalls = 0;
    const { client, store, fetchImpl } = setup((url, init) => {
      if (url.endsWith("/auth/refresh")) return tokens("fresh");
      dataCalls += 1;
      const auth = (init?.headers as Record<string, string>).Authorization;
      return auth === "Bearer fresh" ? json(200, { ok: true }) : expired();
    });
    store.signIn({ access_token: "stale", token_type: "bearer", expires_in: 1 });
    await expect(client.get("/api/v1/users/me")).resolves.toEqual({ ok: true });
    expect(dataCalls).toBe(2);
    expect(fetchImpl).toHaveBeenCalledTimes(3);
  });

  it("does not loop when the retried request also fails", async () => {
    const { client, store, fetchImpl } = setup((url) =>
      url.endsWith("/auth/refresh") ? tokens("fresh") : expired(),
    );
    store.signIn({ access_token: "stale", token_type: "bearer", expires_in: 1 });
    await expect(client.get("/api/v1/users/me")).rejects.toMatchObject({ status: 401 });
    expect(fetchImpl).toHaveBeenCalledTimes(3);
  });

  it("never refreshes for wrong credentials or when signed out", async () => {
    const wrong = () =>
      json(401, { error: { code: "invalid_credentials", message: "x" }, request_id: "r" });
    const { client, store, fetchImpl } = setup(wrong);
    store.signIn({ access_token: "t", token_type: "bearer", expires_in: 60 });
    await expect(
      client.post("/api/v1/auth/login", {}, { skipAuthRefresh: true }),
    ).rejects.toMatchObject({ code: "invalid_credentials" });
    await expect(client.get("/api/v1/x")).rejects.toMatchObject({ code: "invalid_credentials" });
    expect(fetchImpl).toHaveBeenCalledTimes(2);

    store.signOut();
    const second = setup(expired);
    await expect(second.client.get("/api/v1/x")).rejects.toMatchObject({ status: 401 });
    expect(second.fetchImpl).toHaveBeenCalledTimes(1);
  });
});

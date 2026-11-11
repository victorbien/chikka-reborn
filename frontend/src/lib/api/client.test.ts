import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function makeClient(fetchImpl: typeof fetch) {
  return new ApiClient({ baseUrl: "http://api.test/", fetchImpl });
}

describe("ApiClient", () => {
  it("returns parsed JSON and builds the URL with query parameters", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ ok: true }));
    const result = await makeClient(fetchImpl).get<{ ok: boolean }>("/api/v1/health", {
      query: { page: 2, skip: undefined },
    });
    expect(result).toEqual({ ok: true });
    expect(fetchImpl.mock.calls[0]?.[0]).toBe("http://api.test/api/v1/health?page=2");
  });

  it("sends the bearer token and idempotency key when provided", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({}));
    const client = makeClient(fetchImpl);
    client.setTokenProvider(() => "token-123");
    await client.request("/x", { method: "POST", body: { a: 1 }, idempotencyKey: "key-1" });
    const init = fetchImpl.mock.calls[0]?.[1];
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer token-123");
    expect(headers["Idempotency-Key"]).toBe("key-1");
    expect(init?.body).toBe('{"a":1}');
  });

  it("omits the Authorization header when there is no token", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({}));
    await makeClient(fetchImpl).get("/x");
    const headers = fetchImpl.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("parses the error envelope and exposes the request id", async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse(
          { error: { code: "forbidden", message: "Nope", details: {} }, request_id: "req-9" },
          { status: 403 },
        ),
      );
    const error = await makeClient(fetchImpl)
      .get("/x")
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 403,
      code: "forbidden",
      requestId: "req-9",
      kind: "http",
    });
  });

  it("falls back to a generic error when the failing body is not an envelope", async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502 }));
    const error = await makeClient(fetchImpl)
      .get("/x")
      .catch((e: unknown) => e);
    expect(error).toMatchObject({ kind: "http", status: 502, code: "http_error" });
  });

  it("maps a network failure to a network ApiError", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await makeClient(fetchImpl)
      .get("/x")
      .catch((e: unknown) => e);
    expect(error).toMatchObject({ kind: "network", code: "network_error" });
  });

  it("sends cookies for the refresh flow and handles 204", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));
    await expect(makeClient(fetchImpl).delete("/x")).resolves.toBeUndefined();
    expect(fetchImpl.mock.calls[0]?.[1]?.credentials).toBe("include");
  });

  it("sends FormData as-is so the browser sets the multipart boundary", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({}));
    const form = new FormData();
    form.append("avatar", new Blob(["x"]), "a.png");
    await makeClient(fetchImpl).post("/upload", form);
    const init = fetchImpl.mock.calls[0]?.[1];
    expect(init?.body).toBe(form);
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("flags a successful response with an unreadable body", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response("not json"));
    const error = await makeClient(fetchImpl)
      .get("/x")
      .catch((e: unknown) => e);
    expect(error).toMatchObject({ kind: "invalid_response" });
  });
});

import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { toUserFacingError } from "@/lib/error-handling";
import { shouldRetry } from "@/lib/query-client";

const http = (status: number) => new ApiError({ kind: "http", status, message: "raw server text" });
const network = new ApiError({ kind: "network", message: "offline" });

describe("toUserFacingError", () => {
  it("reports network failures as offline and retryable", () => {
    expect(toUserFacingError(network)).toMatchObject({ kind: "offline", retryable: true });
  });

  it("hides server fault details", () => {
    const result = toUserFacingError(http(500));
    expect(result.message).not.toContain("raw server text");
    expect(result.retryable).toBe(true);
  });

  it("treats 401 and 403 as forbidden and not retryable", () => {
    expect(toUserFacingError(http(403))).toMatchObject({ kind: "forbidden", retryable: false });
    expect(toUserFacingError(http(401))).toMatchObject({ kind: "forbidden", retryable: false });
  });

  it("shows client error messages and carries the request id", () => {
    const error = new ApiError({
      kind: "http",
      status: 422,
      message: "Bad number",
      requestId: "r1",
    });
    expect(toUserFacingError(error)).toMatchObject({ message: "Bad number", requestId: "r1" });
  });

  it("gives unknown errors a generic message", () => {
    expect(toUserFacingError(new Error("secret internals")).message).not.toContain("secret");
  });
});

describe("shouldRetry", () => {
  it("retries network and 5xx errors up to the limit", () => {
    expect(shouldRetry(0, network)).toBe(true);
    expect(shouldRetry(0, http(503))).toBe(true);
    expect(shouldRetry(2, http(503))).toBe(false);
  });

  it("never retries client errors or unknown errors", () => {
    expect(shouldRetry(0, http(404))).toBe(false);
    expect(shouldRetry(0, new Error("boom"))).toBe(false);
  });
});

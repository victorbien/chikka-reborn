import { describe, expect, it } from "vitest";
import { hostedEnvProblem } from "@/lib/env-rules";
import { parseEnv } from "@/lib/env";

describe("hostedEnvProblem", () => {
  it("allows local development and test builds without an API URL", () => {
    expect(hostedEnvProblem({})).toBeNull();
    expect(hostedEnvProblem({ VITE_APP_ENV: "development" })).toBeNull();
    expect(hostedEnvProblem({ VITE_APP_ENV: "test" })).toBeNull();
  });

  it("requires an explicit API URL in staging and production", () => {
    expect(hostedEnvProblem({ VITE_APP_ENV: "production" })).toMatch(/must be set/);
    expect(hostedEnvProblem({ VITE_APP_ENV: "staging", VITE_API_BASE_URL: "" })).toMatch(
      /must be set/,
    );
  });

  it("requires https and a public host", () => {
    const base = { VITE_APP_ENV: "production" };
    expect(hostedEnvProblem({ ...base, VITE_API_BASE_URL: "http://api.example.com" })).toMatch(
      /https/,
    );
    expect(hostedEnvProblem({ ...base, VITE_API_BASE_URL: "https://localhost:8000" })).toMatch(
      /local host/,
    );
    expect(hostedEnvProblem({ ...base, VITE_API_BASE_URL: "nonsense" })).toMatch(/valid URL/);
    expect(hostedEnvProblem({ ...base, VITE_API_BASE_URL: "https://api.example.com" })).toBeNull();
  });
});

describe("parseEnv in a hosted build", () => {
  it("refuses to fall back to the localhost API", () => {
    expect(() => parseEnv({ VITE_APP_ENV: "production" })).toThrow(/VITE_API_BASE_URL/);
  });

  it("accepts a complete hosted configuration", () => {
    const env = parseEnv({
      VITE_APP_ENV: "production",
      VITE_API_BASE_URL: "https://api.example.com",
    });
    expect(env.VITE_API_BASE_URL).toBe("https://api.example.com");
  });
});

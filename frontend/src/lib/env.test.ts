import { describe, expect, it } from "vitest";
import { parseEnv } from "@/lib/env";

describe("parseEnv", () => {
  it("applies safe local defaults", () => {
    const env = parseEnv({});
    expect(env.VITE_API_BASE_URL).toBe("http://localhost:8000");
    expect(env.VITE_APP_ENV).toBe("development");
  });

  it("treats empty strings from a copied .env.example as unset", () => {
    const env = parseEnv({ VITE_SUPABASE_URL: "", VITE_SUPABASE_ANON_KEY: "" });
    expect(env.VITE_SUPABASE_URL).toBeUndefined();
    expect(env.VITE_SUPABASE_ANON_KEY).toBeUndefined();
  });

  it("rejects an invalid API URL with a readable message", () => {
    expect(() => parseEnv({ VITE_API_BASE_URL: "not a url" })).toThrow(/VITE_API_BASE_URL/);
  });

  it("rejects an unknown environment name", () => {
    expect(() => parseEnv({ VITE_APP_ENV: "qa" })).toThrow(/VITE_APP_ENV/);
  });
});

import { describe, expect, it } from "vitest";
import {
  deleteAccountSchema,
  loginSchema,
  passwordSchema,
  registerSchema,
} from "@/features/auth/schemas";
import {
  normalisePhone,
  onboardingSchema,
  otpSchema,
  phoneSchema,
  profileFormSchema,
  usernameSchema,
} from "@/features/profile/schemas";
import {
  applyServerFieldErrors,
  formatWait,
  hasFieldProblems,
  retryAfterSeconds,
} from "@/lib/forms";
import { ApiError } from "@/lib/api/errors";

describe("password policy (mirrors the server)", () => {
  it.each(["Short1A", "alllowercase1", "ALLUPPERCASE1", "NoDigitsHere", `${"Ä".repeat(37)}a1B`])(
    "rejects %s",
    (password) => expect(passwordSchema.safeParse(password).success).toBe(false),
  );

  it("accepts a strong password", () => {
    expect(passwordSchema.safeParse("Correct-Horse-7").success).toBe(true);
  });
});

describe("auth schemas", () => {
  it("normalises email and requires terms", () => {
    const parsed = registerSchema.safeParse({
      email: "  Marites@Example.COM ",
      display_name: " Marites ",
      password: "Correct-Horse-7",
      accept_terms: true,
    });
    expect(parsed.success && parsed.data).toMatchObject({
      email: "marites@example.com",
      display_name: "Marites",
    });
    expect(registerSchema.safeParse({ ...parsed.data, accept_terms: false }).success).toBe(false);
  });

  it("login only requires something in each field", () => {
    expect(loginSchema.safeParse({ email: "a@example.com", password: "x" }).success).toBe(true);
    expect(loginSchema.safeParse({ email: "a@example.com", password: "" }).success).toBe(false);
  });

  it("deletion needs the exact phrase", () => {
    expect(deleteAccountSchema.safeParse({ password: "x", confirmation: "DELETE" }).success).toBe(
      true,
    );
    expect(deleteAccountSchema.safeParse({ password: "x", confirmation: "delete" }).success).toBe(
      false,
    );
  });
});

describe("profile schemas", () => {
  it.each(["abc", "Mari_2026", "a".repeat(20)])("accepts username %s", (value) => {
    expect(usernameSchema.safeParse(value).success).toBe(true);
  });

  it.each(["ab", "a".repeat(21), "has space", "dash-name", "ADMIN", "Chikka"])(
    "rejects username %s",
    (value) => {
      expect(usernameSchema.safeParse(value).success).toBe(false);
    },
  );

  it("strips markup and maps empty optional fields to null", () => {
    const parsed = profileFormSchema.parse({
      display_name: "<i>Rowena</i>",
      bio: "   ",
      country_code: "ph",
      language: "fil",
      time_zone: "Asia/Manila",
      theme: "dark",
      ui_mode: "classic",
    });
    expect(parsed).toMatchObject({ display_name: "Rowena", bio: null, country_code: "PH" });
  });

  it("rejects unknown countries, languages and zones", () => {
    const base = {
      username: "valid_name",
      display_name: "Valid",
      country_code: "",
      language: "en",
      time_zone: "UTC",
      ui_mode: "modern",
    };
    expect(onboardingSchema.safeParse(base).success).toBe(true);
    expect(onboardingSchema.safeParse({ ...base, country_code: "ZZ" }).success).toBe(false);
    expect(onboardingSchema.safeParse({ ...base, language: "xx" }).success).toBe(false);
    expect(onboardingSchema.safeParse({ ...base, time_zone: "Mars/Base" }).success).toBe(false);
  });

  it("phone numbers need E.164 after removing spaces", () => {
    expect(normalisePhone("+63 917-123 0001")).toBe("+639171230001");
    expect(phoneSchema.safeParse({ phone_number: "+63 917 123 0001" }).success).toBe(true);
    expect(phoneSchema.safeParse({ phone_number: "09171230001" }).success).toBe(false);
    expect(otpSchema.safeParse({ code: "12345" }).success).toBe(false);
    expect(otpSchema.safeParse({ code: "123456" }).success).toBe(true);
  });
});

describe("form helpers", () => {
  const problems = new ApiError({
    kind: "http",
    status: 422,
    message: "invalid",
    details: {
      problems: [
        { field: "body.email", reason: "Bad email" },
        { field: "body.unknown", reason: "x" },
      ],
    },
  });

  it("maps server field problems onto known fields only", () => {
    const set: string[] = [];
    const applied = applyServerFieldErrors(
      problems,
      ((name: string) => set.push(name)) as never,
      ["email"] as never,
    );
    expect(applied).toBe(true);
    expect(set).toEqual(["email"]);
    expect(hasFieldProblems(problems)).toBe(true);
    expect(hasFieldProblems(new Error("x"))).toBe(false);
  });

  it("reads Retry-After details and formats waits", () => {
    const limited = new ApiError({
      kind: "http",
      status: 429,
      message: "slow",
      details: { retry_after_seconds: 90 },
    });
    expect(retryAfterSeconds(limited)).toBe(90);
    expect(retryAfterSeconds(problems)).toBeNull();
    expect(formatWait(30)).toBe("30 seconds");
    expect(formatWait(60)).toBe("1 minute");
    expect(formatWait(840)).toBe("14 minutes");
  });
});

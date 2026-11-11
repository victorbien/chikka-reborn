import { z } from "zod";
import { COUNTRY_CODES, LANGUAGES, timeZones } from "@/features/profile/reference";

/** Mirrors backend/app/modules/profiles/schemas.py. The server re-validates everything. */
const languageCodes = LANGUAGES.map((language) => language.code) as [string, ...string[]];
const countrySet = new Set<string>(COUNTRY_CODES);

const RESERVED = new Set([
  "admin",
  "administrator",
  "root",
  "system",
  "support",
  "help",
  "chikka",
  "chikkareborn",
  "official",
  "moderator",
  "mod",
  "staff",
  "security",
  "null",
  "undefined",
  "deleted_user",
]);

/** Strip markup the same way the server does, so the counter matches what is stored. */
export function plainText(value: string): string {
  return value.replace(/<[^>]*>/g, "").trim();
}

const displayName = z
  .string()
  .transform(plainText)
  .pipe(z.string().min(2, "Use at least 2 characters.").max(50, "Use at most 50 characters."));

const country = z
  .string()
  .transform((value) => value.trim().toUpperCase())
  .refine((value) => value === "" || countrySet.has(value), "Choose a country from the list.")
  .transform((value) => (value === "" ? null : value));

const timeZone = z.string().refine((value) => timeZones().includes(value), "Choose a time zone.");

export const profileFormSchema = z.object({
  display_name: displayName,
  bio: z
    .string()
    .transform(plainText)
    .pipe(z.string().max(160, "Use at most 160 characters."))
    .transform((value) => (value === "" ? null : value)),
  country_code: country,
  language: z.enum(languageCodes, { error: "Choose a language." }),
  time_zone: timeZone,
  theme: z.enum(["system", "light", "dark"]),
  ui_mode: z.enum(["modern", "classic"]),
});
export type ProfileFormInput = z.input<typeof profileFormSchema>;
export type ProfileFormValues = z.output<typeof profileFormSchema>;

export const usernameSchema = z
  .string()
  .trim()
  .regex(/^[A-Za-z0-9_]{3,20}$/, "Use 3 to 20 letters, digits or underscores.")
  .refine((value) => !RESERVED.has(value.toLowerCase()), "This username is reserved.");

export const onboardingSchema = z.object({
  username: usernameSchema,
  display_name: displayName,
  country_code: country,
  language: z.enum(languageCodes, { error: "Choose a language." }),
  time_zone: timeZone,
  ui_mode: z.enum(["modern", "classic"]),
});
export type OnboardingInput = z.input<typeof onboardingSchema>;
export type OnboardingValues = z.output<typeof onboardingSchema>;

/** E.164 after removing spaces and dashes. The server checks the number is real. */
export function normalisePhone(raw: string): string {
  return raw.replace(/[\s-]/g, "");
}

export const phoneSchema = z.object({
  phone_number: z
    .string()
    .transform(normalisePhone)
    .refine(
      (value) => /^\+[1-9][0-9]{6,14}$/.test(value),
      "Use international format, for example +63 917 123 4567.",
    ),
  password: z.string().optional(),
});
export type PhoneInput = z.input<typeof phoneSchema>;
export type PhoneValues = z.output<typeof phoneSchema>;

export const otpSchema = z.object({
  code: z
    .string()
    .trim()
    .regex(/^[0-9]{6}$/, "Enter the 6-digit code."),
});
export type OtpValues = z.infer<typeof otpSchema>;

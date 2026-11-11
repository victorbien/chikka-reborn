import { z } from "zod";

/**
 * Mirrors backend validation (app/modules/auth/schemas.py) so users get instant feedback.
 * The server re-validates everything; these rules are for usability, not security.
 */
export const passwordSchema = z
  .string()
  .min(8, "Use at least 8 characters.")
  .refine((value) => new TextEncoder().encode(value).length <= 72, "Use at most 72 bytes.")
  .refine((value) => /[a-z]/.test(value), "Include a lowercase letter.")
  .refine((value) => /[A-Z]/.test(value), "Include an uppercase letter.")
  .refine((value) => /[0-9]/.test(value), "Include a digit.");

const emailSchema = z
  .string()
  .trim()
  .min(1, "Enter your email address.")
  .pipe(z.email("Enter a valid email address."))
  .transform((value) => value.toLowerCase());

export const displayNameSchema = z
  .string()
  .trim()
  .min(2, "Use at least 2 characters.")
  .max(50, "Use at most 50 characters.");

export const registerSchema = z.object({
  email: emailSchema,
  display_name: displayNameSchema,
  password: passwordSchema,
  accept_terms: z
    .boolean()
    .refine((accepted) => accepted, "You need to accept the Terms and Privacy Notice."),
});
export type RegisterInput = z.input<typeof registerSchema>;
export type RegisterValues = z.output<typeof registerSchema>;

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Enter your password."),
});
export type LoginInput = z.input<typeof loginSchema>;
export type LoginValues = z.output<typeof loginSchema>;

export const emailOnlySchema = z.object({ email: emailSchema });
export type EmailOnlyInput = z.input<typeof emailOnlySchema>;
export type EmailOnlyValues = z.output<typeof emailOnlySchema>;

export const resetPasswordSchema = z
  .object({ new_password: passwordSchema, confirm_password: z.string() })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match.",
  });
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;

export const deleteAccountSchema = z.object({
  password: z.string().min(1, "Enter your password."),
  confirmation: z.string().refine((value) => value === "DELETE", "Type DELETE in capital letters."),
});
export type DeleteAccountInput = z.input<typeof deleteAccountSchema>;

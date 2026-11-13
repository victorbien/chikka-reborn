import { z } from "zod";

/** Mirrors the backend limits; the server validates again. */
export const retrySettingsSchema = z
  .object({
    max_retry_attempts: z.coerce.number().int().min(1).max(10),
    retry_base_seconds: z.coerce.number().int().min(1).max(3600),
    retry_cap_seconds: z.coerce.number().int().min(1).max(86400),
  })
  .refine((v) => v.retry_cap_seconds >= v.retry_base_seconds, {
    message: "The longest wait must be at least the first wait.",
    path: ["retry_cap_seconds"],
  });

const E164 = /^\+[1-9][0-9]{6,14}$/;

export const simulateReplySchema = z.object({
  from_phone: z.string().regex(E164, "Use international format, for example +12025550142."),
  to_number: z.string().regex(E164, "Use international format, for example +12025550190."),
  body: z.string().min(1, "Write the reply.").max(1600),
});

export type RetrySettingsInput = z.input<typeof retrySettingsSchema>;
export type SimulateReplyInput = z.infer<typeof simulateReplySchema>;

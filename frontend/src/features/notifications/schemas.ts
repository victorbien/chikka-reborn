import { z } from "zod";
import type {
  Channel,
  NotificationPreferences,
  NotificationType,
  PreferencesUpdate,
} from "@/features/notifications/types";

const channels = z.object({ in_app: z.boolean(), push: z.boolean(), email: z.boolean() });

export const preferencesFormSchema = z
  .object({
    types: z.record(z.string(), channels),
    quietEnabled: z.boolean(),
    quietStart: z.string(),
    quietEnd: z.string(),
    showPreviews: z.boolean(),
    thresholdCredits: z
      .number({ error: "Enter a number from 1 to 100" })
      .min(1, "At least 1 credit")
      .max(100, "At most 100 credits"),
  })
  .superRefine((value, context) => {
    if (!value.quietEnabled) return;
    for (const field of ["quietStart", "quietEnd"] as const) {
      if (!/^\d{2}:\d{2}$/.test(value[field])) {
        context.addIssue({ code: "custom", path: [field], message: "Choose a time" });
      }
    }
    if (value.quietStart === value.quietEnd) {
      context.addIssue({
        code: "custom",
        path: ["quietEnd"],
        message: "Start and end must be different",
      });
    }
  });

export type PreferencesFormInput = z.input<typeof preferencesFormSchema>;
export type PreferencesFormValues = z.output<typeof preferencesFormSchema>;

export function toFormInput(prefs: NotificationPreferences): PreferencesFormInput {
  return {
    types: Object.fromEntries(
      prefs.types.map((item) => [
        item.type,
        { in_app: item.in_app, push: item.push, email: item.email },
      ]),
    ),
    quietEnabled: prefs.quiet_hours_start !== null && prefs.quiet_hours_end !== null,
    quietStart: prefs.quiet_hours_start ?? "22:00",
    quietEnd: prefs.quiet_hours_end ?? "07:00",
    showPreviews: prefs.show_previews,
    thresholdCredits: prefs.low_balance_threshold_credits,
  };
}

export function toUpdate(values: PreferencesFormValues): PreferencesUpdate {
  const types: NonNullable<PreferencesUpdate["types"]> = {};
  for (const [kind, set] of Object.entries(values.types)) {
    types[kind as NotificationType] = set as Record<Channel, boolean>;
  }
  return {
    types,
    quiet_hours_start: values.quietEnabled ? values.quietStart : null,
    quiet_hours_end: values.quietEnabled ? values.quietEnd : null,
    show_previews: values.showPreviews,
    low_balance_threshold_units: Math.round(values.thresholdCredits * 100),
  };
}

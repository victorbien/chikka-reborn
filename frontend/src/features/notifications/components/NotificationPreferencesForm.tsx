import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { FormAlert } from "@/components/common/FormAlert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BrowserNotificationControl } from "@/features/notifications/components/BrowserNotificationControl";
import {
  useNotificationPreferences,
  useUpdatePreferences,
} from "@/features/notifications/hooks/useNotifications";
import {
  preferencesFormSchema,
  toFormInput,
  toUpdate,
  type PreferencesFormInput,
  type PreferencesFormValues,
} from "@/features/notifications/schemas";
import type { NotificationPreferences, NotificationType } from "@/features/notifications/types";
import { toUserFacingError } from "@/lib/error-handling";

const LABELS: Record<NotificationType, string> = {
  new_message: "New messages",
  sms_inbound: "SMS replies",
  sms_delivered: "SMS delivered",
  sms_failed: "SMS failed",
  contact_request: "Contact requests",
  contact_accepted: "Accepted contact requests",
  low_balance: "Low credits",
  system: "System notices",
  security: "Security alerts",
};

function Form({ prefs }: { prefs: NotificationPreferences }) {
  const update = useUpdatePreferences();
  const form = useForm<PreferencesFormInput, unknown, PreferencesFormValues>({
    resolver: zodResolver(preferencesFormSchema),
    values: toFormInput(prefs),
  });
  const { register, handleSubmit, formState } = form;
  const quietEnabled = useWatch({ control: form.control, name: "quietEnabled" });

  return (
    <form
      noValidate
      className="space-y-6"
      onSubmit={handleSubmit((values) => update.mutate(toUpdate(values)))}
    >
      {prefs.email_disabled ? (
        <FormAlert tone="error">
          Email is switched off for your account because messages to your address kept failing.
          Notices still appear in the app.
        </FormAlert>
      ) : null}
      {prefs.email_simulated ? (
        <FormAlert tone="info">
          Email is in simulation mode here: nothing is sent to a real mailbox.
        </FormAlert>
      ) : null}

      <fieldset className="space-y-2">
        <legend className="text-lg font-semibold">What to be notified about</legend>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-fg-muted">
                <th scope="col" className="py-2 pr-2 font-medium">
                  Type
                </th>
                <th scope="col" className="px-2 font-medium">
                  In the app
                </th>
                <th scope="col" className="px-2 font-medium">
                  Browser
                </th>
                <th scope="col" className="px-2 font-medium">
                  Email
                </th>
              </tr>
            </thead>
            <tbody>
              {prefs.types.map((item) => (
                <tr key={item.type} className="border-t border-border">
                  <th scope="row" className="py-2 pr-2 text-left font-medium">
                    {LABELS[item.type]}
                  </th>
                  <td className="px-2">
                    {item.in_app_locked ? (
                      <span className="text-xs text-fg-muted">Always on</span>
                    ) : (
                      <input
                        type="checkbox"
                        className="size-5"
                        aria-label={`${LABELS[item.type]} in the app`}
                        {...register(`types.${item.type}.in_app`)}
                      />
                    )}
                  </td>
                  <td className="px-2">
                    <input
                      type="checkbox"
                      className="size-5"
                      aria-label={`${LABELS[item.type]} in the browser`}
                      {...register(`types.${item.type}.push`)}
                    />
                  </td>
                  <td className="px-2">
                    <input
                      type="checkbox"
                      className="size-5"
                      aria-label={`${LABELS[item.type]} by email`}
                      {...register(`types.${item.type}.email`)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </fieldset>

      <BrowserNotificationControl />

      <fieldset className="space-y-2">
        <legend className="text-lg font-semibold">Quiet hours</legend>
        <p className="text-xs text-fg-muted">
          During quiet hours new notices still appear in the app, but there are no browser
          notifications and no emails. Times use your profile time zone.
        </p>
        <label className="flex min-h-11 items-center gap-3 text-sm">
          <input type="checkbox" className="size-5" {...register("quietEnabled")} />
          Use quiet hours
        </label>
        {quietEnabled ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              From
              <Input
                type="time"
                {...register("quietStart")}
                aria-invalid={!!formState.errors.quietStart}
              />
              {formState.errors.quietStart ? (
                <span role="alert" className="text-xs text-danger">
                  {formState.errors.quietStart.message}
                </span>
              ) : null}
            </label>
            <label className="text-sm font-medium">
              Until
              <Input
                type="time"
                {...register("quietEnd")}
                aria-invalid={!!formState.errors.quietEnd}
              />
              {formState.errors.quietEnd ? (
                <span role="alert" className="text-xs text-danger">
                  {formState.errors.quietEnd.message}
                </span>
              ) : null}
            </label>
          </div>
        ) : null}
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-lg font-semibold">Privacy and credits</legend>
        <label className="flex min-h-11 items-start gap-3 text-sm">
          <input type="checkbox" className="mt-1 size-5" {...register("showPreviews")} />
          <span>
            <span className="block font-medium">Show message previews</span>
            <span className="block text-xs text-fg-muted">
              Off by default: notifications say who wrote, not what. SMS text is never shown.
            </span>
          </span>
        </label>
        <label className="block text-sm font-medium">
          Warn me when my demo credits fall to (credits)
          <Input
            type="number"
            step="0.5"
            min={1}
            max={100}
            inputMode="decimal"
            className="max-w-40"
            aria-invalid={!!formState.errors.thresholdCredits}
            {...register("thresholdCredits", { valueAsNumber: true })}
          />
          {formState.errors.thresholdCredits ? (
            <span role="alert" className="text-xs text-danger">
              {formState.errors.thresholdCredits.message}
            </span>
          ) : null}
        </label>
      </fieldset>

      {update.isError ? (
        <FormAlert tone="error">{toUserFacingError(update.error).message}</FormAlert>
      ) : null}
      {update.isSuccess && !formState.isDirty ? (
        <FormAlert tone="success">Your notification settings were saved.</FormAlert>
      ) : null}
      <Button type="submit" disabled={update.isPending}>
        {update.isPending ? "Saving…" : "Save settings"}
      </Button>
    </form>
  );
}

export function NotificationPreferencesForm() {
  const prefs = useNotificationPreferences();
  if (prefs.isPending) {
    return (
      <p role="status" className="text-sm text-fg-muted">
        Loading your notification settings…
      </p>
    );
  }
  if (prefs.isError) {
    return <FormAlert tone="error">{toUserFacingError(prefs.error).message}</FormAlert>;
  }
  return <Form prefs={prefs.data} />;
}

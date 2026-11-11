import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { LocaleFields } from "@/features/profile/components/ProfileFields";
import { useCompleteOnboarding } from "@/features/profile/hooks/useProfile";
import { detectedTimeZone } from "@/features/profile/reference";
import {
  onboardingSchema,
  type OnboardingInput,
  type OnboardingValues,
} from "@/features/profile/schemas";
import type { Profile } from "@/features/profile/types";
import { isApiError } from "@/lib/api/errors";
import { toUserFacingError } from "@/lib/error-handling";
import { applyServerFieldErrors, hasFieldProblems } from "@/lib/forms";

function suggestionsOf(error: unknown): string[] {
  if (!isApiError(error) || error.code !== "username_taken") return [];
  const raw = error.details.suggestions;
  return Array.isArray(raw) ? raw.filter((item): item is string => typeof item === "string") : [];
}

/** Profile setup after email confirmation (FR-AUTH-015). */
export function OnboardingForm({ profile, onDone }: { profile: Profile; onDone: () => void }) {
  const onboarding = useCompleteOnboarding();
  const form = useForm<OnboardingInput, unknown, OnboardingValues>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      username: "",
      display_name: profile.display_name === "New user" ? "" : profile.display_name,
      country_code: profile.country_code ?? "",
      language: profile.language,
      time_zone: profile.time_zone === "UTC" ? detectedTimeZone() : profile.time_zone,
      ui_mode: profile.ui_mode,
    },
  });
  const { errors } = form.formState;
  const suggestions = suggestionsOf(onboarding.error);

  const onSubmit = form.handleSubmit((values) =>
    onboarding.mutate(values, {
      onSuccess: onDone,
      onError: (error) => {
        if (isApiError(error) && error.code === "username_taken") {
          form.setError("username", { type: "server", message: "That username is taken." });
          return;
        }
        applyServerFieldErrors(error, form.setError, [
          "username",
          "display_name",
          "country_code",
          "language",
          "time_zone",
          "ui_mode",
        ]);
      },
    }),
  );

  const showBanner =
    onboarding.error && !hasFieldProblems(onboarding.error) && suggestions.length === 0;

  return (
    <form noValidate onSubmit={onSubmit} className="space-y-4" aria-labelledby="onboarding-heading">
      <div>
        <h1 id="onboarding-heading" className="text-xl font-semibold">
          Set up your profile
        </h1>
        <p className="text-sm text-fg-muted">
          You can change everything except your username later.
        </p>
      </div>
      {showBanner ? (
        <FormAlert tone="error" requestId={toUserFacingError(onboarding.error).requestId}>
          {toUserFacingError(onboarding.error).message}
        </FormAlert>
      ) : null}
      <FormField
        label="Username"
        error={errors.username?.message}
        hint="3 to 20 letters, digits or underscores. Others can find you by it."
      >
        <Input autoComplete="username" autoCapitalize="none" {...form.register("username")} />
      </FormField>
      {suggestions.length > 0 ? (
        <div className="space-y-1" aria-live="polite">
          <p className="text-sm">Available instead:</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <Button
                key={suggestion}
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  form.setValue("username", suggestion, { shouldValidate: true });
                  onboarding.reset();
                }}
              >
                {suggestion}
              </Button>
            ))}
          </div>
        </div>
      ) : null}
      <FormField label="Display name" error={errors.display_name?.message}>
        <Input autoComplete="name" {...form.register("display_name")} />
      </FormField>
      <LocaleFields
        country={form.register("country_code")}
        language={form.register("language")}
        timeZone={form.register("time_zone")}
        errors={{
          country: errors.country_code?.message,
          language: errors.language?.message,
          timeZone: errors.time_zone?.message,
        }}
      />
      <FormField
        label="Interface"
        error={errors.ui_mode?.message}
        hint="Classic is the nostalgic buddy-list look."
      >
        <Select {...form.register("ui_mode")}>
          <option value="modern">Modern</option>
          <option value="classic">Classic</option>
        </Select>
      </FormField>
      <p className="text-xs text-fg-muted">
        Privacy defaults: only your contacts see your profile, and your mobile number is not
        searchable. You can change this later.
      </p>
      <Button type="submit" className="w-full" disabled={onboarding.isPending}>
        {onboarding.isPending ? "Saving…" : "Finish setup"}
      </Button>
    </form>
  );
}

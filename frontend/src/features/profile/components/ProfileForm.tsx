import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { Input, Select, Textarea } from "@/components/ui/input";
import { LocaleFields } from "@/features/profile/components/ProfileFields";
import { useUpdateProfile } from "@/features/profile/hooks/useProfile";
import {
  plainText,
  profileFormSchema,
  type ProfileFormInput,
  type ProfileFormValues,
} from "@/features/profile/schemas";
import type { Profile } from "@/features/profile/types";
import { toUserFacingError } from "@/lib/error-handling";
import { applyServerFieldErrors, hasFieldProblems } from "@/lib/forms";

function toInput(profile: Profile): ProfileFormInput {
  return {
    display_name: profile.display_name,
    bio: profile.bio ?? "",
    country_code: profile.country_code ?? "",
    language: profile.language,
    time_zone: profile.time_zone,
    theme: profile.theme,
    ui_mode: profile.ui_mode,
  };
}

/** Profile editing (FR-AUTH-007). Only changed fields are sent. */
export function ProfileForm({ profile }: { profile: Profile }) {
  const update = useUpdateProfile();
  const form = useForm<ProfileFormInput, unknown, ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    defaultValues: toInput(profile),
  });
  const { errors, dirtyFields, isDirty } = form.formState;
  const bio = useWatch({ control: form.control, name: "bio" });
  const bioLength = plainText(bio ?? "").length;

  const onSubmit = form.handleSubmit((values) => {
    const changes: Partial<ProfileFormValues> = {};
    for (const key of Object.keys(dirtyFields) as (keyof ProfileFormValues)[]) {
      (changes as Record<string, unknown>)[key] = values[key];
    }
    update.mutate(changes, {
      onSuccess: (saved) => form.reset(toInput(saved)),
      onError: (error) =>
        applyServerFieldErrors(error, form.setError, [
          "display_name",
          "bio",
          "country_code",
          "language",
          "time_zone",
          "theme",
          "ui_mode",
        ]),
    });
  });

  return (
    <form noValidate onSubmit={onSubmit} className="space-y-4" aria-label="Profile details">
      {update.isSuccess && !isDirty ? <FormAlert tone="success">Profile saved.</FormAlert> : null}
      {update.error && !hasFieldProblems(update.error) ? (
        <FormAlert tone="error" requestId={toUserFacingError(update.error).requestId}>
          {toUserFacingError(update.error).message}
        </FormAlert>
      ) : null}
      <FormField label="Username" hint="Usernames cannot be changed.">
        <Input value={profile.username ?? ""} readOnly disabled />
      </FormField>
      <FormField
        label="Email"
        hint="Your sign-in address. Managed by your account, not your profile."
      >
        <Input value={profile.email ?? ""} readOnly disabled />
      </FormField>
      <FormField label="Display name" error={errors.display_name?.message}>
        <Input autoComplete="name" {...form.register("display_name")} />
      </FormField>
      <FormField
        label="Bio or status message"
        error={errors.bio?.message}
        hint={<span aria-live="polite">{bioLength}/160</span>}
      >
        <Textarea rows={3} {...form.register("bio")} />
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
        label="Theme"
        error={errors.theme?.message}
        hint="Only the dark palette exists so far. Your choice is saved and will apply when light mode ships."
      >
        <Select {...form.register("theme")}>
          <option value="system">Match my device</option>
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </Select>
      </FormField>
      <FormField label="Interface" error={errors.ui_mode?.message}>
        <Select {...form.register("ui_mode")}>
          <option value="modern">Modern</option>
          <option value="classic">Classic</option>
        </Select>
      </FormField>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!isDirty || update.isPending}>
          {update.isPending ? "Saving…" : "Save changes"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={!isDirty || update.isPending}
          onClick={() => form.reset(toInput(profile))}
        >
          Discard
        </Button>
      </div>
    </form>
  );
}

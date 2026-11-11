import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDeleteAccount } from "@/features/auth/hooks/useAuth";
import { deleteAccountSchema, type DeleteAccountInput } from "@/features/auth/schemas";
import { isApiError } from "@/lib/api/errors";
import { toUserFacingError } from "@/lib/error-handling";
import { formatWait, retryAfterSeconds } from "@/lib/forms";

/** Account deletion (FR-AUTH-009): explains what goes, re-authenticates, needs a typed phrase. */
export function DeleteAccountSection({ onDeleted }: { onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  const remove = useDeleteAccount();
  const form = useForm<DeleteAccountInput>({
    resolver: zodResolver(deleteAccountSchema),
    defaultValues: { password: "", confirmation: "" },
  });
  const { errors } = form.formState;

  if (!open) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-fg-muted">
          Permanently delete your account and personal profile data.
        </p>
        <Button variant="destructive" onClick={() => setOpen(true)}>
          Delete account…
        </Button>
      </div>
    );
  }

  const error = remove.error;
  const wait = retryAfterSeconds(error);
  const message =
    error && isApiError(error) && error.code === "reauthentication_failed"
      ? "The password is incorrect. Nothing was deleted."
      : error && wait
        ? `Too many attempts. Try again in ${formatWait(wait)}.`
        : error
          ? toUserFacingError(error).message
          : null;

  return (
    <form
      noValidate
      className="space-y-3 rounded-panel border border-danger p-3"
      aria-labelledby="delete-heading"
      onSubmit={form.handleSubmit((values) =>
        remove.mutate(values.password, {
          onSuccess: onDeleted,
          onError: () => form.resetField("password"),
        }),
      )}
    >
      <h3 id="delete-heading" className="font-semibold">
        Delete your account
      </h3>
      <ul className="list-disc space-y-1 pl-5 text-sm text-fg-muted">
        <li>Removed now: username, display name, bio, photo, country and mobile numbers.</li>
        <li>You are signed out on every device and cannot sign in again.</li>
        <li>
          Kept, without your name: messages in other people&apos;s chats (shown as &quot;Deleted
          user&quot;), consent and billing records, and the security audit trail.
        </li>
      </ul>
      {message ? <FormAlert tone="error">{message}</FormAlert> : null}
      <FormField label="Your password" error={errors.password?.message}>
        <Input type="password" autoComplete="current-password" {...form.register("password")} />
      </FormField>
      <FormField label="Type DELETE to confirm" error={errors.confirmation?.message}>
        <Input autoComplete="off" autoCapitalize="characters" {...form.register("confirmation")} />
      </FormField>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="destructive" disabled={remove.isPending}>
          {remove.isPending ? "Deleting…" : "Delete my account"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            form.reset();
            remove.reset();
            setOpen(false);
          }}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}

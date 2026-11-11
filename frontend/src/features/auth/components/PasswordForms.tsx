import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useConfirmPasswordReset, useRequestPasswordReset } from "@/features/auth/hooks/useAuth";
import {
  emailOnlySchema,
  resetPasswordSchema,
  type EmailOnlyInput,
  type EmailOnlyValues,
  type ResetPasswordValues,
} from "@/features/auth/schemas";
import { isApiError } from "@/lib/api/errors";
import { toUserFacingError } from "@/lib/error-handling";
import { applyServerFieldErrors, formatWait, retryAfterSeconds } from "@/lib/forms";
import { paths } from "@/lib/paths";

function failureText(error: unknown): string {
  const wait = retryAfterSeconds(error);
  if (wait) return `Too many requests. Try again in ${formatWait(wait)}.`;
  if (isApiError(error) && error.status === 400) return error.message;
  if (isApiError(error) && error.code === "weak_password") return error.message;
  return toUserFacingError(error).message;
}

export function ForgotPasswordForm() {
  const reset = useRequestPasswordReset();
  const form = useForm<EmailOnlyInput, unknown, EmailOnlyValues>({
    resolver: zodResolver(emailOnlySchema),
    defaultValues: { email: "" },
  });

  if (reset.isSuccess) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Check your inbox</h1>
        {/* The same message whether or not the address is registered (FR-AUTH-005 AC2). */}
        <FormAlert tone="success">{reset.data.message}</FormAlert>
        <p className="text-sm text-fg-muted">The link works once and expires after one hour.</p>
        <Link to={paths.signIn} className="text-sm text-accent underline">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form
      noValidate
      className="space-y-4"
      aria-labelledby="forgot-heading"
      onSubmit={form.handleSubmit((values) => reset.mutate(values.email))}
    >
      <h1 id="forgot-heading" className="text-xl font-semibold">
        Reset your password
      </h1>
      <p className="text-sm text-fg-muted">Enter your email and we will send you a reset link.</p>
      {reset.error ? <FormAlert tone="error">{failureText(reset.error)}</FormAlert> : null}
      <FormField label="Email" error={form.formState.errors.email?.message}>
        <Input type="email" autoComplete="email" inputMode="email" {...form.register("email")} />
      </FormField>
      <Button type="submit" className="w-full" disabled={reset.isPending}>
        {reset.isPending ? "Sending…" : "Send reset link"}
      </Button>
      <Link to={paths.signIn} className="block text-center text-sm text-accent underline">
        Back to sign in
      </Link>
    </form>
  );
}

export function ResetPasswordForm({ tokenHash }: { tokenHash: string }) {
  const confirm = useConfirmPasswordReset();
  const form = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });
  const { errors } = form.formState;

  if (confirm.isSuccess) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Password changed</h1>
        <FormAlert tone="success">
          {confirm.data.message} You were signed out on every device.
        </FormAlert>
        <Button asChild className="w-full">
          <Link to={paths.signIn}>Sign in</Link>
        </Button>
      </div>
    );
  }

  return (
    <form
      noValidate
      className="space-y-4"
      aria-labelledby="reset-heading"
      onSubmit={form.handleSubmit((values) =>
        confirm.mutate(
          {
            tokenHash,
            newPassword: values.new_password,
            confirmPassword: values.confirm_password,
          },
          {
            onError: (error) =>
              applyServerFieldErrors(error, form.setError, ["new_password", "confirm_password"]),
          },
        ),
      )}
    >
      <h1 id="reset-heading" className="text-xl font-semibold">
        Choose a new password
      </h1>
      {confirm.error ? (
        <FormAlert tone="error">
          {failureText(confirm.error)}{" "}
          {isApiError(confirm.error) && confirm.error.status === 400 ? (
            <Link to={paths.forgotPassword} className="underline">
              Request a new link
            </Link>
          ) : null}
        </FormAlert>
      ) : null}
      <FormField
        label="New password"
        error={errors.new_password?.message}
        hint="At least 8 characters with an uppercase letter, a lowercase letter and a digit."
      >
        <Input type="password" autoComplete="new-password" {...form.register("new_password")} />
      </FormField>
      <FormField label="Confirm new password" error={errors.confirm_password?.message}>
        <Input type="password" autoComplete="new-password" {...form.register("confirm_password")} />
      </FormField>
      <Button type="submit" className="w-full" disabled={confirm.isPending}>
        {confirm.isPending ? "Saving…" : "Change password"}
      </Button>
    </form>
  );
}

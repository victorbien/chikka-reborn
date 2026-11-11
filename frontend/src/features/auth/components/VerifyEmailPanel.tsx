import { zodResolver } from "@hookform/resolvers/zod";
import { MailCheck } from "lucide-react";
import { useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { PageLoader } from "@/components/common/PageLoader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useResendVerification, useVerifyEmail } from "@/features/auth/hooks/useAuth";
import {
  emailOnlySchema,
  type EmailOnlyInput,
  type EmailOnlyValues,
} from "@/features/auth/schemas";
import { isApiError } from "@/lib/api/errors";
import { toUserFacingError } from "@/lib/error-handling";
import { formatWait, retryAfterSeconds } from "@/lib/forms";
import { paths } from "@/lib/paths";

/** Email verification (FR-AUTH-002). Mobile number verification is separate (settings). */
export function VerifyEmailPanel({
  tokenHash,
  email,
  onVerified,
}: {
  tokenHash: string | null;
  email: string | null;
  onVerified: () => void;
}) {
  return tokenHash ? (
    <ConfirmLink tokenHash={tokenHash} onVerified={onVerified} />
  ) : (
    <CheckInbox email={email} />
  );
}

function ConfirmLink({ tokenHash, onVerified }: { tokenHash: string; onVerified: () => void }) {
  const verify = useVerifyEmail();
  const started = useRef(false);

  useEffect(() => {
    // Links are single use; React StrictMode runs effects twice in development.
    if (started.current) return;
    started.current = true;
    verify.mutate(tokenHash, { onSuccess: onVerified });
  }, [tokenHash, verify, onVerified]);

  if (verify.isError) {
    const expired = isApiError(verify.error) && verify.error.status === 400;
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Confirmation failed</h1>
        <FormAlert tone="error" requestId={toUserFacingError(verify.error).requestId}>
          {expired ? verify.error.message : toUserFacingError(verify.error).message}
        </FormAlert>
        <CheckInbox email={null} heading={false} />
      </div>
    );
  }
  return <PageLoader label="Confirming your email" />;
}

function CheckInbox({ email, heading = true }: { email: string | null; heading?: boolean }) {
  const resend = useResendVerification();
  const form = useForm<EmailOnlyInput, unknown, EmailOnlyValues>({
    resolver: zodResolver(emailOnlySchema),
    defaultValues: { email: email ?? "" },
  });
  const wait = retryAfterSeconds(resend.error);

  return (
    <div className="space-y-4">
      {heading ? (
        <>
          <div className="flex items-center gap-2">
            <MailCheck aria-hidden className="size-6 text-accent" />
            <h1 className="text-xl font-semibold">Confirm your email</h1>
          </div>
          <p className="text-sm text-fg-muted">
            {email ? (
              <>
                If <span className="font-medium text-fg">{email}</span> can be used, we sent a
                confirmation link to it.
              </>
            ) : (
              "Open the confirmation link we emailed you."
            )}{" "}
            The link expires after 24 hours.
          </p>
        </>
      ) : null}
      <form
        noValidate
        className="space-y-3"
        aria-label="Send a new confirmation link"
        onSubmit={form.handleSubmit((values) => resend.mutate(values.email))}
      >
        {resend.isSuccess ? <FormAlert tone="success">{resend.data.message}</FormAlert> : null}
        {resend.error ? (
          <FormAlert tone="error">
            {wait
              ? `You can request another link in ${formatWait(wait)}.`
              : toUserFacingError(resend.error).message}
          </FormAlert>
        ) : null}
        <FormField label="Email" error={form.formState.errors.email?.message}>
          <Input type="email" autoComplete="email" {...form.register("email")} />
        </FormField>
        <Button type="submit" variant="secondary" className="w-full" disabled={resend.isPending}>
          {resend.isPending ? "Sending…" : "Send a new link"}
        </Button>
      </form>
      <Link to={paths.signIn} className="block text-center text-sm text-accent underline">
        Back to sign in
      </Link>
    </div>
  );
}

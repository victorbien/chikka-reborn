import { zodResolver } from "@hookform/resolvers/zod";
import { Smartphone } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { SimulatedBadge } from "@/components/shared/ChannelBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { PageLoader } from "@/components/common/PageLoader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useConfirmPhone,
  usePhoneStatus,
  useRemovePhone,
  useSimulatedInbox,
  useStartPhoneVerification,
} from "@/features/profile/hooks/usePhone";
import {
  otpSchema,
  phoneSchema,
  type OtpValues,
  type PhoneInput,
  type PhoneValues,
} from "@/features/profile/schemas";
import type { PhoneStart } from "@/features/profile/types";
import { isApiError } from "@/lib/api/errors";
import { toUserFacingError } from "@/lib/error-handling";
import { formatWait, retryAfterSeconds } from "@/lib/forms";

function errorText(error: unknown): string {
  const wait = retryAfterSeconds(error);
  if (wait) return `You have requested several codes. Try again in ${formatWait(wait)}.`;
  // Phone endpoints return safe, specific messages for 4xx (wrong code, expired, cooldown).
  if (isApiError(error) && error.status !== null && error.status < 500 && error.status !== 401) {
    return error.message;
  }
  return toUserFacingError(error).message;
}

/**
 * Mobile number verification (FR-AUTH-008, FR-AUTH-012). Separate from email verification.
 * In simulation mode no SMS is sent: the code appears below, labelled SIMULATED.
 */
export function PhoneSection() {
  const status = usePhoneStatus();
  const [pending, setPending] = useState<{ number: string; start: PhoneStart } | null>(null);
  const [changing, setChanging] = useState(false);

  if (status.isPending) return <PageLoader label="Loading your mobile number" />;
  if (status.isError) {
    const friendly = toUserFacingError(status.error);
    return (
      <ErrorState
        kind={friendly.kind}
        message={friendly.message}
        requestId={friendly.requestId}
        onRetry={() => void status.refetch()}
      />
    );
  }

  const simulated = status.data.delivery_mode === "simulated";

  return (
    <div className="space-y-4">
      {simulated ? (
        <FormAlert tone="info">
          <span className="inline-flex flex-wrap items-center gap-2">
            <SimulatedBadge /> Simulation mode: no real text message is sent and nothing is charged.
          </span>
        </FormAlert>
      ) : null}

      {status.data.verified && !changing && !pending ? (
        <VerifiedNumber
          masked={status.data.masked ?? ""}
          mode={status.data.verification_mode}
          onChange={() => setChanging(true)}
        />
      ) : null}

      {!status.data.verified && !pending ? (
        <EmptyState
          icon={Smartphone}
          title="No mobile number yet"
          description="Add a number so SMS contacts can recognise you. We send a 6-digit code to confirm it."
        />
      ) : null}

      {(!status.data.verified || changing) && !pending ? (
        <StartForm
          requirePassword={status.data.verified}
          onStarted={(number, start) => setPending({ number, start })}
          onCancel={changing ? () => setChanging(false) : undefined}
        />
      ) : null}

      {pending ? (
        <ConfirmForm
          number={pending.number}
          start={pending.start}
          onDone={() => {
            setPending(null);
            setChanging(false);
          }}
        />
      ) : null}

      {pending && simulated ? <SimulatedInbox /> : null}
    </div>
  );
}

function VerifiedNumber({
  masked,
  mode,
  onChange,
}: {
  masked: string;
  mode: "live" | "simulated" | null;
  onChange: () => void;
}) {
  const remove = useRemovePhone();
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [password, setPassword] = useState("");

  return (
    <div className="space-y-2 rounded-panel border border-border p-3">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <Smartphone aria-hidden className="size-4" />
        <span className="font-mono">{masked}</span>
        <span className="text-fg-muted">verified</span>
        {mode === "simulated" ? <SimulatedBadge /> : null}
      </p>
      {mode === "simulated" ? (
        <p className="text-xs text-fg-muted">
          Verified in simulation. It must be verified again before live SMS features use it.
        </p>
      ) : null}
      {confirmRemove ? (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            remove.mutate(password, { onSettled: () => setPassword("") });
          }}
        >
          <FormField label="Confirm your password to remove the number">
            <Input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </FormField>
          {remove.error ? <FormAlert tone="error">{errorText(remove.error)}</FormAlert> : null}
          <div className="flex gap-2">
            <Button type="submit" variant="destructive" disabled={!password || remove.isPending}>
              Remove number
            </Button>
            <Button type="button" variant="secondary" onClick={() => setConfirmRemove(false)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={onChange}>
            Change number
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirmRemove(true)}>
            Remove
          </Button>
        </div>
      )}
    </div>
  );
}

function StartForm({
  requirePassword,
  onStarted,
  onCancel,
}: {
  requirePassword: boolean;
  onStarted: (number: string, start: PhoneStart) => void;
  onCancel?: () => void;
}) {
  const start = useStartPhoneVerification();
  const form = useForm<PhoneInput, unknown, PhoneValues>({
    resolver: zodResolver(phoneSchema),
    defaultValues: { phone_number: "", password: "" },
  });
  const { errors } = form.formState;

  return (
    <form
      noValidate
      className="space-y-3"
      aria-label="Add a mobile number"
      onSubmit={form.handleSubmit((values) =>
        start.mutate(
          { phoneNumber: values.phone_number, password: values.password || undefined },
          {
            onSuccess: (result) => onStarted(values.phone_number, result),
            onError: () => form.resetField("password"),
          },
        ),
      )}
    >
      {start.error ? <FormAlert tone="error">{errorText(start.error)}</FormAlert> : null}
      <FormField
        label="Mobile number"
        error={errors.phone_number?.message}
        hint="International format with country code, for example +63 917 123 4567."
      >
        <Input type="tel" autoComplete="tel" inputMode="tel" {...form.register("phone_number")} />
      </FormField>
      {requirePassword ? (
        <FormField label="Your password" hint="Needed to replace a verified number.">
          <Input type="password" autoComplete="current-password" {...form.register("password")} />
        </FormField>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={start.isPending}>
          {start.isPending ? "Sending code…" : "Send code"}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}

function ConfirmForm({
  number,
  start,
  onDone,
}: {
  number: string;
  start: PhoneStart;
  onDone: () => void;
}) {
  const confirm = useConfirmPhone();
  const form = useForm<OtpValues>({
    resolver: zodResolver(otpSchema),
    defaultValues: { code: "" },
  });

  return (
    <form
      noValidate
      className="space-y-3"
      aria-label="Enter the verification code"
      onSubmit={form.handleSubmit((values) =>
        confirm.mutate({ phoneNumber: number, code: values.code }, { onSuccess: onDone }),
      )}
    >
      <p className="text-sm" aria-live="polite">
        We sent a 6-digit code to <span className="font-mono">{start.masked}</span>
        {start.verification_mode === "simulated" ? " (simulated)" : ""}. It expires in{" "}
        {Math.round(start.expires_in / 60)} minutes.
      </p>
      {confirm.error ? <FormAlert tone="error">{errorText(confirm.error)}</FormAlert> : null}
      <FormField label="Verification code" error={form.formState.errors.code?.message}>
        <Input
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          {...form.register("code")}
        />
      </FormField>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={confirm.isPending}>
          {confirm.isPending ? "Checking…" : "Verify number"}
        </Button>
        <Button type="button" variant="secondary" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function SimulatedInbox() {
  const inbox = useSimulatedInbox(true);
  return (
    <section
      aria-labelledby="sim-inbox"
      className="space-y-2 rounded-panel border border-simulated p-3"
    >
      <h3 id="sim-inbox" className="flex items-center gap-2 text-sm font-semibold">
        <SimulatedBadge /> Simulated SMS inbox
      </h3>
      <p className="text-xs text-fg-muted">
        Shown only in simulation outside production. A real phone receives nothing.
      </p>
      {inbox.isPending ? <PageLoader label="Waiting for the simulated message" /> : null}
      {inbox.isError ? (
        <p className="text-sm text-fg-muted">The simulated inbox is not available.</p>
      ) : null}
      {inbox.data && inbox.data.length === 0 ? (
        <p className="text-sm text-fg-muted">No simulated messages yet.</p>
      ) : null}
      <ul className="space-y-2" aria-live="polite">
        {inbox.data?.map((message) => (
          <li key={message.created_at} className="rounded-control bg-surface-raised p-2 text-sm">
            <p className="flex items-center gap-2 text-xs text-fg-muted">
              <SimulatedBadge /> To {message.to}
            </p>
            <p>{message.body}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

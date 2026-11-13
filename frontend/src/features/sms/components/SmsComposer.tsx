import { useState } from "react";
import { FormAlert } from "@/components/common/FormAlert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { SendConfirmDialog } from "@/features/sms/components/SendConfirmDialog";
import { SmsQuotePanel } from "@/features/sms/components/SmsQuotePanel";
import { useQuote, useSendSms, useSetConsent } from "@/features/sms/hooks/useSms";
import type { SmsMessage, SmsTarget } from "@/features/sms/types";
import { toUserFacingError } from "@/lib/error-handling";

export interface SmsComposerProps {
  /** Null until the recipient is known (nothing can be checked or sent yet). */
  target: SmsTarget | null;
  onSent: (message: SmsMessage) => void;
}

const MAX_CHARS = 1600;

/** Compose, check, confirm, send. Sending is only possible after the server's own check says
 *  so, and only after the confirmation dialog. AI text would enter only by being typed here. */
export function SmsComposer({ target, onSent }: SmsComposerProps) {
  const [body, setBody] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const quote = useQuote(target, body);
  const consent = useSetConsent(target);
  const send = useSendSms(target);

  const text = body.trim();
  const current = quote.data;
  const ready =
    target !== null &&
    text.length > 0 &&
    !quote.isFetching &&
    current !== undefined &&
    current.can_send;
  const failedCheck = quote.isError && target !== null;
  const sendError = send.isError ? toUserFacingError(send.error).message : undefined;

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) setConfirmOpen(true);
      }}
    >
      <div>
        <label htmlFor="sms-body" className="mb-1 block text-sm font-medium">
          Message
        </label>
        <Textarea
          id="sms-body"
          value={body}
          maxLength={MAX_CHARS}
          onChange={(event) => setBody(event.target.value)}
          aria-describedby="sms-quote"
        />
      </div>
      <div id="sms-quote">
        <SmsQuotePanel
          body={body}
          quote={current}
          loading={quote.isFetching}
          failed={failedCheck}
          recipientName={current?.recipient.display_name ?? undefined}
          consentPending={consent.isPending}
          onConsentChange={(granted) => consent.mutate(granted ? "granted" : "withdrawn")}
        />
      </div>
      {consent.isError ? (
        <FormAlert tone="error">{toUserFacingError(consent.error).message}</FormAlert>
      ) : null}
      <Button type="submit" disabled={!ready}>
        Review and send
      </Button>
      {current ? (
        <SendConfirmDialog
          open={confirmOpen}
          onOpenChange={setConfirmOpen}
          quote={current}
          body={text}
          pending={send.isPending}
          error={sendError}
          onConfirm={() =>
            send.mutate(text, {
              onSuccess: (message) => {
                setConfirmOpen(false);
                setBody("");
                onSent(message);
              },
            })
          }
        />
      ) : null}
    </form>
  );
}

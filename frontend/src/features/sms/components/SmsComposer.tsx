import { useState } from "react";
import { FormAlert } from "@/components/common/FormAlert";
import { AiAssistedBadge } from "@/components/shared/ChannelBadge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { AiAssistantToggle } from "@/features/ai/components/AiAssistantToggle";
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
  const [aiAssisted, setAiAssisted] = useState(false);
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

  function changeBody(value: string) {
    setBody(value);
    if (!value.trim()) setAiAssisted(false);
  }
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
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <label htmlFor="sms-body" className="text-sm font-medium">
            Message
          </label>
          {aiAssisted ? <AiAssistedBadge /> : null}
        </div>
        <Textarea
          id="sms-body"
          value={body}
          maxLength={MAX_CHARS}
          onChange={(event) => changeBody(event.target.value)}
          aria-describedby="sms-quote"
        />
      </div>
      <AiAssistantToggle
        draft={body}
        channel="sms"
        onUse={(text) => {
          // Only fills the box. The server check and the confirmation dialog still gate Send.
          setBody(text.slice(0, MAX_CHARS));
          setAiAssisted(true);
        }}
      />
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
                setAiAssisted(false);
                onSent(message);
              },
            })
          }
        />
      ) : null}
    </form>
  );
}

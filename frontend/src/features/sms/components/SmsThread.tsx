import { useState } from "react";
import { MessageBubble } from "@/components/shared/MessageBubble";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { formatFull, formatTime } from "@/features/chat/format";
import { useRetrySms } from "@/features/sms/hooks/useSms";
import type { SmsMessage } from "@/features/sms/types";
import { toUserFacingError } from "@/lib/error-handling";
import type { MessageStatus } from "@/lib/types";

/** Plain-language status wording for hover and screen readers. "Accepted" is never "delivered". */
export function statusDetail(message: SmsMessage): string | undefined {
  const delivery = message.delivery;
  if (message.direction === "inbound") return undefined;
  switch (message.status) {
    case "queued":
      return "Waiting to be handed to the SMS provider.";
    case "retrying":
      return delivery?.next_attempt_at
        ? `A temporary problem occurred. Trying again at ${formatTime(delivery.next_attempt_at)}.`
        : "A temporary problem occurred. Trying again.";
    case "accepted":
      return "The SMS provider accepted this message. It has not been delivered yet.";
    case "sent":
      return delivery?.confirmation === "unconfirmed"
        ? "Sent to the carrier. Delivery was not confirmed."
        : "Sent to the carrier. Waiting for delivery confirmation.";
    case "delivered":
      return delivery?.delivered_at
        ? `Delivered ${formatFull(delivery.delivered_at)}${
            message.is_simulated ? " (simulated, not a real carrier)" : ""
          }`
        : "Delivered";
    default:
      return undefined;
  }
}

function toStatus(message: SmsMessage): MessageStatus | undefined {
  if (message.direction === "inbound") return undefined;
  // `received` only exists on inbound messages.
  return message.status === "received" ? undefined : message.status;
}

function MessageFooter({ message, onRetry }: { message: SmsMessage; onRetry: () => void }) {
  const failure = message.failure;
  if (!failure) {
    return message.attempt_count > 1 && message.status === "retrying" ? (
      <p className="text-fg-muted">Attempt {message.attempt_count}</p>
    ) : null;
  }
  return (
    <div role="group" aria-label="Failure details" className="space-y-1 text-danger">
      <p>{failure.reason}</p>
      {failure.may_have_been_delivered ? (
        <p>
          We couldn&apos;t confirm the outcome, so this message may still have been delivered. Check
          with the person before sending it again.
        </p>
      ) : null}
      {message.can_retry ? (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          Send again
        </Button>
      ) : null}
    </div>
  );
}

export interface SmsThreadProps {
  messages: SmsMessage[];
  hasMoreBefore: boolean;
  loadingOlder: boolean;
  onLoadOlder: () => void;
}

export function SmsThread({ messages, hasMoreBefore, loadingOlder, onLoadOlder }: SmsThreadProps) {
  const retry = useRetrySms();
  const [retrying, setRetrying] = useState<SmsMessage | null>(null);

  return (
    <div>
      {hasMoreBefore ? (
        <div className="flex justify-center p-2">
          <Button variant="ghost" size="sm" onClick={onLoadOlder} disabled={loadingOlder}>
            {loadingOlder ? "Loading…" : "Load earlier messages"}
          </Button>
        </div>
      ) : null}
      <ul role="log" aria-label="SMS messages" aria-live="polite" className="space-y-3 p-3">
        {messages.map((message) => {
          const status = toStatus(message);
          return (
            <MessageBubble
              key={message.id}
              body={message.body ?? ""}
              timestamp={formatTime(message.created_at)}
              dateTime={message.created_at}
              timestampTitle={formatFull(message.created_at)}
              direction={message.direction === "outbound" ? "outgoing" : "incoming"}
              channel={message.direction === "outbound" ? "sms-outbound" : "sms-inbound"}
              smsMode={message.is_simulated ? "simulated" : "live"}
              {...(status ? { status } : {})}
              {...(statusDetail(message) ? { statusDetail: statusDetail(message) as string } : {})}
              footer={<MessageFooter message={message} onRetry={() => setRetrying(message)} />}
            />
          );
        })}
      </ul>
      {retry.isError ? (
        <p role="alert" className="px-3 pb-3 text-sm text-danger">
          {toUserFacingError(retry.error).message}
        </p>
      ) : null}
      <ConfirmDialog
        open={retrying !== null}
        onOpenChange={(open) => {
          if (!open) setRetrying(null);
        }}
        title="Send this message again?"
        description="This sends a new SMS with the same text. It is checked and counted like any other message."
        confirmLabel="Send again"
        onConfirm={() => {
          if (retrying) retry.mutate(retrying.id);
        }}
      />
    </div>
  );
}

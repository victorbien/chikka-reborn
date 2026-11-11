import { Paperclip, Send } from "lucide-react";
import { useId, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import type { MessageChannel, SmsMode } from "@/lib/types";
import { AiAssistedBadge, ChannelBadge } from "./ChannelBadge";
import { SmsCostEstimate } from "./SmsCostEstimate";

export interface MessageComposerProps {
  value: string;
  onChange: (value: string) => void;
  /** Called only on an explicit user action (button or Enter). */
  onSend: () => void;
  /** Outbound channel for this draft. */
  channel: Exclude<MessageChannel, "sms-inbound">;
  smsMode?: SmsMode;
  creditsPerSegment?: number;
  creditBalance?: number;
  aiAssisted?: boolean;
  isSending?: boolean;
  /** Explains why sending is blocked (opt-out, unsupported country, offline). */
  disabledReason?: string;
}

export function MessageComposer({
  value,
  onChange,
  onSend,
  channel,
  smsMode = "simulated",
  creditsPerSegment = 1,
  creditBalance,
  aiAssisted = false,
  isSending = false,
  disabledReason,
}: MessageComposerProps) {
  const inputId = useId();
  const reasonId = useId();
  const blocked = Boolean(disabledReason);
  const canSend = !blocked && !isSending && value.trim().length > 0;

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSend) onSend();
    }
  }

  return (
    <form
      className="space-y-2 border-t border-border bg-surface p-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSend) onSend();
      }}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-fg-muted">Sending via</span>
        <ChannelBadge channel={channel} smsMode={channel === "internet" ? undefined : smsMode} />
        {aiAssisted ? <AiAssistedBadge /> : null}
      </div>

      <div className="flex items-end gap-2">
        <Button
          size="icon"
          variant="ghost"
          disabled
          aria-label="Attach file (not available yet)"
          title="Attachments are not available yet"
        >
          <Paperclip aria-hidden className="size-4" />
        </Button>
        <div className="flex-1">
          <label htmlFor={inputId} className="sr-only">
            Message
          </label>
          <textarea
            id={inputId}
            value={value}
            rows={2}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={blocked}
            aria-describedby={blocked ? reasonId : undefined}
            placeholder="Write a message"
            className="w-full resize-none rounded-control border border-border bg-canvas p-2 text-sm text-fg placeholder:text-fg-muted disabled:opacity-60"
          />
        </div>
        <Button
          type="submit"
          disabled={!canSend}
          aria-label={isSending ? "Sending" : "Send message"}
        >
          <Send aria-hidden className="size-4" />
          <span className="hidden sm:inline">{isSending ? "Sending…" : "Send"}</span>
        </Button>
      </div>

      {blocked ? (
        <p id={reasonId} role="status" className="text-xs text-away">
          {disabledReason}
        </p>
      ) : null}

      {channel !== "internet" ? (
        <SmsCostEstimate
          body={value}
          smsMode={smsMode}
          creditsPerSegment={creditsPerSegment}
          creditBalance={creditBalance}
        />
      ) : null}
    </form>
  );
}

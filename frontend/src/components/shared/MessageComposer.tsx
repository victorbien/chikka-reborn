import { Paperclip, Send } from "lucide-react";
import { useId, useRef, type ChangeEvent, type KeyboardEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import type { MessageChannel, SmsMode } from "@/lib/types";
import { AiAssistedBadge, ChannelBadge } from "./ChannelBadge";
import { EmojiPicker } from "./EmojiPicker";
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
  /** Temporarily hold Send (e.g. while files upload) without calling it "Sending". */
  sendDisabled?: boolean;
  /** Explains why sending is blocked (opt-out, unsupported country, offline). */
  disabledReason?: string;
  /** Counted in Unicode code points, so one emoji is one character. */
  maxLength?: number;
  /** Called as the user types (throttling is the caller's job). */
  onTyping?: () => void;
  /** Enables the attach button. Absent means attachments are not offered here. */
  onAttach?: (files: File[]) => void;
  /** Explains why attachments are unavailable (shown on the disabled button). */
  attachUnavailableReason?: string;
  /** Allowed file types for the picker, e.g. "image/*,application/pdf". */
  accept?: string;
  /** Files waiting to be sent, rendered above the text box. */
  attachments?: ReactNode;
  /** Sending is allowed with an empty text when files are attached. */
  hasAttachments?: boolean;
  /** Offer the emoji picker. */
  emoji?: boolean;
  /** A readable error from the last attempt. */
  error?: ReactNode;
  autoFocus?: boolean;
}

function codePoints(value: string): number {
  return Array.from(value).length;
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
  sendDisabled = false,
  disabledReason,
  maxLength,
  onTyping,
  onAttach,
  attachUnavailableReason = "Attachments are not available yet",
  accept,
  attachments,
  hasAttachments = false,
  emoji = false,
  error,
  autoFocus = false,
}: MessageComposerProps) {
  const inputId = useId();
  const reasonId = useId();
  const counterId = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const blocked = Boolean(disabledReason);
  const length = codePoints(value);
  const tooLong = maxLength !== undefined && length > maxLength;
  const hasContent = value.trim().length > 0 || hasAttachments;
  const canSend = !blocked && !isSending && !sendDisabled && hasContent && !tooLong;
  const showCounter = maxLength !== undefined && length > maxLength * 0.9;

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a line; never while an IME is composing a character.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSend) onSend();
    }
  }

  function handleChange(event: ChangeEvent<HTMLTextAreaElement>) {
    onChange(event.target.value);
    if (event.target.value.trim()) onTyping?.();
  }

  function insertEmoji(char: string) {
    const input = textareaRef.current;
    const start = input?.selectionStart ?? value.length;
    const end = input?.selectionEnd ?? value.length;
    onChange(value.slice(0, start) + char + value.slice(end));
    const caret = start + char.length;
    setTimeout(() => {
      input?.focus();
      input?.setSelectionRange(caret, caret);
    }, 0);
  }

  const describedBy = [blocked ? reasonId : null, showCounter ? counterId : null]
    .filter(Boolean)
    .join(" ");

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

      {attachments}

      <div className="flex items-end gap-2">
        {onAttach ? (
          <>
            <Button
              size="icon"
              variant="ghost"
              aria-label="Attach file"
              disabled={blocked}
              onClick={() => fileRef.current?.click()}
            >
              <Paperclip aria-hidden className="size-4" />
            </Button>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept={accept}
              className="sr-only"
              tabIndex={-1}
              aria-hidden
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                event.target.value = "";
                if (files.length) onAttach(files);
              }}
            />
          </>
        ) : (
          <Button
            size="icon"
            variant="ghost"
            disabled
            aria-label={`Attach file (${attachUnavailableReason.toLowerCase()})`}
            title={attachUnavailableReason}
          >
            <Paperclip aria-hidden className="size-4" />
          </Button>
        )}
        {emoji ? <EmojiPicker onPick={insertEmoji} disabled={blocked} /> : null}
        <div className="flex-1">
          <label htmlFor={inputId} className="sr-only">
            Message
          </label>
          <textarea
            ref={textareaRef}
            id={inputId}
            value={value}
            rows={2}
            // Focus moves here deliberately when a conversation opens (FR-MSG-013 AC3).
            autoFocus={autoFocus}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            disabled={blocked}
            aria-invalid={tooLong || undefined}
            aria-describedby={describedBy || undefined}
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

      {showCounter ? (
        <p
          id={counterId}
          aria-live="polite"
          className={tooLong ? "text-xs text-danger" : "text-xs text-fg-muted"}
        >
          {length}/{maxLength} characters
          {tooLong ? ". Shorten your message to send it." : ""}
        </p>
      ) : null}

      {blocked ? (
        <p id={reasonId} role="status" className="text-xs text-away">
          {disabledReason}
        </p>
      ) : null}

      {error}

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

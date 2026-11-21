import { LiveBadge, SimulatedBadge } from "@/components/shared/ChannelBadge";
import { FormAlert } from "@/components/common/FormAlert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Quote } from "@/features/sms/types";

export interface SendConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  quote: Quote;
  body: string;
  pending: boolean;
  error?: string | undefined;
  onConfirm: () => void;
}

/** Every send is a deliberate act (FR-SMS-008): recipient, full text, segments, estimated cost
 *  and the mode, before anything is queued. */
export function SendConfirmDialog({
  open,
  onOpenChange,
  quote,
  body,
  pending,
  error,
  onConfirm,
}: SendConfirmDialogProps) {
  const name = quote.recipient.display_name;
  const credits = quote.cost.credits;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle className="flex flex-wrap items-center gap-2 text-lg font-semibold">
          Send this SMS? {quote.is_simulated ? <SimulatedBadge /> : <LiveBadge />}
        </DialogTitle>
        <DialogDescription className="mt-2 text-sm text-fg-muted">
          {quote.is_simulated
            ? "Simulation mode: no real SMS will be sent."
            : "This will send a real SMS to a real phone."}
        </DialogDescription>
        <dl className="mt-3 space-y-2 text-sm">
          <div>
            <dt className="text-fg-muted">To</dt>
            <dd>
              {name ? `${name} · ` : ""}
              {quote.recipient.masked_phone}
              {quote.recipient.country_name ? ` (${quote.recipient.country_name})` : ""}
            </dd>
          </div>
          <div>
            <dt className="text-fg-muted">Message</dt>
            <dd className="whitespace-pre-wrap break-words rounded-control border border-border p-2">
              {body}
            </dd>
          </div>
          <div>
            <dt className="text-fg-muted">Size and cost</dt>
            <dd>
              {quote.segment.segments} {quote.segment.segments === 1 ? "segment" : "segments"} ·{" "}
              {credits === null
                ? "cost unavailable"
                : `estimated ${credits.toFixed(2)} credits${
                    quote.is_simulated ? " demo credits, charged when accepted" : ""
                  }`}
            </dd>
          </div>
        </dl>
        {error ? (
          <FormAlert tone="error" className="mt-3">
            {error}
          </FormAlert>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <Button onClick={onConfirm} disabled={pending}>
            {pending ? "Sending…" : "Send SMS"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

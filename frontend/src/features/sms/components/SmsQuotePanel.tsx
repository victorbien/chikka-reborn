import { estimateSms } from "@/lib/sms";
import type { Quote, Replies } from "@/features/sms/types";

const REPLIES: Record<Replies, string> = {
  supported: "Replies can reach you here.",
  unverified: "Replies depend on the carrier and route, and are not guaranteed.",
  unsupported: "Replies are not supported for this destination.",
};

export interface SmsQuotePanelProps {
  body: string;
  quote: Quote | undefined;
  loading: boolean;
  /** The quote request itself failed (not a policy blocker). */
  failed: boolean;
  recipientName?: string;
  consentPending: boolean;
  onConsentChange: (granted: boolean) => void;
}

/** Segments, estimated cost, route warnings, consent and blockers: everything the user should
 *  see before sending. The server's numbers win; the local counter only keeps typing instant. */
export function SmsQuotePanel({
  body,
  quote,
  loading,
  failed,
  recipientName,
  consentPending,
  onConsentChange,
}: SmsQuotePanelProps) {
  const local = estimateSms(body);
  const segments = quote?.segment.segments ?? local.segments;
  const encoding = quote?.segment.encoding ?? (local.encoding === "gsm7" ? "gsm7" : "ucs2");
  const blockers = (quote?.blockers ?? []).filter((b) => b.code !== "consent_required");
  const cost = quote?.cost;

  let costText = "Cost unavailable";
  if (cost?.credits !== null && cost?.credits !== undefined) {
    costText = quote?.is_simulated
      ? `Estimated ${cost.credits.toFixed(2)} credits (nothing is charged in simulation${
          cost.source === "demo_default" ? ", demo rate" : ""
        })`
      : `Estimated ${cost.credits.toFixed(2)} credits`;
  }

  return (
    <div className="space-y-2 text-sm" aria-busy={loading}>
      <p aria-live="polite" className="text-xs text-fg-muted">
        {local.characters} characters · {segments} {segments === 1 ? "segment" : "segments"} ·{" "}
        {encoding === "gsm7" ? "GSM-7" : "Unicode"}
        {quote ? ` · ${costText}` : null}
      </p>
      {quote?.segment.too_long ? (
        <p role="alert" className="text-danger">
          This message needs {quote.segment.segments} segments. The limit here is{" "}
          {quote.segment.max_segments}.
        </p>
      ) : null}
      {quote ? <p className="text-xs text-fg-muted">{REPLIES[quote.replies]}</p> : null}
      {quote?.warnings.map((warning) => (
        <p key={warning} className="text-xs text-fg-muted">
          {warning}
        </p>
      ))}
      {quote?.consent.required ? (
        <label className="flex min-h-11 items-start gap-2">
          <input
            type="checkbox"
            className="mt-1 size-4"
            checked={quote.consent.granted}
            disabled={consentPending}
            onChange={(event) => onConsentChange(event.target.checked)}
          />
          <span>
            I have {recipientName ?? "this person"}&apos;s permission to text them, and I will stop
            if they ask.
          </span>
        </label>
      ) : null}
      {blockers.length > 0 ? (
        <ul role="alert" className="list-disc space-y-1 pl-5 text-danger">
          {blockers.map((blocker) => (
            <li key={blocker.code}>{blocker.message}</li>
          ))}
        </ul>
      ) : null}
      {failed ? (
        <p role="alert" className="text-danger">
          We couldn&apos;t check this message. Check the number and try again.
        </p>
      ) : null}
    </div>
  );
}

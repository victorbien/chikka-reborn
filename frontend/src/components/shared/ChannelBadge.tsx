import { Globe, PhoneIncoming, PhoneOutgoing, Sparkles, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MessageChannel, SmsMode } from "@/lib/types";

const CHANNELS: Record<MessageChannel, { label: string; Icon: LucideIcon; className: string }> = {
  internet: { label: "Internet", Icon: Globe, className: "border-accent text-accent" },
  "sms-outbound": { label: "SMS out", Icon: PhoneOutgoing, className: "bg-sms text-sms-fg border-transparent" },
  "sms-inbound": { label: "SMS in", Icon: PhoneIncoming, className: "bg-sms text-sms-fg border-transparent" },
};

export interface ChannelBadgeProps {
  channel: MessageChannel;
  /** Required for SMS channels so simulated and live are never confused. */
  smsMode?: SmsMode;
  className?: string;
}

const BADGE = "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold";

export function ChannelBadge({ channel, smsMode, className }: ChannelBadgeProps) {
  const { label, Icon, className: tone } = CHANNELS[channel];
  const isSms = channel !== "internet";
  return (
    <span className={cn("inline-flex flex-wrap items-center gap-1", className)}>
      <span className={cn(BADGE, tone)}>
        <Icon aria-hidden className="size-3" />
        {label}
      </span>
      {isSms && smsMode === "simulated" ? <SimulatedBadge /> : null}
      {isSms && smsMode === "live" ? (
        <span className={cn(BADGE, "border-transparent bg-live text-live-fg")}>LIVE</span>
      ) : null}
    </span>
  );
}

export function SimulatedBadge({ className }: { className?: string }) {
  return (
    <span className={cn(BADGE, "border-transparent bg-simulated text-simulated-fg", className)}>
      SIMULATED
    </span>
  );
}

export function AiAssistedBadge({ className }: { className?: string }) {
  return (
    <span className={cn(BADGE, "border-transparent bg-ai text-ai-fg", className)}>
      <Sparkles aria-hidden className="size-3" />
      AI-assisted
    </span>
  );
}

import { CheckCheck, Info } from "lucide-react";
import { ChannelBadge } from "@/components/shared/ChannelBadge";
import { PresenceIndicator } from "@/components/shared/PresenceIndicator";
import { formatFull } from "@/features/chat/format";
import { useConversation, useThread } from "@/features/chat/hooks/useChat";
import type { ChatMessage } from "@/features/chat/types";

function describe(message: ChatMessage | undefined, name: string): string {
  if (!message) return "You have not sent a message in this conversation yet.";
  if (message.status === "failed") {
    return "Your last message was not sent. Use “Try again” under it, or discard it.";
  }
  if (message.status === "pending") return "Your last message is being sent.";
  if (message.status === "read" && message.read_at) {
    return `Read by ${name} on ${formatFull(message.read_at)}.`;
  }
  if (message.status === "delivered" && message.delivered_at) {
    return `Delivered to ${name} on ${formatFull(message.delivered_at)}. Not read yet.`;
  }
  return `Sent. It shows as delivered once ${name} receives it.`;
}

/** Delivery information for the open conversation (Chikka-to-Chikka). SMS has its own
 *  statuses and is shown in the SMS area. */
export function DeliveryInfoPanel({ conversationId }: { conversationId: string }) {
  const conversation = useConversation(conversationId);
  const thread = useThread(conversationId);
  const participant = conversation.data?.participant;
  const name = participant?.display_name ?? "your contact";
  const lastMine = [...(thread.data?.messages ?? [])].reverse().find((m) => m.is_mine);

  return (
    <section aria-labelledby="delivery-info-heading" className="space-y-3">
      <h2 id="delivery-info-heading" className="flex items-center gap-2 text-sm font-semibold">
        <Info aria-hidden className="size-4 text-accent" />
        Conversation details
      </h2>
      {participant ? (
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-xs text-fg-muted">With</dt>
            <dd className="font-medium">
              {participant.display_name}
              {participant.username ? (
                <span className="text-fg-muted"> @{participant.username}</span>
              ) : null}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-fg-muted">Presence</dt>
            <dd>
              <PresenceIndicator status={participant.presence} showLabel />
            </dd>
          </div>
          <div>
            <dt className="text-xs text-fg-muted">Channel</dt>
            <dd className="space-y-1">
              <ChannelBadge channel="internet" />
              <span className="block text-xs text-fg-muted">
                Chikka to Chikka over the internet. No SMS is sent and no credits are used.
              </span>
            </dd>
          </div>
        </dl>
      ) : (
        <p role="status" className="text-sm text-fg-muted">
          Loading details…
        </p>
      )}
      <div className="rounded-panel border border-border bg-surface-raised p-3">
        <h3 className="flex items-center gap-2 text-xs font-semibold">
          <CheckCheck aria-hidden className="size-4" />
          Delivery
        </h3>
        <p className="mt-1 text-sm" aria-live="polite">
          {describe(lastMine, name)}
        </p>
      </div>
    </section>
  );
}

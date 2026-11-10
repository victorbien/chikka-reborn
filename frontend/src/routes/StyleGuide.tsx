import { Inbox } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { AiSuggestionPanel } from "@/components/shared/AiSuggestionPanel";
import { Avatar } from "@/components/shared/Avatar";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { ContactListItem } from "@/components/shared/ContactListItem";
import { ConversationItem } from "@/components/shared/ConversationItem";
import { CreditBalance } from "@/components/shared/CreditBalance";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { MessageBubble } from "@/components/shared/MessageBubble";
import { MessageComposer } from "@/components/shared/MessageComposer";
import { ModeSwitcher } from "@/components/shared/ModeSwitcher";
import { NotificationItem } from "@/components/shared/NotificationItem";
import type { MessageChannel, SmsMode } from "@/lib/types";

const SUGGESTIONS = ["Salamat! Ikaw din!", "Maayos naman, salamat. Ikaw?"];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-panel border border-border bg-surface p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

/** Living reference for tokens and shared components, driven by real handlers. */
export function StyleGuide() {
  const [draft, setDraft] = useState("");
  const [channel, setChannel] = useState<Exclude<MessageChannel, "sms-inbound">>("internet");
  const [smsMode, setSmsMode] = useState<SmsMode>("simulated");
  const [aiAssisted, setAiAssisted] = useState(false);
  const [sent, setSent] = useState<string[]>([]);
  const [showAi, setShowAi] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [read, setRead] = useState(false);
  const [selected, setSelected] = useState("Jericho Santos");

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4">
      <header>
        <h1 className="text-2xl font-bold">Chikka Reborn</h1>
        <p className="text-sm text-fg-muted">The Messenger That Refused to Die.</p>
        <p className="text-xs text-fg-muted">
          Independent, Chikka-inspired project. Not affiliated with the original service.
        </p>
      </header>

      <Section title="Display mode">
        <ModeSwitcher />
      </Section>

      <Section title="Buddy list and conversations">
        <Avatar name="Jericho Santos" presence="online" />
        {(["Jericho Santos", "Rowena Cruz", "Ben Reyes"] as const).map((name, index) => (
          <ContactListItem
            key={name}
            name={name}
            presence={index === 0 ? "online" : index === 1 ? "away" : "offline"}
            isSmsContact={index === 2}
            subtitle={index === 2 ? "+63****1234" : undefined}
            selected={selected === name}
            onSelect={() => setSelected(name)}
          />
        ))}
        <ConversationItem
          name="Nanay"
          lastMessagePreview="Kumain ka na ba?"
          timestamp="12:35"
          unreadCount={2}
          channel="sms-inbound"
          smsMode="simulated"
          onSelect={() => setSelected("Nanay")}
        />
      </Section>

      <Section title="Messages">
        <ul className="space-y-2">
          <MessageBubble body="Kumusta ka?" timestamp="12:34" direction="incoming" channel="internet" senderName="Jericho" />
          <MessageBubble body="Hello lola!" timestamp="12:36" direction="outgoing" channel="sms-outbound" smsMode="simulated" status="accepted" />
          <MessageBubble body="Sige, text mo ko mamaya." timestamp="12:37" direction="incoming" channel="sms-inbound" smsMode="simulated" senderName="Lola" />
          {sent.map((body, index) => (
            <MessageBubble key={`${index}-${body}`} body={body} timestamp="now" direction="outgoing" channel={channel} smsMode={channel === "internet" ? undefined : smsMode} status="queued" />
          ))}
        </ul>
      </Section>

      <Section title="Composer">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={() => setChannel(channel === "internet" ? "sms-outbound" : "internet")}>
            Channel: {channel === "internet" ? "Internet" : "SMS"}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setSmsMode(smsMode === "simulated" ? "live" : "simulated")} disabled={channel === "internet"}>
            SMS mode: {smsMode}
          </Button>
        </div>
        {showAi ? (
          <AiSuggestionPanel
            state="ready"
            suggestions={SUGGESTIONS}
            onUse={(text) => { setDraft(text); setAiAssisted(true); }}
            onRegenerate={() => setAiAssisted(false)}
            onDismiss={() => setShowAi(false)}
          />
        ) : (
          <Button size="sm" variant="ghost" onClick={() => setShowAi(true)}>Show AI suggestions</Button>
        )}
        <MessageComposer
          value={draft}
          onChange={(value) => { setDraft(value); }}
          onSend={() => { setSent((previous) => [...previous, draft]); setDraft(""); setAiAssisted(false); }}
          channel={channel}
          smsMode={smsMode}
          creditsPerSegment={0.05}
          creditBalance={0.04}
          aiAssisted={aiAssisted}
        />
      </Section>

      <Section title="Credits, notifications, states">
        <CreditBalance available={0.5} reserved={0.1} />
        <ul>
          <NotificationItem title="Low credit balance" description="Top up before sending live SMS." timestamp="Today" kind="warning" isRead={read} onMarkRead={() => setRead(true)} />
        </ul>
        <EmptyState icon={Inbox} title="No conversations yet" description="Add a contact to start your first chat." action={<Button onClick={() => setSelected("")}>Add a contact</Button>} />
        <ErrorState kind="offline" message="Check your connection and try again." onRetry={() => setConfirmOpen(false)} />
        <Button variant="destructive" onClick={() => setConfirmOpen(true)}>Delete conversation</Button>
        <ConfirmDialog open={confirmOpen} onOpenChange={setConfirmOpen} title="Delete conversation?" description="This removes the conversation from your account." confirmLabel="Delete" destructive onConfirm={() => setSent([])} />
      </Section>
    </main>
  );
}

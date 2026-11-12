import { useState } from "react";
import { BlockedPanel } from "@/features/contacts/components/BlockedPanel";
import { ContactProfileDrawer } from "@/features/contacts/components/ContactProfileDrawer";
import { ContactRequestsPanel } from "@/features/contacts/components/ContactRequestsPanel";
import { ContactSidebar } from "@/features/contacts/components/ContactSidebar";
import { RecentPanel } from "@/features/contacts/components/RecentPanel";
import { useRequests } from "@/features/contacts/hooks/useContacts";
import { cn } from "@/lib/utils";

type Tab = "contacts" | "requests" | "recent" | "blocked";

/** Contacts and buddy list (Module B). */
export function ContactsPage() {
  const [tab, setTab] = useState<Tab>("contacts");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const incoming = useRequests("incoming");
  const waiting = incoming.data?.pagination.total ?? 0;

  const tabs: { id: Tab; label: string }[] = [
    { id: "contacts", label: "Contacts" },
    { id: "requests", label: waiting > 0 ? `Requests (${waiting})` : "Requests" },
    { id: "recent", label: "Recent" },
    { id: "blocked", label: "Blocked" },
  ];

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold">Contacts</h1>
      <div role="group" aria-label="Contacts sections" className="flex flex-wrap gap-1">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-pressed={tab === item.id}
            onClick={() => setTab(item.id)}
            className={cn(
              "inline-flex min-h-11 items-center rounded-control px-3 text-sm font-medium hover:bg-surface-raised",
              tab === item.id ? "bg-surface-raised text-accent" : "text-fg",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>
      <section aria-label={tabs.find((item) => item.id === tab)?.label}>
        {tab === "contacts" ? (
          <ContactSidebar selectedId={selectedId} onSelect={setSelectedId} />
        ) : null}
        {tab === "requests" ? <ContactRequestsPanel /> : null}
        {tab === "recent" ? <RecentPanel onSelectContact={setSelectedId} /> : null}
        {tab === "blocked" ? <BlockedPanel /> : null}
      </section>
      <ContactProfileDrawer contactId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}

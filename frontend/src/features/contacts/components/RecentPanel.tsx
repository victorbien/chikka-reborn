import { Clock } from "lucide-react";
import { EmptyState } from "@/components/shared/EmptyState";
import { Avatar } from "@/components/shared/Avatar";
import { Button } from "@/components/ui/button";
import { ContactRow } from "@/features/contacts/components/ContactRow";
import { QueryError } from "@/features/contacts/components/QueryError";
import {
  useClearRecent,
  useRecentContacts,
  useRecentConversations,
} from "@/features/contacts/hooks/useContacts";

function when(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "";
}

/** Recent contacts (clearable) and recent conversations. Message text is never shown here. */
export function RecentPanel({ onSelectContact }: { onSelectContact: (contactId: string) => void }) {
  const recent = useRecentContacts();
  const conversations = useRecentConversations();
  const clear = useClearRecent();

  if (recent.isPending || conversations.isPending) return <p role="status">Loading recent…</p>;
  if (recent.isError) {
    return <QueryError error={recent.error} onRetry={() => void recent.refetch()} />;
  }
  if (conversations.isError) {
    return <QueryError error={conversations.error} onRetry={() => void conversations.refetch()} />;
  }
  if (recent.data.length === 0 && conversations.data.length === 0) {
    return (
      <EmptyState
        icon={Clock}
        title="Nothing recent yet"
        description="People and conversations you have been in touch with lately appear here."
      />
    );
  }
  return (
    <div className="space-y-5">
      <section aria-labelledby="recent-contacts-heading" className="space-y-1">
        <div className="flex items-center justify-between">
          <h3 id="recent-contacts-heading" className="text-sm font-semibold">
            Recent contacts
          </h3>
          {recent.data.length > 0 ? (
            <Button
              size="sm"
              variant="ghost"
              disabled={clear.isPending}
              onClick={() => clear.mutate(undefined)}
            >
              Clear list
            </Button>
          ) : null}
        </div>
        {recent.data.length === 0 ? (
          <p className="text-sm text-fg-muted">Cleared. Your conversations are untouched.</p>
        ) : (
          <ul>
            {recent.data.map((entry) => (
              <ContactRow
                key={entry.contact.id}
                contact={entry.contact}
                onSelect={onSelectContact}
              />
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="recent-conversations-heading" className="space-y-1">
        <h3 id="recent-conversations-heading" className="text-sm font-semibold">
          Recent conversations
        </h3>
        <ul className="space-y-1">
          {conversations.data.map((conversation) => (
            <li
              key={conversation.conversation_id}
              className="flex items-center gap-3 rounded-control px-2 py-1.5"
            >
              <Avatar
                name={conversation.display_name}
                imageUrl={conversation.avatar_url ?? undefined}
                size="sm"
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">
                  {conversation.display_name}
                </span>
                <span className="block truncate text-xs text-fg-muted">
                  {conversation.conversation_type === "sms"
                    ? `SMS · ${conversation.masked_phone ?? ""}`
                    : conversation.is_contact
                      ? "Chikka"
                      : "Chikka · not in your contacts"}
                </span>
              </span>
              <span className="text-xs text-fg-muted">{when(conversation.last_message_at)}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

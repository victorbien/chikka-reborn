import { Inbox, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ConversationItem } from "@/components/shared/ConversationItem";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatListTime } from "@/features/chat/format";
import { useConversations } from "@/features/chat/hooks/useChat";
import type { ConversationSummary } from "@/features/chat/types";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";

function preview(conversation: ConversationSummary): string {
  const last = conversation.last_message;
  if (!last) return "No messages yet";
  return last.is_mine ? `You: ${last.preview}` : last.preview;
}

export function ConversationList({ selectedId }: { selectedId?: string }) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [archived, setArchived] = useState(false);
  const debounced = useDebouncedValue(search, 300);
  const query = debounced.trim().length >= 2 ? debounced.trim() : "";
  const list = useConversations({ archived, q: query });

  return (
    <nav aria-label="Conversations" className="space-y-3">
      <div className="relative">
        <Search
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-muted"
        />
        <Input
          type="search"
          aria-label="Search conversations"
          placeholder="Search names and messages"
          className="pl-9"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      {query ? null : (
        <div role="group" aria-label="Show" className="flex gap-2">
          <Button
            size="sm"
            variant={archived ? "secondary" : "primary"}
            aria-pressed={!archived}
            onClick={() => setArchived(false)}
          >
            Inbox
          </Button>
          <Button
            size="sm"
            variant={archived ? "primary" : "secondary"}
            aria-pressed={archived}
            onClick={() => setArchived(true)}
          >
            Archived
          </Button>
        </div>
      )}

      {list.isPending ? <p role="status">Loading conversations…</p> : null}
      {list.isError ? (
        <ErrorState
          kind={toUserFacingError(list.error).kind}
          message={toUserFacingError(list.error).message}
          requestId={toUserFacingError(list.error).requestId}
          onRetry={() => void list.refetch()}
        />
      ) : null}
      {list.data && list.data.data.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={
            query
              ? "No conversations match"
              : archived
                ? "Nothing archived"
                : "No conversations yet"
          }
          description={
            query
              ? "Try a different name or word."
              : archived
                ? "Archived conversations come back when a new message arrives."
                : "Open a contact and choose Message to start chatting."
          }
        />
      ) : null}
      {list.data && list.data.data.length > 0 ? (
        <ul className="space-y-1">
          {list.data.data.map((conversation) => (
            <li key={conversation.id}>
              <ConversationItem
                name={conversation.participant.display_name}
                avatarUrl={conversation.participant.avatar_url ?? undefined}
                lastMessagePreview={preview(conversation)}
                timestamp={formatListTime(conversation.last_message_at)}
                unreadCount={conversation.is_muted ? 0 : conversation.unread_count}
                presence={conversation.participant.presence}
                channel="internet"
                selected={conversation.id === selectedId}
                onSelect={() => navigate(`${paths.messages}/${conversation.id}`)}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </nav>
  );
}

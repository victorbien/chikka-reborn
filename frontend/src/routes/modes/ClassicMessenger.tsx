import { ChevronDown, ChevronRight, Mail, MessagesSquare, Search, Users } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { FormAlert } from "@/components/common/FormAlert";
import { EmptyState } from "@/components/shared/EmptyState";
import { PresenceIndicator } from "@/components/shared/PresenceIndicator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tip } from "@/components/ui/tooltip";
import { ConversationView } from "@/features/chat/components/ConversationView";
import { useConversations } from "@/features/chat/hooks/useChat";
import { useContactList } from "@/features/contacts/hooks/useContacts";
import type { ContactSummary } from "@/features/contacts/types";
import { useArrowKeyNavigation } from "@/hooks/useArrowKeyNavigation";
import { useSlashToSearch } from "@/hooks/useSlashToSearch";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";
import { cn } from "@/lib/utils";
import { useOpenContact } from "@/routes/modes/useOpenContact";

const ONLINE_STATES = new Set(["online", "away", "busy"]);

function buddyName(contact: ContactSummary): string {
  return contact.nickname?.trim() || contact.display_name;
}

interface BuddyRowProps {
  contact: ContactSummary;
  unread: number;
  selected: boolean;
  disabled: boolean;
  onOpen: (contact: ContactSummary) => void;
}

function BuddyRow({ contact, unread, selected, disabled, onOpen }: BuddyRowProps) {
  const name = buddyName(contact);
  const subtitle =
    contact.nickname && contact.nickname !== contact.display_name
      ? contact.display_name
      : (contact.status_message ?? contact.masked_phone ?? "");
  return (
    <li>
      <Tip
        label={`${contact.display_name}${contact.status_message ? `: ${contact.status_message}` : ""}`}
        side="right"
      >
        <button
          type="button"
          data-buddy
          disabled={disabled}
          aria-current={selected ? "true" : undefined}
          onClick={() => onOpen(contact)}
          className={cn(
            "flex min-h-11 w-full items-center gap-2 rounded-control px-2 text-left hover:bg-surface-raised md:min-h-8",
            selected && "bg-surface-raised",
          )}
        >
          <PresenceIndicator status={contact.presence} />
          <span className="min-w-0 flex-1">
            <span className={cn("block truncate", unread > 0 && "font-bold")}>{name}</span>
            {subtitle ? (
              <span className="block truncate text-xs text-fg-muted">{subtitle}</span>
            ) : null}
          </span>
          {contact.contact_type === "sms" ? (
            <span className="rounded-control border border-sms px-1 text-[0.65rem] text-sms">
              SMS
            </span>
          ) : null}
          {unread > 0 ? (
            <span className="inline-flex items-center gap-1 text-accent">
              <Mail aria-hidden className="size-4 animate-notify" />
              <span className="text-xs font-bold">{unread}</span>
              <span className="sr-only">{unread} unread messages</span>
            </span>
          ) : null}
        </button>
      </Tip>
    </li>
  );
}

interface BuddyGroupProps {
  title: string;
  contacts: ContactSummary[];
  unreadByUser: Map<string, number>;
  selectedUserId: string | null;
  disabled: boolean;
  onOpen: (contact: ContactSummary) => void;
}

function BuddyGroup({
  title,
  contacts,
  unreadByUser,
  selectedUserId,
  disabled,
  onOpen,
}: BuddyGroupProps) {
  const [expanded, setExpanded] = useState(true);
  return (
    <section aria-label={title}>
      <button
        type="button"
        aria-expanded={expanded}
        data-buddy-group
        onClick={() => setExpanded((value) => !value)}
        className="flex min-h-11 w-full items-center gap-1 px-1 text-left text-xs font-bold hover:text-accent md:min-h-7"
      >
        {expanded ? (
          <ChevronDown aria-hidden className="size-3.5" />
        ) : (
          <ChevronRight aria-hidden className="size-3.5" />
        )}
        {title} ({contacts.length})
      </button>
      {expanded ? (
        <ul className="animate-enter">
          {contacts.map((contact) => (
            <BuddyRow
              key={contact.id}
              contact={contact}
              unread={contact.user_id ? (unreadByUser.get(contact.user_id) ?? 0) : 0}
              selected={contact.user_id !== null && contact.user_id === selectedUserId}
              disabled={disabled}
              onOpen={onOpen}
            />
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export interface ClassicMessengerProps {
  conversationId?: string;
  viewerId?: string;
}

/** Classic mode: a compact buddy list and a separate chat window, like early-2000s messengers.
 *  It reads the same queries as Modern mode; only the presentation differs. */
export function ClassicMessenger({ conversationId, viewerId }: ClassicMessengerProps) {
  const root = useRef<HTMLDivElement>(null);
  useSlashToSearch(root);
  // Up/Down/Home/End walk the whole list, across the Online and Offline groups.
  const onListKeyDown = useArrowKeyNavigation("button[data-buddy], button[data-buddy-group]");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const contacts = useContactList({ filter: "all", page });
  const conversations = useConversations({ archived: false, q: "" });
  const { open, isPending: opening, error: openError } = useOpenContact();

  const conversationList = conversations.data?.data;
  const unreadByUser = useMemo(() => {
    const map = new Map<string, number>();
    for (const conversation of conversationList ?? []) {
      if (conversation.is_muted) continue;
      map.set(conversation.participant.user_id, conversation.unread_count);
    }
    return map;
  }, [conversationList]);
  const totalUnread = [...unreadByUser.values()].reduce((sum, n) => sum + n, 0);
  const selected = conversationList?.find((c) => c.id === conversationId);

  const needle = search.trim().toLowerCase();
  const visible = (contacts.data?.data ?? []).filter(
    (contact) =>
      !needle ||
      [contact.display_name, contact.nickname ?? "", contact.username ?? ""].some((value) =>
        value.toLowerCase().includes(needle),
      ),
  );
  const byName = (a: ContactSummary, b: ContactSummary) => buddyName(a).localeCompare(buddyName(b));
  const online = visible.filter((c) => ONLINE_STATES.has(c.presence)).sort(byName);
  const offline = visible.filter((c) => !ONLINE_STATES.has(c.presence)).sort(byName);
  const onlineCount = (contacts.data?.data ?? []).filter((c) =>
    ONLINE_STATES.has(c.presence),
  ).length;
  const nickname = (() => {
    const userId = selected?.participant.user_id;
    const match = (contacts.data?.data ?? []).find((c) => c.user_id === userId);
    return match?.nickname?.trim() || null;
  })();

  return (
    <div
      ref={root}
      className="grid gap-2 md:h-[calc(100dvh-9rem)] md:min-h-[28rem] md:grid-cols-[16rem_1fr]"
    >
      <h1 className="sr-only">Messages</h1>
      <section
        aria-labelledby="buddy-list-title"
        className={cn(
          "flex min-h-0 flex-col rounded-panel border border-border bg-surface bevel",
          conversationId ? "hidden md:flex" : "flex",
        )}
      >
        <h2
          id="buddy-list-title"
          className="border-b border-border bg-surface-raised px-2 py-1 text-xs font-bold"
        >
          Buddy list
        </h2>
        <div className="relative p-2">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-4 top-1/2 size-3.5 -translate-y-1/2 text-fg-muted"
          />
          <Input
            type="search"
            aria-label="Search buddies"
            placeholder="Find a buddy ( / )"
            className="min-h-11 pl-7 md:min-h-8"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div onKeyDown={onListKeyDown} className="min-h-0 flex-1 overflow-y-auto px-1 pb-1">
          {contacts.isPending ? (
            <p role="status" className="p-2 text-fg-muted">
              Loading buddies…
            </p>
          ) : null}
          {contacts.isError ? (
            <div className="space-y-2 p-2">
              <FormAlert tone="error" requestId={toUserFacingError(contacts.error).requestId}>
                {toUserFacingError(contacts.error).message}
              </FormAlert>
              <Button size="sm" variant="secondary" onClick={() => void contacts.refetch()}>
                Try again
              </Button>
            </div>
          ) : null}
          {openError ? (
            <FormAlert tone="error">{toUserFacingError(openError).message}</FormAlert>
          ) : null}
          {contacts.data && contacts.data.data.length === 0 ? (
            <EmptyState
              icon={Users}
              title="Your buddy list is empty"
              description="Add people by username and they will appear here once they accept."
              action={
                <Button asChild size="sm" variant="secondary">
                  <Link to={paths.contacts}>Add buddies</Link>
                </Button>
              }
            />
          ) : null}
          {contacts.data && contacts.data.data.length > 0 && visible.length === 0 ? (
            <p role="status" className="p-2 text-fg-muted">
              No buddies match “{search.trim()}”.
            </p>
          ) : null}
          {online.length > 0 ? (
            <BuddyGroup
              title="Online"
              contacts={online}
              unreadByUser={unreadByUser}
              selectedUserId={selected?.participant.user_id ?? null}
              disabled={opening}
              onOpen={open}
            />
          ) : null}
          {offline.length > 0 ? (
            <BuddyGroup
              title="Offline"
              contacts={offline}
              unreadByUser={unreadByUser}
              selectedUserId={selected?.participant.user_id ?? null}
              disabled={opening}
              onOpen={open}
            />
          ) : null}
          {contacts.data &&
          (contacts.data.pagination.has_prev || contacts.data.pagination.has_next) ? (
            <div className="flex justify-between gap-2 p-1">
              <Button
                size="sm"
                variant="secondary"
                disabled={!contacts.data.pagination.has_prev}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={!contacts.data.pagination.has_next}
                onClick={() => setPage(page + 1)}
              >
                Next
              </Button>
            </div>
          ) : null}
        </div>
        <p
          role="status"
          className="flex items-center justify-between border-t border-border bg-surface-raised px-2 py-1 text-xs"
        >
          <span>
            {onlineCount} online · {contacts.data?.pagination.total ?? 0} total
          </span>
          {totalUnread > 0 ? (
            <span className="inline-flex items-center gap-1 text-accent">
              <Mail aria-hidden className="size-3.5 animate-notify" />
              {totalUnread} new
            </span>
          ) : null}
        </p>
      </section>

      <div
        className={cn(
          "min-h-0 overflow-hidden rounded-panel border border-border bg-surface bevel",
          conversationId ? "block" : "hidden md:block",
        )}
      >
        {conversationId && viewerId ? (
          <ConversationView
            key={conversationId}
            conversationId={conversationId}
            viewerId={viewerId}
            variant="classic"
            nickname={nickname}
            className="min-h-[60vh] md:h-full md:min-h-0"
          />
        ) : (
          <EmptyState
            icon={MessagesSquare}
            title="No chat window open"
            description="Choose a buddy from the list to start chatting."
          />
        )}
      </div>
    </div>
  );
}

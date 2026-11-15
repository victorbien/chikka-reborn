import { MessagesSquare, Search, Settings, Sparkles, Users } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { FormAlert } from "@/components/common/FormAlert";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tip } from "@/components/ui/tooltip";
import { AiAssistantPanel } from "@/features/ai/components/AiAssistantPanel";
import type { ComposerSuggestion } from "@/features/chat/components/ChatComposer";
import { ConversationList } from "@/features/chat/components/ConversationList";
import { ConversationView } from "@/features/chat/components/ConversationView";
import { DeliveryInfoPanel } from "@/features/chat/components/DeliveryInfoPanel";
import { ContactRow } from "@/features/contacts/components/ContactRow";
import { useContactList } from "@/features/contacts/hooks/useContacts";
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/useMediaQuery";
import { useSlashToSearch } from "@/hooks/useSlashToSearch";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";
import { cn } from "@/lib/utils";
import { useOpenContact } from "@/routes/modes/useOpenContact";

function PeopleTab() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const contacts = useContactList({ filter: "all", page });
  const { open, isPending, error } = useOpenContact();
  const needle = search.trim().toLowerCase();
  const all = contacts.data?.data ?? [];
  const visible = all.filter(
    (contact) =>
      !needle ||
      [contact.display_name, contact.nickname ?? "", contact.username ?? ""].some((value) =>
        value.toLowerCase().includes(needle),
      ),
  );

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-muted"
        />
        <Input
          type="search"
          aria-label="Search contacts"
          placeholder="Search contacts"
          className="pl-9"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      {contacts.isPending ? <p role="status">Loading contacts…</p> : null}
      {contacts.isError ? (
        <div className="space-y-2">
          <FormAlert tone="error" requestId={toUserFacingError(contacts.error).requestId}>
            {toUserFacingError(contacts.error).message}
          </FormAlert>
          <Button size="sm" variant="secondary" onClick={() => void contacts.refetch()}>
            Try again
          </Button>
        </div>
      ) : null}
      {error ? <FormAlert tone="error">{toUserFacingError(error).message}</FormAlert> : null}
      {contacts.data && all.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No contacts yet"
          description="Find people by their exact username and send a request."
          action={
            <Button asChild variant="secondary">
              <Link to={paths.contacts}>Add contacts</Link>
            </Button>
          }
        />
      ) : null}
      {contacts.data && all.length > 0 && visible.length === 0 ? (
        <p role="status" className="text-sm text-fg-muted">
          No contacts match “{search.trim()}”.
        </p>
      ) : null}
      {visible.length > 0 ? (
        <ul aria-label="Contacts" aria-busy={isPending}>
          {visible.map((contact) => (
            <ContactRow key={contact.id} contact={contact} onSelect={() => open(contact)} />
          ))}
        </ul>
      ) : null}
      {contacts.data && (contacts.data.pagination.has_prev || contacts.data.pagination.has_next) ? (
        <div className="flex justify-between gap-2">
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
  );
}

export interface ModernMessengerProps {
  conversationId?: string;
  viewerId?: string;
}

/** Modern mode: conversations and contacts, the open conversation, and (on desktop) a side
 *  column with delivery details and the AI assistant. On small screens it is one column at a time. */
export function ModernMessenger({ conversationId, viewerId }: ModernMessengerProps) {
  const root = useRef<HTMLDivElement>(null);
  useSlashToSearch(root);
  const desktop = useMediaQuery(DESKTOP_QUERY);
  const [draft, setDraft] = useState("");
  const [suggestion, setSuggestion] = useState<ComposerSuggestion | null>(null);
  const [aiOpen, setAiOpen] = useState(true);
  const suggestionId = useRef(0);
  const onDraftChange = useCallback((value: string) => setDraft(value), []);

  const showSide = desktop && Boolean(conversationId && viewerId);

  return (
    <div
      ref={root}
      className={cn(
        "grid gap-4 md:h-[calc(100dvh-8rem)] md:min-h-[32rem] md:grid-cols-[19rem_minmax(0,1fr)]",
        showSide && "lg:grid-cols-[19rem_minmax(0,1fr)_21rem]",
      )}
    >
      <h1 className="sr-only">Messages</h1>

      <div
        className={cn(
          "min-h-0 flex-col md:flex md:overflow-y-auto",
          conversationId ? "hidden" : "flex",
        )}
      >
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Chats and people</h2>
          <Tip label="Settings">
            <Button asChild variant="ghost" size="icon">
              <Link to={paths.settings} aria-label="Settings">
                <Settings aria-hidden className="size-4" />
              </Link>
            </Button>
          </Tip>
        </div>
        <Tabs defaultValue="chats">
          <TabsList aria-label="Chats or people">
            <TabsTrigger value="chats">Chats</TabsTrigger>
            <TabsTrigger value="people">People</TabsTrigger>
          </TabsList>
          <TabsContent value="chats">
            <ConversationList selectedId={conversationId} />
          </TabsContent>
          <TabsContent value="people">
            <PeopleTab />
          </TabsContent>
        </Tabs>
      </div>

      <div
        className={cn(
          "min-h-0 overflow-hidden rounded-panel border border-border bg-surface",
          conversationId ? "block" : "hidden md:block",
        )}
      >
        {conversationId && viewerId ? (
          <ConversationView
            key={conversationId}
            conversationId={conversationId}
            viewerId={viewerId}
            className="min-h-[60vh] md:h-full md:min-h-0"
            suggestion={suggestion}
            onDraftChange={onDraftChange}
            showAiToggle={!showSide}
          />
        ) : (
          <EmptyState
            icon={MessagesSquare}
            title="Choose a conversation"
            description="Pick a chat, or open a person from the People tab."
          />
        )}
      </div>

      {showSide && conversationId ? (
        <aside
          aria-label="Conversation tools"
          className="animate-enter min-h-0 space-y-4 overflow-y-auto"
        >
          <div className="rounded-panel border border-border bg-surface p-3">
            <DeliveryInfoPanel conversationId={conversationId} />
          </div>
          {aiOpen ? (
            <AiAssistantPanel
              draft={draft}
              conversationId={conversationId}
              channel="chat"
              onUse={(text) => {
                suggestionId.current += 1;
                setSuggestion({ id: suggestionId.current, text });
              }}
              onClose={() => setAiOpen(false)}
            />
          ) : (
            <Button variant="secondary" aria-expanded={false} onClick={() => setAiOpen(true)}>
              <Sparkles aria-hidden className="size-4 text-ai" />
              Show AI assistant
            </Button>
          )}
        </aside>
      ) : null}
    </div>
  );
}

import { Users } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { AddContactDialog } from "@/features/contacts/components/AddContactDialog";
import { ContactRow } from "@/features/contacts/components/ContactRow";
import { ContactSearch } from "@/features/contacts/components/ContactSearch";
import { GroupManager } from "@/features/contacts/components/GroupManager";
import { QueryError } from "@/features/contacts/components/QueryError";
import { useContactList, useGroups, useUpdateContact } from "@/features/contacts/hooks/useContacts";
import type { ContactFilter, ContactSummary } from "@/features/contacts/types";

const FILTERS: { value: Exclude<ContactFilter, "group">; label: string }[] = [
  { value: "all", label: "All" },
  { value: "online", label: "Online" },
  { value: "offline", label: "Offline" },
  { value: "favourites", label: "Favourites" },
];

export interface ContactSidebarProps {
  selectedId: string | null;
  onSelect: (contactId: string) => void;
}

/** The buddy list: search, filters, groups and the contacts themselves. */
export function ContactSidebar({ selectedId, onSelect }: ContactSidebarProps) {
  const [filter, setFilter] = useState<ContactFilter>("all");
  const [groupId, setGroupId] = useState<string>("");
  const [page, setPage] = useState(1);
  const [searching, setSearching] = useState(false);
  const groups = useGroups();
  const favourite = useUpdateContact();

  const activeFilter: ContactFilter = filter === "group" && !groupId ? "all" : filter;
  const list = useContactList({
    filter: activeFilter,
    groupId: activeFilter === "group" ? groupId : undefined,
    page,
  });

  const choose = (next: ContactFilter) => {
    setFilter(next);
    setPage(1);
  };
  const toggleFavourite = (contact: ContactSummary) =>
    favourite.mutate({ id: contact.id, changes: { is_favourite: !contact.is_favourite } });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <AddContactDialog />
        <GroupManager />
      </div>
      <ContactSearch onSelectContact={onSelect} onActiveChange={setSearching} />

      {searching ? null : (
        <>
          <div role="group" aria-label="Filter contacts" className="flex flex-wrap gap-2">
            {FILTERS.map((option) => (
              <Button
                key={option.value}
                size="sm"
                variant={activeFilter === option.value ? "primary" : "secondary"}
                aria-pressed={activeFilter === option.value}
                onClick={() => choose(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
          {groups.data && groups.data.length > 0 ? (
            <label className="flex flex-col gap-1 text-sm font-medium">
              Group
              <Select
                value={activeFilter === "group" ? groupId : ""}
                onChange={(event) => {
                  setGroupId(event.target.value);
                  choose(event.target.value ? "group" : "all");
                }}
              >
                <option value="">No group filter</option>
                {groups.data.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name} ({group.member_count})
                  </option>
                ))}
              </Select>
            </label>
          ) : null}

          {list.isPending ? <p role="status">Loading contacts…</p> : null}
          {list.isError ? (
            <QueryError error={list.error} onRetry={() => void list.refetch()} />
          ) : null}
          {list.data && list.data.data.length === 0 ? (
            <EmptyState
              icon={Users}
              title={activeFilter === "all" ? "No contacts yet" : "Nobody matches this filter"}
              description={
                activeFilter === "all"
                  ? "Find people by their exact username and send a request. They appear here once they accept."
                  : "Try another filter to see more of your contacts."
              }
            />
          ) : null}
          {list.data && list.data.data.length > 0 ? (
            <>
              <ul aria-label="Contacts">
                {list.data.data.map((contact) => (
                  <ContactRow
                    key={contact.id}
                    contact={contact}
                    selected={contact.id === selectedId}
                    onSelect={onSelect}
                    onToggleFavourite={toggleFavourite}
                  />
                ))}
              </ul>
              <div className="flex items-center justify-between text-xs text-fg-muted">
                <span>
                  {list.data.pagination.total}{" "}
                  {list.data.pagination.total === 1 ? "contact" : "contacts"}
                </span>
                {list.data.pagination.has_prev || list.data.pagination.has_next ? (
                  <span className="flex gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={!list.data.pagination.has_prev}
                      onClick={() => setPage(page - 1)}
                    >
                      Previous
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={!list.data.pagination.has_next}
                      onClick={() => setPage(page + 1)}
                    >
                      Next
                    </Button>
                  </span>
                ) : null}
              </div>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}

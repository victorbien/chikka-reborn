import { Search } from "lucide-react";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { ContactRow } from "@/features/contacts/components/ContactRow";
import { PersonResult } from "@/features/contacts/components/PersonResult";
import { QueryError } from "@/features/contacts/components/QueryError";
import { useContactSearch } from "@/features/contacts/hooks/useContacts";
import { MIN_SEARCH_LENGTH } from "@/features/contacts/schemas";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const DEBOUNCE_MS = 300;

export interface ContactSearchProps {
  onSelectContact: (contactId: string) => void;
  /** Called with true while a search is active, so the parent can hide the buddy list. */
  onActiveChange?: (active: boolean) => void;
}

/** Search your contacts by name, or find a person by exact username, email or number. */
export function ContactSearch({ onSelectContact, onActiveChange }: ContactSearchProps) {
  const [text, setText] = useState("");
  const debounced = useDebouncedValue(text, DEBOUNCE_MS);
  const search = useContactSearch(debounced);
  const long = text.trim().length >= MIN_SEARCH_LENGTH;

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-muted"
        />
        <Input
          type="search"
          aria-label="Search contacts"
          placeholder="Search contacts or find a username"
          className="pl-9"
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            onActiveChange?.(event.target.value.trim().length >= MIN_SEARCH_LENGTH);
          }}
        />
      </div>
      {long ? (
        <div aria-live="polite" className="space-y-2">
          {text.trim() !== debounced.trim() || search.isFetching ? (
            <p role="status" className="px-2 text-sm text-fg-muted">
              Searching…
            </p>
          ) : null}
          {search.isError ? (
            <QueryError error={search.error} onRetry={() => void search.refetch()} />
          ) : null}
          {search.data ? (
            <>
              {search.data.contacts.length > 0 ? (
                <section aria-label="Your contacts">
                  <h3 className="px-2 text-xs font-semibold uppercase text-fg-muted">
                    Your contacts
                  </h3>
                  <ul>
                    {search.data.contacts.map((contact) => (
                      <ContactRow key={contact.id} contact={contact} onSelect={onSelectContact} />
                    ))}
                  </ul>
                </section>
              ) : null}
              {search.data.people.length > 0 ? (
                <section aria-label="People">
                  <h3 className="px-2 text-xs font-semibold uppercase text-fg-muted">People</h3>
                  <ul>
                    {search.data.people.map((person) => (
                      <PersonResult
                        key={person.user_id}
                        person={person}
                        onOpenContact={onSelectContact}
                      />
                    ))}
                  </ul>
                </section>
              ) : null}
              {search.data.contacts.length === 0 && search.data.people.length === 0 ? (
                <p className="px-2 text-sm text-fg-muted">
                  No matches. To add someone new, enter their exact username, or an email or number
                  they have chosen to share.
                </p>
              ) : null}
            </>
          ) : null}
        </div>
      ) : text.trim().length > 0 ? (
        <p className="px-2 text-xs text-fg-muted">Type at least 2 characters.</p>
      ) : null}
    </div>
  );
}

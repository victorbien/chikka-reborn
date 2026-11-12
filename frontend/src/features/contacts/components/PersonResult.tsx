import { Avatar } from "@/components/shared/Avatar";
import { FormAlert } from "@/components/common/FormAlert";
import { Button } from "@/components/ui/button";
import { useSendRequest } from "@/features/contacts/hooks/useContacts";
import type { SearchPerson } from "@/features/contacts/types";
import { toUserFacingError } from "@/lib/error-handling";

export interface PersonResultProps {
  person: SearchPerson;
  note?: string | null;
  onOpenContact?: (contactId: string) => void;
}

/** A person found by exact username, email or number, with the right next step. */
export function PersonResult({ person, note = null, onOpenContact }: PersonResultProps) {
  const send = useSendRequest();
  const name = person.display_name;

  let action;
  if (person.relationship === "contact" && person.contact_id) {
    const contactId = person.contact_id;
    action = onOpenContact ? (
      <Button size="sm" variant="secondary" onClick={() => onOpenContact(contactId)}>
        View contact
      </Button>
    ) : (
      <span className="text-xs text-fg-muted">Already a contact</span>
    );
  } else if (person.relationship === "request_sent" || send.data?.status === "sent") {
    // Shown for every outcome of a send, so a blocked sender sees the same thing.
    action = <span className="text-xs text-fg-muted">Request sent</span>;
  } else if (send.data?.status === "contacts") {
    action = <span className="text-xs text-fg-muted">Now contacts</span>;
  } else if (person.relationship === "request_received") {
    action = <span className="text-xs text-fg-muted">Sent you a request. See Requests.</span>;
  } else {
    action = (
      <Button
        size="sm"
        disabled={send.isPending}
        aria-label={`Add ${name}`}
        onClick={() => send.mutate({ userId: person.user_id, note })}
      >
        {send.isPending ? "Sending…" : "Add"}
      </Button>
    );
  }

  return (
    <li className="space-y-1">
      <div className="flex items-center gap-3 rounded-control px-2 py-1.5">
        <Avatar name={name} imageUrl={person.avatar_url ?? undefined} size="sm" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{name}</span>
          {person.username ? (
            <span className="block truncate text-xs text-fg-muted">@{person.username}</span>
          ) : null}
        </span>
        {action}
      </div>
      {send.error ? (
        <FormAlert tone="error" requestId={toUserFacingError(send.error).requestId}>
          {toUserFacingError(send.error).message}
        </FormAlert>
      ) : null}
    </li>
  );
}

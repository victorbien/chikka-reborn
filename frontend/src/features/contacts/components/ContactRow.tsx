import { Star } from "lucide-react";
import { ContactListItem } from "@/components/shared/ContactListItem";
import type { ContactSummary } from "@/features/contacts/types";
import { cn } from "@/lib/utils";

export interface ContactRowProps {
  contact: ContactSummary;
  selected?: boolean;
  onSelect: (contactId: string) => void;
  onToggleFavourite?: (contact: ContactSummary) => void;
}

/** One buddy-list entry: avatar, name, presence, status message and a favourite star. */
export function ContactRow({ contact, selected, onSelect, onToggleFavourite }: ContactRowProps) {
  const isSms = contact.contact_type === "sms";
  return (
    <li className="flex items-center gap-1">
      <div className="min-w-0 flex-1">
        <ContactListItem
          name={contact.display_name}
          subtitle={contact.status_message ?? contact.masked_phone ?? undefined}
          presence={contact.presence}
          isSmsContact={isSms}
          selected={selected}
          onSelect={() => onSelect(contact.id)}
        />
      </div>
      {onToggleFavourite ? (
        <button
          type="button"
          aria-pressed={contact.is_favourite}
          aria-label={`Favourite ${contact.display_name}`}
          onClick={() => onToggleFavourite(contact)}
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-control hover:bg-surface-raised"
        >
          <Star
            aria-hidden
            className={cn("size-4", contact.is_favourite ? "fill-away text-away" : "text-fg-muted")}
          />
        </button>
      ) : null}
    </li>
  );
}

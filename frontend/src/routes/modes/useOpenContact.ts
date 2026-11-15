import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useOpenConversation } from "@/features/chat/hooks/useChat";
import type { ContactSummary } from "@/features/contacts/types";
import { paths } from "@/lib/paths";

/** Opens the right conversation for a contact. Used by both Classic and Modern, so a contact
 *  leads to the same place whichever interface is on. */
export function useOpenContact() {
  const navigate = useNavigate();
  const { mutate, isPending, error, reset } = useOpenConversation();

  const open = useCallback(
    (contact: ContactSummary) => {
      if (contact.contact_type === "sms" || !contact.user_id) {
        navigate(`${paths.smsNew}?contact=${encodeURIComponent(contact.id)}`);
        return;
      }
      reset();
      mutate(contact.user_id, {
        onSuccess: (summary) => navigate(`${paths.messages}/${summary.id}`),
      });
    },
    [mutate, navigate, reset],
  );

  return { open, isPending, error };
}

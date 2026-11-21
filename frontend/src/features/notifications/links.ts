import { paths } from "@/lib/paths";
import type { AppNotification } from "@/features/notifications/types";

/** Where a notification leads, or null when there is nothing more to open. */
export function notificationLink(
  notification: Pick<AppNotification, "type" | "reference_type" | "reference_id">,
): string | null {
  switch (notification.type) {
    case "new_message":
      return notification.reference_id
        ? `${paths.messages}/${notification.reference_id}`
        : paths.messages;
    case "sms_inbound":
    case "sms_delivered":
    case "sms_failed":
      return paths.sms;
    case "contact_request":
    case "contact_accepted":
      return paths.contacts;
    case "low_balance":
      return paths.credits;
    case "security":
      return paths.settings;
    case "system":
      return notification.reference_type === "credit_transaction" ? paths.credits : null;
  }
}

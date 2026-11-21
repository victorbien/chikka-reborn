/** Mirrors backend/app/modules/notifications/schemas.py. */

export type NotificationType =
  | "new_message"
  | "sms_inbound"
  | "sms_delivered"
  | "sms_failed"
  | "contact_request"
  | "contact_accepted"
  | "low_balance"
  | "system"
  | "security";

export const NOTIFICATION_TYPES: readonly NotificationType[] = [
  "new_message",
  "sms_inbound",
  "sms_delivered",
  "sms_failed",
  "contact_request",
  "contact_accepted",
  "low_balance",
  "system",
  "security",
];

export type Channel = "in_app" | "push" | "email";

export interface AppNotification {
  id: string;
  type: NotificationType;
  title: string;
  body: string | null;
  reference_type: string | null;
  reference_id: string | null;
  /** How many events a grouped notification stands for (for example 3 new messages). */
  occurrence_count: number;
  is_read: boolean;
  created_at: string;
}

export interface NotificationPage {
  data: AppNotification[];
  pagination: {
    total: number;
    page: number;
    page_size: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface PreferenceType {
  type: NotificationType;
  in_app: boolean;
  push: boolean;
  email: boolean;
  /** Notices that always appear in the app. */
  in_app_locked: boolean;
}

export interface NotificationPreferences {
  types: PreferenceType[];
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  show_previews: boolean;
  low_balance_threshold_units: number;
  low_balance_threshold_credits: number;
  email_disabled: boolean;
  email_simulated: boolean;
}

export interface PreferencesUpdate {
  types?: Partial<Record<NotificationType, Partial<Record<Channel, boolean>>>>;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  show_previews?: boolean;
  low_balance_threshold_units?: number;
}

/** The `notification.created` real-time event. */
export interface NotificationCreatedEvent {
  notification: AppNotification;
  browser: boolean;
  unread_count: number;
}

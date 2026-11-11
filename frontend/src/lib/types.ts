/** Delivery states mirror sms-provider-guidelines. "accepted" is never "delivered". */
export type MessageStatus = "queued" | "accepted" | "sent" | "delivered" | "failed" | "undelivered";

/** How a message travels. Every bubble and the composer must show one. */
export type MessageChannel = "internet" | "sms-outbound" | "sms-inbound";

/** Whether an SMS is real. Internet messages have no SMS mode. */
export type SmsMode = "simulated" | "live";

export type PresenceStatus = "online" | "away" | "offline";

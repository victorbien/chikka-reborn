# Module G — Notifications (`NOTIF`)

Part of the [Functional Requirements Specification](../functional-requirements.md). Notification types: `new_message`, `sms_inbound`, `sms_delivered`, `sms_failed`, `contact_request`, `contact_accepted`, `low_balance`, `system`. Notifications about simulated SMS carry the SIMULATED label. Email and push content never includes full message bodies (only a short preview, and none for SMS content unless the user opts in).

---

### FR-NOTIF-001 — In-App Message Alerts

| Field | Detail |
|---|---|
| Module | G — Notifications |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users see unread indicators and incoming message alerts inside the app. |
| Preconditions | Signed in. Conversation not muted (FR-CONTACTS-006). |
| Trigger | A new message arrives in a conversation the user is not viewing. |
| Main workflow | 1) Unread count increments on the conversation row. 2) The browser tab title shows the total unread count. 3) A brief toast with the sender and preview appears (if enabled). 4) Opening the conversation clears the count. |
| Alternative workflows | A) Do-not-disturb (presence `busy`) suppresses toasts and sound but keeps counts. B) Sound is optional and off by default. |
| Expected result | Users never miss a message when the app is open. |
| Error scenarios | Realtime failure: counts reconcile on reconnect. |
| Dependencies | FR-MSG-007. |
| Acceptance criteria | AC1 Count clears on open. AC2 Toasts are announced via ARIA live regions without stealing focus. AC3 Muted conversations create no toast or count in the title. AC4 Counts persist across reloads. |

### FR-NOTIF-002 — Browser Push Notifications

| Field | Detail |
|---|---|
| Module | G — Notifications |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users receive browser notifications when the app is in the background. |
| Preconditions | User granted browser permission and enabled the setting. |
| Trigger | Incoming message or alert while the tab is hidden. |
| Main workflow | 1) The app explains the benefit before requesting permission. 2) The browser permission is requested only after the user clicks "Enable". 3) A service worker subscription is registered (Web Push). 4) The backend sends a notification with the sender name and a generic or short preview per settings. 5) Clicking opens the conversation. |
| Alternative workflows | A) Permission denied: a help message explains how to change it. B) Unsupported browser: option hidden. |
| Expected result | Timely alerts that respect privacy. |
| Error scenarios | Subscription expired (410): removed. Delivery failure: ignored, in-app notification still exists. |
| Dependencies | Web Push (VAPID keys in environment), FR-NOTIF-005. |
| Acceptance criteria | AC1 Permission is never requested on page load. AC2 Previews can be hidden. AC3 Muted contacts do not push. AC4 Subscription is removed on logout. |

### FR-NOTIF-003 — SMS Delivery Alerts

| Field | Detail |
|---|---|
| Module | G — Notifications |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Users are told when an SMS they sent is delivered or fails. |
| Preconditions | Message status changed to `delivered`, `failed` or `undelivered`. |
| Trigger | Status event (FR-SMS-004). |
| Main workflow | 1) An in-app notification is created with recipient name or masked number and the status. 2) Failed ones include the reason category and actions: retry, edit or dismiss. 3) Simulated messages say "(SIMULATED)". |
| Alternative workflows | A) Delivered alerts can be disabled in preferences. Failed alerts cannot be disabled in-app. B) Several failures in a short time are grouped. |
| Expected result | Honest status awareness. |
| Error scenarios | Notification write failure: logged and retried. |
| Dependencies | FR-SMS-004, FR-SMS-010. |
| Acceptance criteria | AC1 "Accepted" never generates a "Delivered" alert. AC2 Permanent failure alert appears after retries end. AC3 Alerts link to the message. AC4 Phone numbers are masked in notification text for push and email. |

### FR-NOTIF-004 — Low-Balance Notification

| Field | Detail |
|---|---|
| Module | G — Notifications |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** (simulation: refers to demo credits) |
| Description | Users are warned when their credit balance falls under a threshold. |
| Preconditions | Threshold configured (default 5 credits; user can change). |
| Trigger | A deduction takes the balance below the threshold. |
| Main workflow | 1) A `low_balance` notification is created once per crossing. 2) It links to the credits page. 3) Email follows preferences. |
| Alternative workflows | A) Balance reaches zero: a stronger notice. B) Balance restored above the threshold re-arms the alert. |
| Expected result | No surprise at send time. |
| Error scenarios | Not applicable. |
| Dependencies | FR-CREDIT-008. |
| Acceptance criteria | AC1 Fires once per crossing, not per message. AC2 Links to the credits page. AC3 Simulation notices say they refer to demo credits. |

### FR-NOTIF-005 — Notification Preferences

| Field | Detail |
|---|---|
| Module | G — Notifications |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users choose which notifications they receive on which channel. |
| Preconditions | Signed in. |
| Trigger | User opens Settings, Notifications. |
| Main workflow | 1) A matrix of types by channel (in-app, push, email) with toggles. 2) Global quiet hours (optional). 3) Preview privacy toggle. 4) Changes save immediately. |
| Alternative workflows | A) Reset to defaults. |
| Expected result | Notifications match preferences. |
| Error scenarios | Save failure: toggle reverts. |
| Dependencies | FR-NOTIF-002, FR-NOTIF-008. |
| Acceptance criteria | AC1 Preferences persist per user. AC2 Security and system-critical notices cannot be fully disabled. AC3 Changes apply to the next event. AC4 Controls are keyboard accessible with labelled switches. |

### FR-NOTIF-006 — Notification History

| Field | Detail |
|---|---|
| Module | G — Notifications |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users view, filter and manage past notifications. |
| Preconditions | Signed in. |
| Trigger | User opens the notification centre. |
| Main workflow | 1) Paginated list, newest first. 2) Filter by type and read state. 3) Mark one or all as read. 4) Dismiss one. 5) Selecting opens the related item. |
| Alternative workflows | A) Empty state. B) Items older than 90 days are removed. |
| Expected result | A reviewable activity trail. |
| Error scenarios | Linked item deleted: item shows "No longer available". |
| Dependencies | None. |
| Acceptance criteria | AC1 Unread badge matches the list. AC2 Pagination is cursor based. AC3 Users only see their own notifications (RLS). |

### FR-NOTIF-007 — Contact Request Alerts

| Field | Detail |
|---|---|
| Module | G — Notifications |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users are notified of incoming contact requests and acceptances. |
| Preconditions | Request created or accepted. |
| Trigger | FR-CONTACTS-001 or FR-CONTACTS-010 event. |
| Main workflow | 1) `contact_request` notification to the recipient with requester display name. 2) `contact_accepted` to the requester upon acceptance. 3) Rejections generate nothing. 4) Push and email follow preferences. |
| Alternative workflows | A) Requests from users the recipient has blocked create no notification. |
| Expected result | Timely visibility without leaking rejections or blocks. |
| Error scenarios | Not applicable. |
| Dependencies | FR-CONTACTS-001, FR-CONTACTS-010. |
| Acceptance criteria | AC1 Notification includes accept and reject shortcuts. AC2 No rejection or block signal is sent to requesters. AC3 Counts show on the Requests tab. |

### FR-NOTIF-008 — Email Notifications

| Field | Detail |
|---|---|
| Module | G — Notifications |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent (uses the email service, not SMS) |
| Description | Users can receive email for selected events when they are away. |
| Preconditions | Verified email. Type enabled for email. |
| Trigger | Event while the user is offline longer than 15 minutes (messages), or immediately (requests, low balance, security). |
| Main workflow | 1) Messages are batched into a digest at most once every 30 minutes per conversation. 2) The email contains sender name, count and a link. No message bodies. 3) Every email has an unsubscribe link and a link to settings. |
| Alternative workflows | A) Unsubscribe via link disables that category without sign-in. |
| Expected result | Away users learn of activity without content exposure. |
| Error scenarios | Bounce: after 3 hard bounces email notifications are disabled and the user is informed in-app. |
| Dependencies | Email provider, FR-NOTIF-005. |
| Acceptance criteria | AC1 No full message text in email. AC2 Unsubscribe works with one click. AC3 Rate limit of 10 emails per hour per user. AC4 Simulated SMS events state they are simulated. |

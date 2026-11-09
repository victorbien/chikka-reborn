# Functional Requirements Specification (FRS)

**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Date:** November 2026  

---

## 1. Introduction

This document specifies the functional requirements for Chikka Reborn. Each requirement is identified by a unique ID, linked to a module, and accompanied by acceptance criteria. Requirements marked `[MUST]` are mandatory for the phase indicated. Requirements marked `[SHOULD]` are strongly desired. Requirements marked `[MAY]` are optional enhancements.

---

## 2. Requirement Notation

- `FR-A-xxx` — Authentication and User Management
- `FR-B-xxx` — Contacts and Buddy List
- `FR-C-xxx` — Real-Time Chikka-to-Chikka Messaging
- `FR-D-xxx` — Internet-to-SMS Messaging
- `FR-E-xxx` — SMS-to-Internet Messaging
- `FR-F-xxx` — AI-Powered Chikka Assistant
- `FR-G-xxx` — Notifications
- `FR-H-xxx` — SMS Credits and Cost Management
- `FR-I-xxx` — Privacy and Security
- `FR-J-xxx` — Administration Dashboard
- `FR-K-xxx` — Classic and Modern Mode

---

## 3. Module A — Authentication and User Management

### FR-A-001 [MUST] — Email and Password Registration
**Phase:** 1  
**Description:** Users must be able to create an account using an email address and password.  
**Acceptance Criteria:**
- Email must match a valid RFC 5322 format.
- Password must be at least 8 characters and include at least one uppercase letter, one lowercase letter, and one number.
- Registration triggers a verification email to the provided address.
- Duplicate email addresses are rejected with a clear error.

### FR-A-002 [MUST] — Email Verification
**Phase:** 1  
**Description:** New accounts must verify their email address before gaining full access.  
**Acceptance Criteria:**
- A verification link is emailed upon registration.
- Unverified accounts can log in but are shown a persistent verification prompt.
- Unverified accounts cannot send SMS messages.
- The verification link expires after 24 hours.
- Users can request a new verification email.

### FR-A-003 [SHOULD] — Social Login
**Phase:** 1  
**Description:** Users may sign up and log in via Google or GitHub OAuth.  
**Acceptance Criteria:**
- OAuth flow completes within the platform without requiring separate registration steps.
- Social-login users are prompted to set a display name on first login.

### FR-A-004 [MUST] — Authenticated Login
**Phase:** 1  
**Description:** Registered users must be able to log in with their credentials.  
**Acceptance Criteria:**
- Correct credentials grant access and issue a session token (managed by Supabase Auth).
- Incorrect credentials return a generic error that does not reveal whether the email exists.
- Sessions expire after 7 days of inactivity.
- Sessions can be explicitly terminated (logout).

### FR-A-005 [MUST] — Password Reset
**Phase:** 1  
**Description:** Users must be able to reset a forgotten password via email.  
**Acceptance Criteria:**
- A password reset link is sent to the registered email.
- The reset link expires after 1 hour.
- After reset, all existing sessions are invalidated.

### FR-A-006 [MUST] — Rate Limiting on Login
**Phase:** 1  
**Description:** Failed login attempts must be rate-limited to prevent brute-force attacks.  
**Acceptance Criteria:**
- After 5 consecutive failed attempts from the same IP or account, further attempts are blocked for 15 minutes.
- Rate limit status is communicated clearly to the user.

### FR-A-007 [MUST] — User Profile
**Phase:** 1  
**Description:** Users must be able to set and update their profile information.  
**Acceptance Criteria:**
- Profile fields: display name, bio, profile photo, country.
- Display name must be 2–50 characters.
- Profile photo is stored in Supabase Storage.
- Profile updates are reflected immediately across the platform.

### FR-A-008 [MUST] — Mobile Number Association
**Phase:** 2  
**Description:** Users must be able to associate a mobile phone number with their account.  
**Acceptance Criteria:**
- Phone number is entered in E.164 international format.
- A 6-digit OTP is sent to the provided number for verification.
- OTP is valid for 10 minutes.
- A maximum of 3 OTP send attempts per 30-minute window is enforced.
- Only one verified phone number per account.

### FR-A-009 [MUST] — Account Deletion
**Phase:** 1  
**Description:** Users must be able to delete their account.  
**Acceptance Criteria:**
- Deletion requires re-authentication (password or OAuth confirmation).
- Upon deletion, personal data is scheduled for erasure within 30 days.
- Conversation history is anonymised, not deleted, to preserve thread integrity for other parties.
- Active sessions are immediately invalidated.

---

## 4. Module B — Contacts and Buddy List

### FR-B-001 [MUST] — Add Chikka Contact
**Phase:** 1  
**Description:** Users must be able to find and add registered Chikka users as contacts.  
**Acceptance Criteria:**
- Search by username or email address.
- Results respect the searched user's privacy settings.
- Adding a contact does not require the other party's approval (follow model, not mutual-friend model).

### FR-B-002 [MUST] — Add SMS Contact
**Phase:** 2  
**Description:** Users must be able to add a mobile phone number as an SMS contact.  
**Acceptance Criteria:**
- Phone number is validated in E.164 format.
- Country capability is checked; unsupported destinations display a warning.
- SMS contacts appear in the contact list alongside Chikka contacts.

### FR-B-003 [MUST] — Contact List Display
**Phase:** 1  
**Description:** Users must be able to view their full contact list.  
**Acceptance Criteria:**
- Contacts are listed alphabetically by display name.
- Online Chikka users are indicated with a presence indicator.
- SMS-only contacts are distinguished visually from Chikka users.
- List is paginated for large contact lists (> 50 contacts).

### FR-B-004 [MUST] — Block Contact
**Phase:** 1  
**Description:** Users must be able to block a contact.  
**Acceptance Criteria:**
- A blocked user cannot send messages to the blocker.
- A blocked user cannot see the blocker's online status.
- Blocking is reversible.
- Blocked contacts appear in a separate blocked list, not the main contact list.

### FR-B-005 [SHOULD] — Contact Groups
**Phase:** 2  
**Description:** Users should be able to organise contacts into named groups.  
**Acceptance Criteria:**
- Groups are user-defined and user-named.
- A contact can belong to multiple groups.
- Groups appear in the contact list sidebar.

---

## 5. Module C — Real-Time Chikka-to-Chikka Messaging

### FR-C-001 [MUST] — Send Chikka Message
**Phase:** 1  
**Description:** Users must be able to send text messages to other registered Chikka users in real time.  
**Acceptance Criteria:**
- Messages are delivered via WebSocket when both parties are online.
- Messages are stored and delivered when the recipient comes online.
- Maximum message length: 2000 characters.
- Empty messages cannot be sent.

### FR-C-002 [MUST] — Message Status Indicators
**Phase:** 1  
**Description:** Users must see the delivery and read status of their sent messages.  
**Acceptance Criteria:**
- Statuses: Sent, Delivered, Read.
- Delivered status is set when the message reaches the recipient's client.
- Read status is set when the recipient views the message.
- Status changes update in real time for the sender.

### FR-C-003 [MUST] — Typing Indicator
**Phase:** 1  
**Description:** Users must see when the other party is typing.  
**Acceptance Criteria:**
- Typing indicator appears within 500ms of the other party beginning to type.
- Typing indicator disappears within 3 seconds of the other party stopping.
- Typing events are not persisted to the database.

### FR-C-004 [MUST] — Conversation History
**Phase:** 1  
**Description:** Users must be able to view their full conversation history with each contact.  
**Acceptance Criteria:**
- Most recent 50 messages are loaded on conversation open.
- Older messages load on scroll (infinite scroll / load more).
- Timestamps are shown per message.
- Date separators appear between messages from different days.

### FR-C-005 [SHOULD] — Message Deletion
**Phase:** 2  
**Description:** Users should be able to delete messages they have sent.  
**Acceptance Criteria:**
- "Delete for me" removes the message from the sender's view only.
- "Delete for everyone" removes the message for both parties within 5 minutes of sending.
- Deleted messages show a "This message was deleted" placeholder for the other party.

### FR-C-006 [MUST] — Emoji Support
**Phase:** 1  
**Description:** Messages must support Unicode emoji.  
**Acceptance Criteria:**
- Emoji are stored as Unicode characters.
- Emoji render correctly in both Classic and Modern mode.

---

## 6. Module D — Internet-to-SMS Messaging

### FR-D-001 [MUST] — Compose and Send SMS
**Phase:** 2  
**Description:** Users must be able to compose and send an SMS message to a mobile phone number.  
**Acceptance Criteria:**
- Recipient phone number is validated in E.164 format before sending.
- Country capability is checked before sending. Unsupported destinations are rejected with an explanation.
- Message body is required and cannot be empty.
- The outbound message is stored in the database regardless of provider outcome.

### FR-D-002 [MUST] — SMS Segment and Credit Preview
**Phase:** 2  
**Description:** Users must see the segment count and credit cost before sending.  
**Acceptance Criteria:**
- Segment count updates in real time as the user types.
- Credit cost is displayed as a numeric value alongside the segment count.
- The calculation correctly distinguishes GSM-7 (160 chars/segment) from Unicode (70 chars/segment).

### FR-D-003 [MUST] — Simulation Mode Labelling
**Phase:** 2  
**Description:** All messages sent in simulation mode must be clearly labelled.  
**Acceptance Criteria:**
- A persistent "SIMULATED" badge appears on every simulated message in the message list, message detail view, and delivery status display.
- The badge cannot be removed or hidden by user settings.
- Simulated messages are stored with `is_simulated = true` in the database.

### FR-D-004 [MUST] — SMS Delivery Status Tracking
**Phase:** 2  
**Description:** Users must see accurate delivery status for all sent SMS messages.  
**Acceptance Criteria:**
- Statuses: Queued, Sent, Delivered, Failed, Undelivered.
- Status is updated via provider callback, not assumed from send acceptance.
- "Delivered" status is only set when the provider confirms handset delivery.
- Status updates appear in real time in the conversation view.

### FR-D-005 [MUST] — Insufficient Credit Prevention
**Phase:** 2  
**Description:** Users must not be able to send an SMS if they lack sufficient credits.  
**Acceptance Criteria:**
- The send button is disabled when the credit cost exceeds the user's balance.
- A clear message explains the shortfall and links to the top-up page.

---

## 7. Module E — SMS-to-Internet Messaging

### FR-E-001 [MUST] — Inbound SMS Delivery to Conversation
**Phase:** 2  
**Description:** Inbound SMS replies must appear in the correct conversation thread.  
**Acceptance Criteria:**
- Inbound SMS is matched to the conversation by sender phone number and virtual number used.
- Matched messages appear in the conversation thread in real time.
- Unmatched inbound SMS is logged and flagged in the admin dashboard.

### FR-E-002 [MUST] — Webhook Signature Validation
**Phase:** 2  
**Description:** All inbound SMS webhooks must be validated before processing.  
**Acceptance Criteria:**
- The webhook endpoint validates the provider signature on every request.
- Requests with invalid signatures return HTTP 403 and are not processed.
- Validation failures are logged with the request metadata (no message body).

### FR-E-003 [MUST] — SMS Origin Labelling
**Phase:** 2  
**Description:** Messages received via SMS must be visually distinguished from Chikka-originated messages.  
**Acceptance Criteria:**
- An "SMS" label or icon appears on messages received from the SMS pathway.
- The label is visible in the conversation thread view.

---

## 8. Module F — AI-Powered Chikka Assistant

### FR-F-001 [MUST] — Smart Reply Suggestions
**Phase:** 3  
**Description:** The AI assistant must generate reply suggestions based on conversation context.  
**Acceptance Criteria:**
- 2–3 suggestions are generated per request.
- Suggestions appear in a review panel below or beside the compose field.
- Selecting a suggestion populates the compose field but does not send automatically.
- The user can edit, accept, or dismiss any suggestion.

### FR-F-002 [MUST] — Message Translation
**Phase:** 3  
**Description:** Users must be able to translate a message or their draft into another language.  
**Acceptance Criteria:**
- User selects a target language from a supported list.
- Translation is presented as a suggestion, not auto-inserted.
- If translation fails, the user is notified and can still send the original.

### FR-F-003 [MUST] — Message Rewriting
**Phase:** 3  
**Description:** Users must be able to ask the AI to rewrite their draft message.  
**Acceptance Criteria:**
- Rewrite options: improve clarity, fix grammar, make more formal, make more casual.
- Rewritten content is presented as a suggestion.
- The original draft is preserved until the user explicitly accepts the rewrite.

### FR-F-004 [MUST] — SMS Length Optimisation
**Phase:** 3  
**Description:** The AI must be able to shorten a message to fit within SMS segment limits.  
**Acceptance Criteria:**
- The resulting character count, segment count, and credit cost are displayed.
- The optimised message is presented as a suggestion.
- If the AI cannot preserve meaning within the limit, it states this explicitly rather than silently truncating.

### FR-F-005 [MUST] — Conversation Summary
**Phase:** 3  
**Description:** The AI must be able to summarise a conversation thread.  
**Acceptance Criteria:**
- Summary covers the most recent N messages (configurable, default 20).
- Summary is displayed in a panel, not inserted into the conversation.
- Users can dismiss the summary without any side effects.

### FR-F-006 [MUST] — Mandatory User Approval Before Sending
**Phase:** 3  
**Description:** AI-generated content must never be sent without explicit user approval.  
**Acceptance Criteria:**
- No AI feature auto-sends any message under any circumstances.
- AI suggestions are only placed in the compose field when the user explicitly accepts them.
- This requirement has no exceptions and is not configurable.

---

## 9. Module G — Notifications

### FR-G-001 [MUST] — In-App Notifications
**Phase:** 1  
**Description:** Users must receive in-app notifications for new messages.  
**Acceptance Criteria:**
- A notification badge appears on the conversation/contact in the sidebar.
- An unread count is displayed in the browser tab title.
- Notifications clear when the user opens the relevant conversation.

### FR-G-002 [SHOULD] — Browser Push Notifications
**Phase:** 2  
**Description:** Users should receive push notifications when the app is not in focus.  
**Acceptance Criteria:**
- Push notification permission is requested with a clear explanation.
- Users can disable push notifications from account settings.
- Push notifications link directly to the relevant conversation.

### FR-G-003 [MUST] — SMS Delivery Notifications
**Phase:** 2  
**Description:** Users must be notified when a sent SMS message changes delivery status.  
**Acceptance Criteria:**
- Status changes (delivered, failed) generate an in-app notification.
- Failed delivery shows a clear action prompt (retry or dismiss).

---

## 10. Module H — SMS Credits and Cost Management

### FR-H-001 [MUST] — Credit Balance Display
**Phase:** 2  
**Description:** Users must always be able to see their current credit balance.  
**Acceptance Criteria:**
- Credit balance is displayed in the navigation/header area.
- Balance updates in real time after a deduction or top-up.

### FR-H-002 [MUST] — Per-Country Credit Pricing
**Phase:** 2  
**Description:** The platform must maintain a credit cost per destination country per SMS segment.  
**Acceptance Criteria:**
- Credit rates are configurable by admin without a code deploy.
- Rates are displayed to users before sending.

### FR-H-003 [MUST] — Credit Deduction and Refund
**Phase:** 2  
**Description:** Credits must be deducted on message acceptance and refunded on permanent failure.  
**Acceptance Criteria:**
- Deduction occurs only after the provider accepts the message.
- Refund occurs after all retries are exhausted and the message is marked permanently failed.
- Every transaction is logged with full audit trail.

### FR-H-004 [SHOULD] — Credit Top-Up
**Phase:** 4  
**Description:** Users should be able to purchase additional credits.  
**Acceptance Criteria:**
- Top-up initiates a payment flow (payment gateway TBD).
- Credits are added only after successful payment confirmation.
- Top-up history is visible in the account settings.

---

## 11. Module I — Privacy and Security

### FR-I-001 [MUST] — Profile Visibility Controls
**Phase:** 1  
**Description:** Users must be able to control the visibility of their profile information.  
**Acceptance Criteria:**
- Options: visible to all, visible to contacts only, private.
- Private profiles do not appear in contact search results.

### FR-I-002 [MUST] — Data Export
**Phase:** 2  
**Description:** Users must be able to request a copy of their personal data.  
**Acceptance Criteria:**
- Export includes: profile, contact list, conversation history, SMS history, credit history.
- Export is generated as a downloadable JSON or CSV archive.
- Export request is processed within 48 hours.

### FR-I-003 [MUST] — SMS Opt-Out Handling
**Phase:** 2  
**Description:** Recipients must be able to opt out of receiving SMS from the platform.  
**Acceptance Criteria:**
- Opt-out is honoured immediately; no further SMS is sent to that number.
- Opt-out is stored per phone number.
- Attempting to send to an opted-out number is blocked with a clear notification to the sender.

### FR-I-004 [MUST] — Message Reporting
**Phase:** 2  
**Description:** Users must be able to report abusive or unwanted messages.  
**Acceptance Criteria:**
- Report action is available on every message.
- Reports are queued for admin review.
- Reporter's identity is not revealed to the reported user.

---

## 12. Module J — Administration Dashboard

### FR-J-001 [MUST] — Platform Statistics
**Phase:** 2  
**Description:** Admins must be able to view aggregate platform metrics.  
**Acceptance Criteria:**
- Metrics: total users, active users (last 24h/7d/30d), messages sent, SMS sent, delivery rate, AI requests.
- Metrics refresh at least every 5 minutes.

### FR-J-002 [MUST] — User Management
**Phase:** 2  
**Description:** Admins must be able to view, suspend, reinstate, and delete user accounts.  
**Acceptance Criteria:**
- Admin actions are logged with admin ID, timestamp, and reason.
- Suspended users cannot log in but their data is preserved.
- Admin cannot delete their own account from this interface.

### FR-J-003 [MUST] — SMS Provider Mode Configuration
**Phase:** 2  
**Description:** Admins must be able to switch SMS mode between simulation and live.  
**Acceptance Criteria:**
- Mode switch requires admin re-authentication.
- Switching to live mode displays an explicit confirmation dialog with cost warning.
- Current mode is displayed prominently in the admin dashboard.

### FR-J-004 [MUST] — SMS Audit Log
**Phase:** 2  
**Description:** Admins must be able to view the SMS audit log.  
**Acceptance Criteria:**
- Log entries include: message ID, masked recipient, provider, status, timestamp.
- Log is searchable by date range, status, and user.
- Log is read-only from the admin UI.

### FR-J-005 [MUST] — Country Capability Management
**Phase:** 2  
**Description:** Admins must be able to configure per-country SMS capabilities.  
**Acceptance Criteria:**
- Configurable per country: outbound enabled, inbound enabled, alphanumeric sender ID, registered sender required, content restrictions.
- Changes take effect immediately without a code deploy.

---

## 13. Module K — Classic and Modern Mode

### FR-K-001 [MUST] — Mode Toggle
**Phase:** 5  
**Description:** Users must be able to switch between Classic Chikka Mode and Modern Mode.  
**Acceptance Criteria:**
- Toggle is accessible from account settings and the main interface.
- Mode preference is persisted in the user profile.
- All core features (messaging, contacts, SMS) are fully functional in both modes.

### FR-K-002 [MUST] — Classic Mode Appearance
**Phase:** 5  
**Description:** Classic Mode must evoke the visual identity of the original Chikka.  
**Acceptance Criteria:**
- Uses an original-inspired colour scheme and typography (no licensed assets without permission).
- Buddy list layout resembles the original Chikka contact list.
- Message composition area is styled consistent with the original Chikka interface.
- Clearly identified as an independent, inspired design — not an official Chikka reproduction.

### FR-K-003 [MUST] — Modern Mode Appearance
**Phase:** 1  
**Description:** Modern Mode must provide a contemporary messaging interface.  
**Acceptance Criteria:**
- Uses shadcn/ui components with Tailwind CSS.
- Split-panel layout: contact/conversation list on the left, active conversation on the right.
- Full mobile responsiveness.

---

## 14. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

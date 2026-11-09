# Functional Requirements

**Document:** CHKR-PROD-005  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document defines all functional requirements for Chikka Reborn using unique, domain-prefixed identifiers. Each requirement specifies what the system must, should, or may do — along with its MVP classification, phase, and acceptance criteria.

## Scope

Covers all 11 product modules (A–K). Cross-references the earlier `docs/frs.md` which used the `FR-A-xxx` scheme. The new identifiers in this document (e.g. `FR-AUTH-001`) are the canonical identifiers going forward.

## Requirement Priority

- **MVP** — Required for the Minimum Viable Product (Phase 1–2 launch).
- **POST-MVP** — Required but delivered in a later phase.
- **FUTURE** — Desirable; subject to resourcing.

---

## Module AUTH — Authentication and User Management

### FR-AUTH-001 — Email Registration
**Priority:** MVP | **Phase:** 1 | **Was:** FR-A-001  
Users must be able to register with a valid email address and password.  
**Acceptance Criteria:**
- Email validates RFC 5322 format.
- Password: min 8 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit.
- Duplicate emails rejected with a non-revealing error.
- Verification email sent on registration.

### FR-AUTH-002 — Email Verification
**Priority:** MVP | **Phase:** 1 | **Was:** FR-A-002  
Accounts must verify email before gaining full platform access.  
**Acceptance Criteria:**
- Verification link emailed on registration.
- Link expires after 24 hours.
- Unverified accounts cannot send SMS.
- User can request a new verification email.

### FR-AUTH-003 — Social Login (Google, GitHub)
**Priority:** MVP | **Phase:** 1 | **Was:** FR-A-003  
Users may register and log in via OAuth providers.  
**Acceptance Criteria:**
- OAuth flow completes within the platform.
- Social users prompted for display name on first login.

### FR-AUTH-004 — Authenticated Login
**Priority:** MVP | **Phase:** 1 | **Was:** FR-A-004  
Registered users must be able to log in securely.  
**Acceptance Criteria:**
- Correct credentials issue a Supabase JWT.
- Wrong credentials return a generic error (no email enumeration).
- Sessions expire after 7 days of inactivity.
- Explicit logout invalidates the session.

### FR-AUTH-005 — Password Reset
**Priority:** MVP | **Phase:** 1 | **Was:** FR-A-005  
Users must be able to reset a forgotten password.  
**Acceptance Criteria:**
- Reset link emailed; valid for 1 hour.
- All existing sessions invalidated after reset.

### FR-AUTH-006 — Login Rate Limiting
**Priority:** MVP | **Phase:** 1 | **Was:** FR-A-006  
Failed login attempts must be rate-limited.  
**Acceptance Criteria:**
- 5 consecutive failures trigger a 15-minute lockout per IP/account.
- Rate limit status communicated to the user.

### FR-AUTH-007 — User Profile Management
**Priority:** MVP | **Phase:** 1 | **Was:** FR-A-007  
Users must be able to set and update their profile.  
**Acceptance Criteria:**
- Fields: display name (2–50 chars), bio, avatar, country code, UI mode.
- Avatar stored in Supabase Storage.
- Profile updates reflected immediately.

### FR-AUTH-008 — Mobile Number Verification
**Priority:** MVP | **Phase:** 2 | **Was:** FR-A-008  
Users must be able to verify a mobile phone number via SMS OTP.  
**Acceptance Criteria:**
- Phone number accepted in E.164 format.
- 6-digit OTP sent via SMS; valid 10 minutes.
- Max 3 OTP send attempts per 30-minute window.
- One verified number per account.

### FR-AUTH-009 — Account Deletion
**Priority:** MVP | **Phase:** 1 | **Was:** FR-A-009  
Users must be able to delete their account.  
**Acceptance Criteria:**
- Requires re-authentication before deletion.
- Personal data scheduled for erasure within 30 days.
- Conversation history anonymised, not deleted.
- All sessions immediately invalidated.

---

## Module CONTACTS — Contacts and Buddy List

### FR-CONTACTS-001 — Add Chikka Contact
**Priority:** MVP | **Phase:** 1 | **Was:** FR-B-001  
Users must be able to find and add registered Chikka users.  
**Acceptance Criteria:**
- Search by username or email.
- Search respects target user's privacy settings.
- Follow model (no mutual approval required).

### FR-CONTACTS-002 — Add SMS Contact
**Priority:** MVP | **Phase:** 2 | **Was:** FR-B-002  
Users must be able to add a mobile number as an SMS contact.  
**Acceptance Criteria:**
- Number validated in E.164 format.
- Country capability checked; unsupported destinations show warning.

### FR-CONTACTS-003 — Contact List Display
**Priority:** MVP | **Phase:** 1 | **Was:** FR-B-003  
Users must be able to view their contacts with presence indicators.  
**Acceptance Criteria:**
- Alphabetical order by display name.
- Online Chikka users indicated with a presence dot.
- SMS contacts visually distinguished.
- Paginated beyond 50 contacts.

### FR-CONTACTS-004 — Block Contact
**Priority:** MVP | **Phase:** 1 | **Was:** FR-B-004  
Users must be able to block a contact.  
**Acceptance Criteria:**
- Blocked user cannot send messages or see blocker's presence.
- Block is reversible.
- Blocked contacts appear in a separate list.

### FR-CONTACTS-005 — Contact Groups
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-B-005  
Users should be able to organise contacts into named groups.  
**Acceptance Criteria:**
- User-defined group names.
- Contact belongs to multiple groups.
- Groups visible in contact sidebar.

---

## Module MSG — Real-Time Chikka-to-Chikka Messaging

### FR-MSG-001 — Send Chikka Message
**Priority:** MVP | **Phase:** 1 | **Was:** FR-C-001  
Users must be able to send text messages to registered Chikka users in real time.  
**Acceptance Criteria:**
- Delivered via Supabase Realtime when both online.
- Queued and delivered when recipient comes online.
- Max 2000 characters per message.
- Empty messages cannot be sent.

### FR-MSG-002 — Message Status Indicators
**Priority:** MVP | **Phase:** 1 | **Was:** FR-C-002  
Users must see delivery and read status per message.  
**Acceptance Criteria:**
- Statuses: Sent → Delivered → Read with timestamps.
- Status updates in real time for the sender.

### FR-MSG-003 — Typing Indicator
**Priority:** MVP | **Phase:** 1 | **Was:** FR-C-003  
Users must see when the other party is typing.  
**Acceptance Criteria:**
- Indicator appears within 500ms of typing start.
- Disappears within 3 seconds of typing stop.
- Not persisted to the database.

### FR-MSG-004 — Conversation History
**Priority:** MVP | **Phase:** 1 | **Was:** FR-C-004  
Users must be able to view full conversation history.  
**Acceptance Criteria:**
- Most recent 50 messages on open.
- Load more on scroll.
- Timestamps per message; date separators between days.

### FR-MSG-005 — Message Deletion
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-C-005  
Users should be able to delete sent messages.  
**Acceptance Criteria:**
- "Delete for me" and "delete for everyone" (within 5 minutes of sending).
- Deleted message shows "This message was deleted" placeholder.

### FR-MSG-006 — Emoji Support
**Priority:** MVP | **Phase:** 1 | **Was:** FR-C-006  
Messages must support Unicode emoji.  
**Acceptance Criteria:**
- Stored as Unicode; render correctly in both UI modes.

---

## Module SMS — Internet-to-SMS Messaging

### FR-SMS-001 — Compose and Send SMS
**Priority:** MVP | **Phase:** 2 | **Was:** FR-D-001  
Users must be able to send an SMS to any mobile number.  
**Acceptance Criteria:**
- E.164 format validation before send.
- Country capability checked; unsupported destinations rejected with explanation.
- Message body required.
- Message stored regardless of provider outcome.

### FR-SMS-002 — Segment and Credit Preview
**Priority:** MVP | **Phase:** 2 | **Was:** FR-D-002  
Users must see segment count and credit cost before sending.  
**Acceptance Criteria:**
- Updates in real time as user types.
- GSM-7: 160 chars/segment; Unicode: 70 chars/segment.
- Credit cost shown alongside segment count.

### FR-SMS-003 — Simulation Mode Labelling
**Priority:** MVP | **Phase:** 2 | **Was:** FR-D-003  
All simulated messages must be permanently labelled.  
**Acceptance Criteria:**
- "SIMULATED" badge on message in list, detail, and delivery status views.
- Badge cannot be hidden or removed.
- Stored with `is_simulated = true`.

### FR-SMS-004 — Delivery Status Tracking
**Priority:** MVP | **Phase:** 2 | **Was:** FR-D-004  
Delivery status must reflect provider delivery events, not acceptance.  
**Acceptance Criteria:**
- Statuses: Queued → Sent → Delivered / Failed / Undelivered.
- "Delivered" set only on provider handset confirmation.
- Status updates in real time.

### FR-SMS-005 — Insufficient Credit Prevention
**Priority:** MVP | **Phase:** 2 | **Was:** FR-D-005  
Users must not be able to send if credits are insufficient.  
**Acceptance Criteria:**
- Send button disabled when cost exceeds balance.
- Clear message explaining shortfall with link to top-up.

---

## Module SMS-RECV — SMS-to-Internet Messaging

### FR-SMSRECV-001 — Inbound SMS to Conversation
**Priority:** MVP | **Phase:** 2 | **Was:** FR-E-001  
Inbound SMS replies must appear in the correct conversation.  
**Acceptance Criteria:**
- Matched by sender number and originating platform number.
- Appears in real time in the conversation thread.
- Unmatched inbound SMS logged and admin-flagged.

### FR-SMSRECV-002 — Webhook Signature Validation
**Priority:** MVP | **Phase:** 2 | **Was:** FR-E-002  
All inbound webhooks must be validated before processing.  
**Acceptance Criteria:**
- Invalid signatures return HTTP 403.
- Not processed. Logged as warning.

### FR-SMSRECV-003 — SMS Origin Labelling
**Priority:** MVP | **Phase:** 2 | **Was:** FR-E-003  
SMS-originated messages must be visually distinguished.  
**Acceptance Criteria:**
- "SMS" label/icon on messages from SMS pathway.
- Visible in conversation thread.

---

## Module AI — AI-Powered Chikka Assistant

### FR-AI-001 — Smart Reply Suggestions
**Priority:** POST-MVP | **Phase:** 3 | **Was:** FR-F-001  
AI must generate 2–3 reply suggestions from conversation context.  
**Acceptance Criteria:**
- Shown in review panel; not auto-inserted.
- Selecting populates compose field but does not send.
- User can dismiss or regenerate.

### FR-AI-002 — Message Translation
**Priority:** POST-MVP | **Phase:** 3 | **Was:** FR-F-002  
AI must translate a message to a user-selected language.  
**Acceptance Criteria:**
- User selects target language from supported list.
- Translation shown as suggestion.
- Failure is non-blocking; original message composable.

### FR-AI-003 — Message Rewriting
**Priority:** POST-MVP | **Phase:** 3 | **Was:** FR-F-003  
AI must rewrite a draft message per a user instruction.  
**Acceptance Criteria:**
- Options: improve_clarity, fix_grammar, make_formal, make_casual.
- Rewrite shown as suggestion; original preserved until accepted.

### FR-AI-004 — SMS Length Optimisation
**Priority:** POST-MVP | **Phase:** 3 | **Was:** FR-F-004  
AI must shorten a message to fit within SMS segment limits.  
**Acceptance Criteria:**
- Resulting character count, segment count, and credit cost displayed.
- Shown as suggestion.
- If meaning cannot be preserved, AI states this explicitly.

### FR-AI-005 — Conversation Summary
**Priority:** POST-MVP | **Phase:** 3 | **Was:** FR-F-005  
AI must summarise a conversation thread.  
**Acceptance Criteria:**
- Covers most recent N messages (default 20, configurable).
- Shown in panel; not inserted into conversation.
- Dismissible without side effects.

### FR-AI-006 — Mandatory User Approval
**Priority:** MVP | **Phase:** 3 | **Was:** FR-F-006  
AI-generated content must never be sent without explicit user approval.  
**Acceptance Criteria:**
- No auto-send under any circumstances.
- AI content only placed in compose field when explicitly accepted.
- No exceptions; not configurable.

### FR-AI-007 — AI-Assisted Badge
**Priority:** POST-MVP | **Phase:** 3  
Any message composed or significantly modified by AI must show an "AI-assisted" badge before sending.  
**Acceptance Criteria:**
- Badge visible on unsent message.
- Badge not visible to message recipient after sending.

---

## Module NOTIF — Notifications

### FR-NOTIF-001 — In-App Notifications
**Priority:** MVP | **Phase:** 1 | **Was:** FR-G-001  
Users must receive in-app notifications for new messages.  
**Acceptance Criteria:**
- Badge on conversation in sidebar.
- Unread count in browser tab title.
- Clears when conversation is opened.

### FR-NOTIF-002 — Browser Push Notifications
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-G-002  
Users should receive push notifications when app is not in focus.  
**Acceptance Criteria:**
- Permission requested with explanation.
- Configurable in account settings.
- Push notification links to relevant conversation.

### FR-NOTIF-003 — SMS Delivery Notifications
**Priority:** MVP | **Phase:** 2 | **Was:** FR-G-003  
Users must be notified of SMS delivery status changes.  
**Acceptance Criteria:**
- Delivered and failed events generate in-app notifications.
- Failed delivery shows action prompt (retry or dismiss).

---

## Module CREDIT — SMS Credits and Cost Management

### FR-CREDIT-001 — Credit Balance Display
**Priority:** MVP | **Phase:** 2 | **Was:** FR-H-001  
Users must always be able to see their credit balance.  
**Acceptance Criteria:**
- Balance displayed in navigation/header.
- Updates in real time after deduction or top-up.

### FR-CREDIT-002 — Per-Country Credit Pricing
**Priority:** MVP | **Phase:** 2 | **Was:** FR-H-002  
Credit cost per segment must be configurable per destination country.  
**Acceptance Criteria:**
- Rates configurable by admin without code deploy.
- Rates shown to users before sending.

### FR-CREDIT-003 — Credit Deduction and Refund
**Priority:** MVP | **Phase:** 2 | **Was:** FR-H-003  
Credits deducted on acceptance; refunded on permanent failure.  
**Acceptance Criteria:**
- Deduction after provider acceptance.
- Refund after all retries exhausted.
- Full audit trail per transaction.

### FR-CREDIT-004 — Credit Top-Up
**Priority:** POST-MVP | **Phase:** 4 | **Was:** FR-H-004  
Users should be able to purchase additional credits.  
**Acceptance Criteria:**
- Initiates payment flow (gateway TBD — OD-001).
- Credits added only after payment confirmation.
- Top-up history visible in account settings.

---

## Module PRIVACY — Privacy and Security

### FR-PRIVACY-001 — Profile Visibility Controls
**Priority:** MVP | **Phase:** 1 | **Was:** FR-I-001  
Users must control who can see their profile.  
**Acceptance Criteria:**
- Options: all, contacts only, private.
- Private profiles excluded from search.

### FR-PRIVACY-002 — Data Export
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-I-002  
Users must be able to export their personal data.  
**Acceptance Criteria:**
- Includes profile, contacts, conversations, SMS history, credits.
- JSON or CSV archive; delivered within 48 hours.

### FR-PRIVACY-003 — SMS Opt-Out
**Priority:** MVP | **Phase:** 2 | **Was:** FR-I-003  
Recipients must be able to opt out of SMS from the platform.  
**Acceptance Criteria:**
- Opt-out honoured immediately; stored per phone number.
- Attempted send to opted-out number blocked with sender notification.

### FR-PRIVACY-004 — Message Reporting
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-I-004  
Users must be able to report abusive messages.  
**Acceptance Criteria:**
- Report action on every message.
- Reports queued for admin review.
- Reporter identity not revealed to reported user.

---

## Module ADMIN — Administration Dashboard

### FR-ADMIN-001 — Platform Statistics
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-J-001  
Admins must view aggregate platform metrics.  
**Acceptance Criteria:**
- Metrics: users, active users (24h/7d/30d), messages, SMS, delivery rate, AI requests.
- Refresh every 5 minutes.

### FR-ADMIN-002 — User Management
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-J-002  
Admins must manage user accounts.  
**Acceptance Criteria:**
- View, suspend, reinstate, delete users.
- All actions logged with admin ID, timestamp, reason.

### FR-ADMIN-003 — SMS Provider Mode Configuration
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-J-003  
Admins must be able to toggle SMS mode.  
**Acceptance Criteria:**
- Requires admin re-authentication.
- Switching to live shows cost warning confirmation dialog.
- Current mode prominently displayed.

### FR-ADMIN-004 — SMS Audit Log
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-J-004  
Admins must view the SMS audit log.  
**Acceptance Criteria:**
- Includes message ID, masked recipient, provider, status, timestamp.
- Searchable by date range, status, user.
- Read-only from admin UI.

### FR-ADMIN-005 — Country Capability Management
**Priority:** POST-MVP | **Phase:** 2 | **Was:** FR-J-005  
Admins must configure per-country SMS capabilities.  
**Acceptance Criteria:**
- Configurable: outbound, inbound, alphanumeric sender, registered sender required, content restrictions.
- Changes effective immediately without code deploy.

### FR-ADMIN-006 — AI Usage Metrics
**Priority:** POST-MVP | **Phase:** 3  
Admins must view AI usage metrics.  
**Acceptance Criteria:**
- Feature usage counts, token totals, average latency.
- Visible in admin dashboard.

---

## Module CLASSIC — Classic and Modern Mode

### FR-CLASSIC-001 — Mode Toggle
**Priority:** POST-MVP | **Phase:** 5 | **Was:** FR-K-001  
Users must be able to switch between Classic and Modern modes.  
**Acceptance Criteria:**
- Toggle in account settings and main interface.
- Preference persisted in user profile.
- All core features functional in both modes.

### FR-CLASSIC-002 — Classic Mode Appearance
**Priority:** POST-MVP | **Phase:** 5 | **Was:** FR-K-002  
Classic Mode must evoke the original Chikka's visual identity.  
**Acceptance Criteria:**
- Original-inspired colour scheme and typography (no licensed assets without permission).
- Buddy list layout resembling original Chikka.
- Identified as independent inspired design; not an official reproduction.

### FR-CLASSIC-003 — Modern Mode (Default)
**Priority:** MVP | **Phase:** 1 | **Was:** FR-K-003  
Modern Mode is the default interface.  
**Acceptance Criteria:**
- Split-panel layout; contact list left, active conversation right.
- shadcn/ui + Tailwind.
- Fully mobile-responsive.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft using domain-prefixed IDs |

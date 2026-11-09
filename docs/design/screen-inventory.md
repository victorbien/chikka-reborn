# Screen Inventory

**Document:** CHKR-DESIGN-004  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document catalogues every screen in Chikka Reborn with its route, description, key components, states to design, feature requirements, and development phase.

## Scope

All screens across Modern Mode, Classic Mode, and Admin Dashboard. This is the authoritative list for design and frontend implementation work.

---

## Screen ID Convention

`SCR-[AREA]-[NNN]`

- `AUTH` — Authentication screens
- `MAIN` — Main application screens
- `SMS` — SMS-specific screens
- `AI` — AI assistant screens
- `CREDIT` — Credits screens
- `SETTINGS` — Settings screens
- `ADMIN` — Administration screens

---

## Authentication Screens

### SCR-AUTH-001 — Login Screen
**Route:** `/login`  
**Phase:** 1  
**FR:** FR-AUTH-004  

**Description:** Entry point for returning users. Email/password login with social login options.

**Key Components:**
- Email input + password input with show/hide toggle
- Google OAuth button
- GitHub OAuth button
- "Forgot password?" link
- Submit button (loading state on submit)
- Link to registration

**States:**
- Default (empty form)
- Loading (form submitted)
- Error (invalid credentials — generic message only)
- Rate limited (5 failed attempts)

---

### SCR-AUTH-002 — Registration Screen
**Route:** `/register`  
**Phase:** 1  
**FR:** FR-AUTH-001  

**Description:** New user registration with email and password.

**Key Components:**
- Display name, email, password, confirm password fields
- Password strength indicator
- Terms of service agreement checkbox
- Submit button

**States:**
- Default, loading, field-level validation errors, success (redirect to verify-email)

---

### SCR-AUTH-003 — Email Verification Prompt
**Route:** `/verify-email`  
**Phase:** 1  
**FR:** FR-AUTH-002  

**Description:** Shown after registration and when an unverified user tries to access restricted features.

**Key Components:**
- Status message ("Check your inbox")
- Resend verification email button (with cooldown)
- Continue to app button (limited access)

---

### SCR-AUTH-004 — Password Reset Request
**Route:** `/reset-password`  
**Phase:** 1  
**FR:** FR-AUTH-005  

**Description:** User enters their email to receive a reset link.

**Key Components:**
- Email input
- Submit button
- "Back to login" link

**States:** Default, loading, success (always — prevents email enumeration), error

---

### SCR-AUTH-005 — New Password Form
**Route:** `/reset-password/confirm`  
**Phase:** 1  
**FR:** FR-AUTH-005  

**Description:** User sets a new password after clicking the reset link in their email.

**Key Components:**
- New password + confirm password fields
- Submit button

---

## Main Application Screens

### SCR-MAIN-001 — Conversation List
**Route:** `/app/messages`  
**Phase:** 1  
**FR:** FR-MSG-004, FR-MSG-011  

**Description:** List of all conversations. Entry point after login.

**Key Components:**
- Conversation list items (avatar, name, last message preview, timestamp, unread count)
- "New conversation" button
- Search/filter input

**States:** Loading (skeleton), empty ("Start a conversation"), populated list

---

### SCR-MAIN-002 — Active Conversation
**Route:** `/app/messages/:conversationId`  
**Phase:** 1  
**FR:** FR-MSG-001–006  

**Description:** The core messaging screen. Shows conversation history and compose field.

**Key Components:**
- Header: contact name, online status, message actions menu
- Message thread (scroll area): message bubbles with status icons, SIMULATED badges, SMS labels, date separators
- Typing indicator
- Compose area: textarea, emoji picker, AI assistant button, send button
- SMS segment counter (when conversation is SMS type)
- AI suggestion panel (collapsible)

**States:** Loading history, empty conversation, populated, sending, error

---

### SCR-MAIN-003 — Contacts / Buddy List
**Route:** `/app/contacts`  
**Phase:** 1  
**FR:** FR-CONTACTS-001–004, FR-CONTACTS-011  

**Description:** List of all contacts — Chikka users and SMS contacts. Search and add.

**Key Components:**
- Search bar (searches Chikka users by username/email)
- Contact list (alphabetical, presence dot, SMS badge for SMS contacts)
- Add contact button → Add contact modal
- Contact row actions: message, block, remove

**States:** Loading, empty ("Add your first contact"), populated, no search results

---

### SCR-MAIN-004 — Add Contact Modal
**Route:** `/app/contacts` (modal overlay)  
**Phase:** 1–2  
**FR:** FR-CONTACTS-001, FR-CONTACTS-002  

**Description:** Add a Chikka user or an SMS contact.

**Key Components:**
- Tabs: "Chikka User" / "SMS Number"
- Chikka tab: search field + user search results
- SMS tab: phone number input + display name field + country capability check
- Add button

---

## SMS Screens

### SCR-SMS-001 — New SMS Compose
**Route:** `/app/sms/new`  
**Phase:** 2  
**FR:** FR-SMS-001–005  

**Description:** Compose and send an SMS to any phone number.

**Key Components:**
- Recipient phone number input (E.164 format hint)
- Country capability indicator (outbound: ✓, inbound: ✓ / requires verification)
- Message textarea
- SMS segment counter + credit cost display
- Character count progress bar
- SIMULATED mode banner (when in simulation mode)
- Send button (disabled if insufficient credits)
- Credit balance link

**States:** Default, loading capability check, unsupported country error, insufficient credits, loading (sending), success, failure

---

### SCR-SMS-002 — Outbound SMS Detail
**Route:** `/app/messages/:conversationId` (SMS conversation)  
**Phase:** 2  
**FR:** FR-SMS-004  

**Description:** Shows a conversation thread with an SMS contact. Outbound SMS messages show SIMULATED badge and delivery status.

*Reuses SCR-MAIN-002 with SMS-specific overlays (SIMULATED badge, SMS origin labels, segment counter in compose area).*

---

## AI Assistant Screens (Phase 3)

### SCR-AI-001 — AI Suggestion Panel
**Route:** Overlay within active conversation  
**Phase:** 3  
**FR:** FR-AI-001–007  

**Description:** The AI assistant panel — appears within the conversation screen when any AI feature is triggered.

**Key Components:**
- Panel header with feature name (e.g. "Smart Replies", "Translation", "Rewrite")
- Loading state while AI processes
- Result display (suggestions list for smart reply; before/after for translation/rewrite; optimised text for SMS optimise)
- Accept / Edit / Dismiss / Regenerate actions
- AI-assisted badge on compose field when suggestion is accepted
- Latency indicator (shows processing time)

**States:** Hidden, loading, results shown, error (non-blocking), dismissed

---

## Credits Screens

### SCR-CREDIT-001 — Credits Overview
**Route:** `/app/credits`  
**Phase:** 2  
**FR:** FR-CREDIT-001, FR-CREDIT-002, FR-CREDIT-003, FR-CREDIT-004  

**Description:** Credit balance, usage history, and top-up.

**Key Components:**
- Current balance display (large, prominent)
- Available vs reserved breakdown
- Per-country credit rate table
- Transaction history list (paginated)
- Top-up button (Phase 4)
- Low-balance warning banner

**States:** Loading, populated, empty history, low balance warning

---

## Settings Screens

### SCR-SET-001 — Account Settings Hub
**Route:** `/app/settings`  
**Phase:** 1  

**Description:** Settings landing page with navigation to sub-sections.

**Key Components:**
- Navigation links to: Profile, Privacy, Notifications, UI Mode
- Account deletion section (destructive, requires confirmation)

---

### SCR-SET-002 — Profile Edit
**Route:** `/app/settings/profile`  
**Phase:** 1  
**FR:** FR-AUTH-007, FR-AUTH-008  

**Key Components:**
- Avatar upload
- Display name, bio, country selector
- Mobile phone number (with OTP verification flow, Phase 2)
- Save button

---

### SCR-SET-003 — Privacy Settings
**Route:** `/app/settings/privacy`  
**Phase:** 1  
**FR:** FR-PRIVACY-001, FR-PRIVACY-002  

**Key Components:**
- Profile visibility selector (all / contacts / private)
- Data export request button
- SMS opt-in/out preferences

---

### SCR-SET-004 — Notification Preferences
**Route:** `/app/settings/notifications`  
**Phase:** 2  
**FR:** FR-NOTIF-002, FR-NOTIF-005  

**Key Components:**
- Push notification enable/disable toggle
- Per-notification-type toggles (new message, SMS delivery, low balance)

---

### SCR-SET-005 — UI Mode Selection
**Route:** `/app/settings/mode`  
**Phase:** 5  
**FR:** FR-CLASSIC-001, FR-CLASSIC-002  

**Key Components:**
- Mode preview cards: Modern vs Classic
- Radio selector to choose mode
- Save preference button

---

## Admin Screens

### SCR-ADMIN-001 — Admin Overview
**Route:** `/admin`  
**Phase:** 2  
**FR:** FR-ADMIN-001  

**Key Components:**
- Stat cards: total users, active users, messages sent, SMS sent, delivery rate, AI requests
- Time period selector (24h / 7d / 30d)
- Quick links to audit logs, user management, config

---

### SCR-ADMIN-002 — User Management
**Route:** `/admin/users`  
**Phase:** 2  
**FR:** FR-ADMIN-002  

**Key Components:**
- Searchable, sortable user table (email, display name, joined date, status)
- Filter by status (active / suspended)
- Row actions: view, suspend, reinstate, delete (with confirmation)

---

### SCR-ADMIN-003 — SMS Audit Log
**Route:** `/admin/sms-logs`  
**Phase:** 2  
**FR:** FR-ADMIN-004  

**Key Components:**
- Filterable log table (date range, status, user, provider)
- Row: message ID, masked recipient, provider, segments, status, timestamp
- Export to CSV button

---

### SCR-ADMIN-004 — Platform Configuration
**Route:** `/admin/config`  
**Phase:** 2  
**FR:** FR-ADMIN-003  

**Key Components:**
- SMS mode indicator + toggle (requires re-auth + confirmation)
- Feature flag toggles
- Current mode prominent display

---

### SCR-ADMIN-005 — Country Capabilities
**Route:** `/admin/countries`  
**Phase:** 2  
**FR:** FR-ADMIN-005  

**Key Components:**
- Country table with capability columns
- Edit row inline (outbound, inbound, sender ID, cost per segment)
- Save changes button per row

---

### SCR-ADMIN-006 — AI Usage Metrics
**Route:** `/admin/ai-metrics`  
**Phase:** 3  
**FR:** FR-ADMIN-006  

**Key Components:**
- Feature usage bar chart
- Token usage over time
- Average latency per feature
- Failure rate

---

## Screen Count Summary

| Area | Screen Count | Phase |
|---|---|---|
| Authentication | 5 | 1 |
| Main Application | 4 | 1–2 |
| SMS | 2 | 2 |
| AI Assistant | 1 | 3 |
| Credits | 1 | 2 |
| Settings | 5 | 1–5 |
| Admin | 6 | 2–3 |
| **Total** | **24** | — |

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

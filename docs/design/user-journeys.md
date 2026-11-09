# User Journeys

**Document:** CHKR-DESIGN-005  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document defines the critical user journeys through Chikka Reborn — the end-to-end paths a user takes to accomplish a core task. Each journey maps screens, decisions, happy paths, and error paths.

## Scope

Primary journeys for all five user personas. Used for E2E test scenario planning and UX validation.

---

## Journey 1 — New User Registration and First Login

**Persona:** Any new user (Marites, Jericho, Rowena)  
**Goal:** Create an account and access the messaging interface.

```mermaid
flowchart TD
    A[Land on /login] --> B{Has account?}
    B -->|No| C[Click 'Create account']
    C --> D[SCR-AUTH-002: Fill registration form]
    D --> E{Form valid?}
    E -->|No| F[Show field errors]
    F --> D
    E -->|Yes| G[Submit → POST /auth/register]
    G --> H[SCR-AUTH-003: Check your email prompt]
    H --> I[Click verification link in email]
    I --> J[Redirect to /app/messages]
    J --> K[SCR-MAIN-001: Empty conversation list]
    K --> L[Prompted to add first contact]

    B -->|Yes| M[SCR-AUTH-001: Enter credentials]
    M --> N{Auth success?}
    N -->|No| O[Generic error shown\nno email enumeration]
    O --> M
    N -->|Yes| J
```

**Error Paths:**
- Duplicate email → field error on registration form.
- Expired verification link → "Resend" button available.
- 5 failed logins → rate limit message; 15-minute wait.

---

## Journey 2 — Sending a Chikka-to-Chikka Message

**Persona:** Jericho (registered Chikka user to registered Chikka user)  
**Goal:** Send a real-time message to a friend on Chikka.

```mermaid
flowchart TD
    A[SCR-MAIN-001: Conversation List] --> B{Conversation exists?}
    B -->|Yes| C[Click existing conversation]
    B -->|No| D[Go to Contacts → SCR-MAIN-003]
    D --> E[Search for user by username]
    E --> F[Add as contact]
    F --> G[Open conversation]
    C --> G
    G --> H[SCR-MAIN-002: Active Conversation]
    H --> I[Type message in compose field]
    I --> J[Click Send]
    J --> K[Message appears in thread with 'Sent' status]
    K --> L{Recipient online?}
    L -->|Yes| M[Recipient receives via Supabase Realtime\nStatus → Delivered]
    L -->|No| N[Message queued in DB\nDelivered when recipient connects]
    M --> O[Recipient opens conversation\nStatus → Read]
    O --> P[Sender sees 'Read' with timestamp]
```

---

## Journey 3 — Sending an Internet-to-SMS Message (Simulation Mode)

**Persona:** Marites (OFW sending to Lolo Ben)  
**Goal:** Send an SMS message to a basic phone user.

```mermaid
flowchart TD
    A[Click 'Send SMS' in sidebar] --> B[SCR-SMS-001: SMS Compose]
    B --> C[Enter recipient phone number\n+639171234567]
    C --> D[System checks country capability\nGET /sms/capability]
    D --> E{Country supported?}
    E -->|No| F[Error shown: Unsupported destination\nSend blocked]
    E -->|Yes| G[Capability info shown:\nOutbound: ✓  Inbound: requires verification\nCost: 0.05 credits/segment]
    G --> H[Type message body]
    H --> I[Real-time segment counter:\n'45 / 160 chars | 1 segment | 0.05 credits']
    I --> J{Sufficient credits?}
    J -->|No| K[Send button disabled\nLow balance warning shown\nLink to top-up]
    J -->|Yes| L[Click Send → POST /sms/send]
    L --> M[Message appears in thread\nWith SIMULATED badge\nStatus: Queued]
    M --> N[Mock callback after 2s\nStatus: Sent]
    N --> O[Mock callback after 2s\nStatus: Delivered]
    O --> P[Delivery notification appears\nin notification panel]
```

**Simulation Mode Invariants:**
- SIMULATED badge is visible at every step — Queued, Sent, Delivered.
- No real SMS is sent under any circumstances.
- No credits are deducted.

---

## Journey 4 — Receiving an Inbound SMS Reply

**Persona:** Marites (receiving Lolo Ben's reply)  
**Goal:** See a reply from the basic phone user in the conversation.

```mermaid
flowchart TD
    A[Lolo Ben receives SMS on Nokia 3310] --> B[Lolo Ben replies via standard SMS]
    B --> C[SMS reaches Twilio\nor MockSmsProvider]
    C --> D[POST /webhooks/sms/inbound]
    D --> E{Webhook signature valid?}
    E -->|No| F[403 Forbidden\nLogged\nNot processed]
    E -->|Yes| G[Match sender number to conversation]
    G --> H{Conversation found?}
    H -->|No| I[Stored as unmatched\nAdmin notified]
    H -->|Yes| J[INSERT messages\norigin=sms\nsender_phone=+639171234567]
    J --> K[Supabase Realtime push\nto Marites browser]
    K --> L[New message appears in thread\nWith SMS badge]
    L --> M[Marites sees reply in real time]
```

---

## Journey 5 — Using AI Translation

**Persona:** Rowena (translating a message from English to Filipino)  
**Goal:** Translate a draft message and send it after review.

```mermaid
flowchart TD
    A[SCR-MAIN-002: Active Conversation with Nanay] --> B[Rowena types draft in English:\n'I hope you are feeling better soon.']
    B --> C[Click AI button → 'Translate']
    C --> D[Language selector appears\nRowena selects: Filipino]
    D --> E[POST /ai/translate\nBody: text + target_language]
    E --> F{AI available?}
    F -->|No| G[Error shown:\n'AI unavailable. You can still send manually.'\nCompose field remains active]
    F -->|Yes| H[AI processes\nLoading indicator shown\nCompose field still editable]
    H --> I[Translation returned:\n'Umaasa akong mabilis kang mabuting muli.']
    I --> J[AI suggestion panel shows\nbefore: English | after: Filipino]
    J --> K{Rowena satisfied?}
    K -->|No, edit| L[Edits translation in panel]
    L --> M
    K -->|Yes| M[Click 'Use this translation']
    M --> N[Translation placed in compose field\nAI-assisted badge appears]
    N --> O{Send?}
    O -->|No| P[Can still edit compose field\nBadge persists until field cleared]
    O -->|Yes| Q[Click Send]
    Q --> R[Message sent\nAI-assisted badge removed from recipient's view]
```

**AI Safety Invariants:**
- The AI translation is never auto-sent.
- Rowena explicitly clicks "Use this translation" then separately clicks "Send".
- If she clears the compose field, the AI-assisted badge disappears.
- If AI fails at any step, her original English draft is preserved.

---

## Journey 6 — Admin Switching SMS to Live Mode

**Persona:** Mark (administrator enabling live SMS for integration testing)  
**Goal:** Switch from simulation to live SMS mode safely.

```mermaid
flowchart TD
    A[Mark logs into /admin] --> B[SCR-ADMIN-004: Platform Configuration]
    B --> C[Sees: SMS Mode: SIMULATION]
    C --> D[Clicks 'Switch to Live Mode']
    D --> E[Confirmation dialog appears:\n'This will send real SMS messages.\nReal costs will be incurred.\nThis action requires re-authentication.']
    E --> F{Mark confirms?}
    F -->|No| G[Dialog closes\nMode unchanged]
    F -->|Yes| H[Re-authentication prompt\nEnter password]
    H --> I{Auth success?}
    I -->|No| J[Auth error\nMode unchanged]
    I -->|Yes| K[Mode switches to LIVE\nPage shows: SMS Mode: LIVE ⚠]
    K --> L[Admin action logged:\nmark@chikka.app switched to live mode\ntimestamp]
    L --> M[All subsequent SMS sends\nuse TwilioSmsProvider\nReal messages sent\nCredits consumed]
```

**Invariants:**
- At least 3 friction steps before live mode activates (click → confirm dialog → re-auth).
- Mode change is logged with admin ID, timestamp, and previous state.
- If re-auth fails, mode does not change.
- Switching back to simulation follows the same flow.

---

## Journey 7 — User Account Deletion

**Persona:** Any registered user  
**Goal:** Delete their account and all personal data.

```mermaid
flowchart TD
    A[SCR-SET-001: Account Settings] --> B[Scroll to 'Delete Account' section]
    B --> C[Click 'Delete my account']
    C --> D[Warning dialog:\n'This will permanently delete your account.\nYour personal data will be erased within 30 days.\nYour conversation history will be anonymised.\nThis cannot be undone.']
    D --> E{Confirm?}
    E -->|No| F[Dialog closes\nNo action]
    E -->|Yes| G[Re-authentication prompt\nEnter password]
    G --> H{Auth success?}
    H -->|No| I[Error shown\nNo action]
    H -->|Yes| J[DELETE /users/me\nAccount deletion scheduled]
    J --> K[All sessions invalidated immediately]
    K --> L[Redirect to /login\nConfirmation message shown]
    L --> M[Background: personal data erasure\nwithin 30 days\nConversation history anonymised]
```

---

## Journey 8 — Credit Top-Up (Phase 4)

**Persona:** Marites (running low on credits)  
**Goal:** Top up credit balance before sending an SMS.

```mermaid
flowchart TD
    A[Low balance warning appears\nin conversation or credits page] --> B[Click 'Top up now']
    B --> C[SCR-CREDIT-001: Credits page]
    C --> D[Select top-up amount]
    D --> E[Click 'Top up' → initiates payment flow]
    E --> F[Payment gateway UI\nPayment TBD - OD-001]
    F --> G{Payment success?}
    G -->|No| H[Payment error\nBalance unchanged]
    G -->|Yes| I[Credits added to account\nBalance updated in real time]
    I --> J[Success message shown]
    J --> K[User returns to SMS compose\nSend button now enabled]
```

> **Note:** Payment gateway is an open decision (OD-001). This journey will be updated when the gateway is selected.

---

## Journey Summary

| Journey | Persona | Phase | E2E Test Coverage |
|---|---|---|---|
| 1 — Registration + Login | All | 1 | ✅ Required Phase 1 |
| 2 — Chikka-to-Chikka Message | Jericho | 1 | ✅ Required Phase 1 |
| 3 — Internet-to-SMS (Simulation) | Marites | 2 | ✅ Required Phase 2 |
| 4 — Inbound SMS Reply | Marites / Lolo Ben | 2 | ✅ Required Phase 2 |
| 5 — AI Translation | Rowena | 3 | ✅ Required Phase 3 |
| 6 — Admin Live SMS Toggle | Mark | 2 | ✅ Required Phase 2 |
| 7 — Account Deletion | Any | 1 | ✅ Required Phase 1 |
| 8 — Credit Top-Up | Marites | 4 | ⬜ Required Phase 4 |

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

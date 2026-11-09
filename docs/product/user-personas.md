# User Personas

**Document:** CHKR-PROD-004  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document defines five representative user personas for Chikka Reborn. Each persona gives the product and engineering team a concrete human to design for. Personas are derived from the user segments in `docs/product/target-users.md`.

## Scope

Personas apply across all product, design, and UX decisions. They are used to validate feature priorities, evaluate interface designs, and ground acceptance criteria in real human contexts.

---

## Persona 1 — Marites, The OFW in Dubai

**Segment:** Diaspora Sender  
**Age:** 38  
**Location:** Dubai, UAE  
**Occupation:** Domestic worker  

### Background
Marites has been working in Dubai for 6 years. She sends money home every month to her parents and two children in Tarlac, Central Luzon. She communicates with her family daily using WhatsApp when they are near Wi-Fi, but her parents have a basic Nokia phone and no internet access. Before Chikka shut down, she used it to message her parents directly. Since then, she has been relying on expensive international SMS from her UAE SIM.

### Goals
- Message her parents directly from her phone without asking them to install anything.
- Receive their replies in the same chat window.
- Compose messages in Filipino without auto-correct changing her words.
- Understand her SMS credit balance before hitting send.

### Frustrations
- WhatsApp doesn't reach her parents at all.
- International SMS from her carrier costs 1 AED per message.
- Her parents sometimes don't understand messages she writes in English.

### How Marites Uses Chikka Reborn
- Opens the app on her Android phone's browser.
- Sees her contact "Nanay" with an SMS icon.
- Types a message in Filipino; the character counter shows 1 segment.
- Sends the message; sees "Delivered" status when her mother's phone receives it.
- Her mother replies via SMS; the reply appears in the same thread.
- When composing a long update, she uses AI to shorten it to fit one SMS.

### Key Feature Dependencies
- `FR-AUTH-001`, `FR-AUTH-004` — Account and login
- `FR-SMS-001`, `FR-SMS-002` — Internet-to-SMS send with segment preview
- `FR-SMS-RECV-001` — Inbound SMS to conversation
- `FR-AI-004` — SMS length optimisation
- `FR-CREDIT-001` — Credit balance visible before send

### Design Notes
- Must work on a mid-range Android browser with moderate bandwidth.
- Filipino language must be fully supported in all text fields.
- Low-balance warning must be prominent — Marites monitors her credits carefully.

---

## Persona 2 — Lolo Ben, The Basic Phone Recipient

**Segment:** Basic Phone Recipient / SMS User  
**Age:** 72  
**Location:** Tarlac, Philippines  
**Device:** Nokia 3310 (no internet)  

### Background
Lolo Ben (Ben is Marites's father) retired from farming. He has never used a smartphone and has no interest in learning. He calls his daughter monthly using a prepaid load. He receives messages from Marites via SMS and replies by composing a standard text message. He has no Chikka account and never will.

### Goals
- Receive messages from Marites on his phone.
- Reply with a short text and know it reaches her.

### Frustrations
- He sometimes receives messages from unknown numbers and doesn't know if they are from Marites.
- Long messages get cut off on his screen.

### How Lolo Ben Interacts with Chikka Reborn
- Lolo Ben does not interact with the Chikka Reborn platform directly.
- He receives Marites's message as a standard SMS on his Nokia phone.
- The message appears from a Chikka platform number — consistent enough for him to save in his contacts.
- He replies using his phone's SMS compose screen.
- His reply appears in Marites's conversation thread on Chikka Reborn.

### Key Constraints
- No internet access. No app. No account.
- Platform must never require him to do anything beyond standard SMS.
- Two-way SMS availability for Philippines requires carrier verification (RISK-001, RISK-004).

### Design Notes
- This persona validates the core SMS architecture, not the UI.
- The SMS message he receives must be clear and identify Marites as the sender (display name or registered sender ID).

---

## Persona 3 — Jericho, The Local Power User

**Segment:** Registered Chikka User / Local Internet User  
**Age:** 25  
**Location:** Quezon City, Philippines  
**Occupation:** Freelance graphic designer  

### Background
Jericho grew up using the original Chikka and has strong nostalgia for it. He is tech-savvy, uses his laptop and phone constantly, and has both internet-connected friends and older relatives on basic phones. He heard about Chikka Reborn and signed up immediately. He switches between Modern Mode for daily use and Classic Mode when he wants the nostalgic feel.

### Goals
- Message friends in real time.
- Send SMS to his lola who doesn't have a smartphone.
- Use AI smart replies when he's busy.
- Experience the Classic Chikka interface he remembers from his youth.

### Frustrations
- Modern messaging apps feel impersonal for reaching older relatives.
- He wants one app for everything, not separate platforms for different audiences.

### How Jericho Uses Chikka Reborn
- Logs in on desktop; uses Modern Mode for most conversations.
- Switches to Classic Mode on weekends for the nostalgia.
- Uses smart reply suggestions when juggling multiple client conversations.
- Uses tone adjustment to make a client update sound more professional.
- Sends SMS to his lola; monitors the delivery status.
- Views his credit balance in the top navigation bar.

### Key Feature Dependencies
- `FR-MSG-001`–`FR-MSG-006` — Full messaging feature set
- `FR-AI-001`, `FR-AI-003` — Smart replies and message rewriting
- `FR-CLASSIC-001`, `FR-CLASSIC-002` — Classic Mode
- `FR-SMS-001`–`FR-SMS-004` — Full SMS send flow
- `FR-NOTIF-001`, `FR-NOTIF-002` — Notifications

### Design Notes
- Jericho is the primary Classic Mode tester. Classic Mode must feel authentic, not ironic.
- AI features must be fast; Jericho is busy. A 5-second AI response feels long to him.
- He will notice anything that feels "off" about the Classic Mode because he remembers the original.

---

## Persona 4 — Rowena, The Multilingual Sender

**Segment:** Multilingual Communicator  
**Age:** 45  
**Location:** Toronto, Canada  
**Occupation:** Registered nurse  

### Background
Rowena immigrated to Canada 12 years ago. She communicates with family in the Philippines in a mix of Filipino, Cebuano, and English depending on the recipient. Her mother speaks primarily Cebuano; her teenage niece speaks mostly English. She uses AI translation to adapt her messages for each recipient without composing entirely separate messages.

### Goals
- Compose a message in English and translate it to Filipino for her mother.
- Verify the translation before sending — she has been burned by bad auto-translations before.
- Summarise a long conversation thread before jumping back in after a busy week.

### Frustrations
- Automatic translation in other apps sends the translation immediately without showing her first.
- She often has to re-read many messages to catch up on a conversation she was away from.

### How Rowena Uses Chikka Reborn
- Composes a message in English.
- Clicks "Translate" → selects Filipino.
- Reviews the translation in the AI suggestion panel.
- Makes a small edit to naturalise a phrase.
- Accepts and sends.
- After a busy week, opens the conversation and clicks "Summarise" to get the gist before reading in full.

### Key Feature Dependencies
- `FR-AI-002` — Message translation with user review before send
- `FR-AI-003` — Message rewriting
- `FR-AI-005` — Conversation summary
- `FR-AI-006` — Mandatory approval gate

### Design Notes
- The AI suggestion panel must clearly show the before/after of any translation or rewrite.
- Rowena must always be able to edit a translation before accepting it — AI is a starting point.
- The summarise feature must be on-demand, not automatic.

---

## Persona 5 — Mark, The Platform Administrator

**Segment:** Platform Administrator  
**Age:** 30  
**Location:** Remote  
**Occupation:** Full-stack developer / Platform operator  

### Background
Mark is one of the Chikka Reborn developers. He manages the staging and production environments. During Phase 2 testing, he switches SMS mode from simulation to live for integration tests. He monitors the admin dashboard to check delivery rates and AI usage.

### Goals
- Switch SMS from simulation to live mode safely, with confirmation steps.
- View SMS audit logs when a message is reported as undelivered.
- Monitor AI token usage to manage costs.
- Manage user accounts if abuse is reported.

### Frustrations
- Switching modes is irreversible in the short term — he wants to be sure before doing it.
- SMS delivery failures are hard to debug without full logs.

### How Mark Uses Chikka Reborn
- Logs into the admin dashboard at `/admin`.
- Checks platform stats: messages sent today, delivery rate, active users.
- Reviews SMS audit logs to investigate a specific undelivered message.
- Switches SMS provider mode to live — is prompted to re-authenticate before the change takes effect.
- Views AI usage: which features are most used, average latency, total tokens this month.
- Suspends a user account flagged for abuse.

### Key Feature Dependencies
- `FR-ADMIN-001`–`FR-ADMIN-005` — Full admin feature set
- `FR-ADMIN-003` — SMS mode toggle with re-authentication
- `FR-ADMIN-004` — SMS audit log
- `FR-ADMIN-006` — AI metrics

### Design Notes
- The SMS mode switch must have at least two confirmation steps: initial click + re-authentication + confirmation dialog with cost warning.
- Audit logs must be searchable and exportable.
- Admin UI can be dense — Mark is technical. Clarity is more important than simplicity here.

---

## 6. Persona–Feature Mapping Summary

| Feature Area | Marites | Lolo Ben | Jericho | Rowena | Mark |
|---|---|---|---|---|---|
| Email registration / login | ✅ | ❌ | ✅ | ✅ | ✅ |
| Chikka-to-Chikka messaging | ❌ | ❌ | ✅ | ✅ | ❌ |
| Internet-to-SMS | ✅ | ❌ (recipient) | ✅ | ✅ | ❌ |
| SMS-to-Internet | ✅ (receives) | ✅ (sends) | ✅ | ✅ | ❌ |
| AI translation | ✅ | ❌ | ❌ | ✅ | ❌ |
| AI smart replies | ❌ | ❌ | ✅ | ❌ | ❌ |
| AI SMS optimisation | ✅ | ❌ | ❌ | ❌ | ❌ |
| Conversation summary | ❌ | ❌ | ❌ | ✅ | ❌ |
| Classic Mode | ❌ | ❌ | ✅ | ❌ | ❌ |
| Credit balance | ✅ | ❌ | ✅ | ✅ | ❌ |
| Admin dashboard | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 7. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

# Product Requirements Document (PRD)

> **SUPERSEDED (November 2026).** Retained for history. The canonical version is in docs/product/product-vision.md, product/product-overview.md, product/target-users.md. Requirement IDs here use the older scheme (e.g. FR-A-001); see the 'Was:' fields in docs/product/functional-requirements.md for the mapping.

**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Date:** November 2026  
**Category:** Kiroween 2026 — RESURRECTION  

---

## 1. Executive Summary

Chikka Reborn is a modern revival of the original Chikka messaging platform — the pioneering Filipino service that connected internet users with mobile phone users via SMS. After the original service was discontinued in 2018, a significant gap was left for users who valued the ability to communicate across internet and SMS boundaries.

This project resurrects that capability as a globally accessible, AI-enhanced, multilingual messaging platform. It is an independent, Chikka-inspired project and is not affiliated with or endorsed by the original owners.

---

## 2. Problem Statement

### 2.1 The Gap Left by the Original Chikka

When Chikka shut down in 2018:
- Millions of users lost a free or low-cost bridge between internet and SMS communication.
- Filipino diaspora communities lost a convenient way to reach mobile-only relatives.
- Basic phone users lost access to internet-initiated messages directed at them.

### 2.2 Persisting Communication Barriers

Today, despite smartphone proliferation:
- A significant portion of the global population still uses basic (non-smart) mobile phones.
- Internet connectivity remains unreliable or unaffordable in many regions.
- Language barriers continue to hinder cross-border and cross-community communication.
- Existing messaging platforms require both parties to have the same app or internet access.

---

## 3. Product Vision

> "Everyone should be able to communicate, whether they have a smartphone, an internet connection, or just a basic mobile phone."

Chikka Reborn will be the platform that bridges the gap between the connected and the not-yet-connected — combining real-time messaging, SMS reach, and AI-powered communication tools in a single, accessible application.

---

## 4. Goals and Objectives

### 4.1 Primary Goals

| Goal | Description |
|---|---|
| Bridge internet and SMS | Allow internet users to send messages to any mobile phone number |
| Enable SMS replies | Allow basic phone users to reply and engage with the platform |
| Real-time messaging | Provide instant messaging between registered platform users |
| AI communication assistance | Help users communicate more effectively across languages and contexts |
| Global reach | Support international messaging with country-aware capability handling |

### 4.2 Success Metrics (Phase 1–2 Targets)

| Metric | Target |
|---|---|
| User registration completion rate | ≥ 80% of signup initiations |
| Message delivery rate (live SMS mode) | ≥ 95% for supported countries |
| Chikka-to-Chikka message latency | < 500ms end-to-end (p95) |
| AI suggestion acceptance rate | Tracked; target ≥ 30% |
| Accessibility compliance | WCAG 2.1 AA |
| Mobile usability score | Lighthouse ≥ 85 |

---

## 5. Target Users

### 5.1 Primary User Segments

**Internet User (Sender)**
- Has a computer, tablet, or smartphone with internet access.
- Wants to send messages to contacts who may or may not use Chikka.
- May want AI assistance to compose, translate, or refine messages.
- May be communicating across language boundaries.

**Basic Phone User (SMS Recipient/Sender)**
- Has a mobile phone capable of receiving and sending SMS.
- Does not necessarily have a smartphone or internet connection.
- Receives Chikka messages as standard SMS.
- Can reply via SMS and have that reply appear in Chikka Reborn.

**Registered Chikka User (Both directions)**
- Has a Chikka Reborn account with internet access.
- Messages other registered users in real time.
- Also sends SMS to non-Chikka contacts.

**International / Diaspora User**
- Communicates across country boundaries.
- May communicate in a non-English language.
- Values low-cost or credit-based international SMS.

### 5.2 Secondary User Segments

**Administrator**
- Manages the platform: user accounts, SMS credits, provider configuration, audit logs.

---

## 6. Scope

### 6.1 In Scope (All Phases)

| Module | Description |
|---|---|
| A — Authentication & User Management | Registration, login, profile, account settings |
| B — Contacts & Buddy List | Add, organise, and manage contacts |
| C — Real-Time Chikka-to-Chikka Messaging | Instant messaging between platform users via WebSocket |
| D — Internet-to-SMS Messaging | Send messages to any mobile number |
| E — SMS-to-Internet Messaging | Receive SMS replies in the platform |
| F — AI-Powered Chikka Assistant | Smart replies, translation, rewriting, summaries, SMS optimisation |
| G — Notifications | Real-time in-app and push notifications |
| H — SMS Credits & Cost Management | Credit balance, purchase, usage tracking, per-message cost |
| I — Privacy & Security | Consent, data controls, opt-out, privacy settings |
| J — Administration Dashboard | Platform management, monitoring, audit, configuration |
| K — Classic & Modern Mode | Nostalgic Chikka UI and modern chat interface |

### 6.2 Out of Scope (This Version)

- Voice or video calling.
- Group SMS (MMS or multi-party SMS threads).
- Native mobile applications (iOS/Android).
- End-to-end encryption for SMS (SMS is inherently unencrypted).
- Payments processing beyond credit top-up.
- Social features (public profiles, feeds, reactions).
- AI auto-sending without user approval (prohibited permanently).

---

## 7. Feature Requirements by Module

### Module A — Authentication and User Management

**User Stories:**
- As a new user, I can register with my email address and a password.
- As a new user, I can sign up using a social provider (Google, GitHub).
- As a returning user, I can log in securely and access my account.
- As a user, I can reset my forgotten password via email.
- As a user, I can set my display name, profile photo, and mobile phone number.
- As a user, I can verify my mobile phone number via SMS OTP.
- As a user, I can manage my account settings and change my password.
- As a user, I can delete my account and request data erasure.

**Acceptance Criteria (selected):**
- Registration requires a valid email and a password meeting minimum complexity requirements.
- A verification email is sent upon registration. Unverified accounts have limited access.
- Mobile number verification uses a 6-digit OTP valid for 10 minutes.
- Failed login attempts are rate-limited: 5 attempts before a temporary lockout.
- Account deletion removes all personal data within 30 days per data retention policy.

---

### Module B — Contacts and Buddy List

**User Stories:**
- As a user, I can search for other Chikka users by username or email.
- As a user, I can add a contact by entering a mobile phone number (SMS contact).
- As a user, I can organise contacts into groups or label them.
- As a user, I can see which of my contacts are online.
- As a user, I can block or mute a contact.
- As a user, I can remove a contact from my list.

**Acceptance Criteria (selected):**
- Contact search returns only users who have not set their profile to private.
- Blocking a user prevents them from seeing the blocker's online status and sending them messages.
- Contact lists are paginated for users with large contact lists.

---

### Module C — Real-Time Chikka-to-Chikka Messaging

**User Stories:**
- As a user, I can open a conversation with another registered Chikka user and send messages instantly.
- As a user, I can see when my message has been delivered and read.
- As a user, I can see when the other person is typing.
- As a user, I can send text messages with emoji.
- As a user, I can view my full conversation history.
- As a user, I can delete a message I sent (for myself, or for both parties within a time limit).

**Acceptance Criteria (selected):**
- Messages are delivered via WebSocket when both users are online.
- Messages are queued and delivered when the recipient comes online.
- Read receipts are displayed per message with a timestamp.
- Conversation history is paginated: load most recent 50 messages, with scroll-to-load-more.
- Messages are stored encrypted at rest in Supabase.

---

### Module D — Internet-to-SMS Messaging

**User Stories:**
- As a user, I can compose a message and send it to any mobile phone number.
- As a user, I can see how many SMS segments my message will use before sending.
- As a user, I can see the credit cost of the message before sending.
- As a user, I can track the delivery status of my sent SMS messages.
- As a user, I can view simulated messages clearly labelled as such when in simulation mode.

**Acceptance Criteria (selected):**
- Segment count and credit cost are displayed in real time as the user types.
- In simulation mode, every outbound message shows a persistent "SIMULATED" label.
- In live mode, delivery status reflects the provider's actual delivery event, not mere acceptance.
- A message cannot be sent if the user has insufficient credits.
- Phone number input is validated for format and country capability before sending.

---

### Module E — SMS-to-Internet Messaging

**User Stories:**
- As a basic phone user, I can reply to a Chikka message by responding via SMS.
- As a Chikka user, I receive SMS replies in my conversation thread in real time.
- As a Chikka user, I can identify which replies came via SMS.

**Acceptance Criteria (selected):**
- Inbound SMS is matched to the correct conversation by sender phone number and originating number.
- SMS-originated messages are visually distinguished from Chikka-originated messages.
- Inbound webhook is validated before processing.
- Inbound SMS to unrecognised numbers generates a system notification to the operator.

---

### Module F — AI-Powered Chikka Assistant

**User Stories:**
- As a user, I can request smart reply suggestions for any conversation.
- As a user, I can request a translation of a message into a language I choose.
- As a user, I can ask the AI to rewrite my draft for clarity or tone.
- As a user, I can ask the AI to shorten my message to fit within SMS limits.
- As a user, I can request a summary of a long conversation.
- As a user, I must approve any AI-generated content before it is sent.

**Acceptance Criteria (selected):**
- AI suggestions are always presented in a review panel, never auto-inserted into the send field.
- An "AI-assisted" badge is visible on any unsent message that has been composed or significantly modified by AI.
- AI features degrade gracefully: failures do not block manual messaging.
- AI calls do not expose conversation content to logs.
- Every AI interaction records metadata: feature used, model, token counts, latency.

---

### Module G — Notifications

**User Stories:**
- As a user, I receive an in-app notification when I receive a new message.
- As a user, I receive a browser push notification when I have a new message and the app is not in focus.
- As a user, I can configure which notification types I receive.
- As a user, I can see a notification history.

---

### Module H — SMS Credits and Cost Management

**User Stories:**
- As a user, I can view my current credit balance.
- As a user, I can see the credit cost per message per destination country.
- As a user, I can view my usage history.
- As a user, I can top up my credits (payment integration TBD).
- As a user, I receive a low-balance warning before attempting to send.

**Acceptance Criteria (selected):**
- Credits are deducted only after provider acceptance.
- Credits are refunded for permanently failed messages.
- Simulation mode messages do not consume credits.
- Credit balance is displayed prominently in the messaging interface.

---

### Module I — Privacy and Security

**User Stories:**
- As a user, I can control who can see my profile information.
- As a user, I can opt out of SMS marketing or bulk messages.
- As a user, I can request a copy of my data.
- As a user, I can report abusive messages.

---

### Module J — Administration Dashboard

**User Stories:**
- As an admin, I can view platform-wide message volume and delivery statistics.
- As an admin, I can manage user accounts (suspend, reinstate, delete).
- As an admin, I can configure SMS provider mode (simulation vs live).
- As an admin, I can view SMS audit logs.
- As an admin, I can view AI usage metrics.
- As an admin, I can manage country capability configurations.
- As an admin, I can view credit transaction history across users.

---

### Module K — Classic Chikka Mode and Modern Mode

**User Stories:**
- As a user, I can switch between a nostalgic Classic Chikka interface and a modern chat interface.
- As a user, my mode preference is saved to my profile.
- Classic Mode preserves the look, feel, and interaction patterns of the original Chikka.
- Modern Mode provides a contemporary chat interface comparable to current messaging apps.

---

## 8. Design Principles

- **Accessibility first:** WCAG 2.1 AA compliance across all features.
- **Mobile-first responsive design:** All interfaces function on mobile and desktop.
- **Progressive enhancement:** Core functionality works without advanced browser features.
- **Clear system status:** Users always know what is happening (loading, sent, failed, simulated).
- **Honest capability display:** Never show features or statuses that are not real.
- **Nostalgic authenticity (Classic Mode):** Capture the spirit of the original without misleading users about affiliation.

---

## 9. Constraints and Assumptions

### Constraints
- SMS two-way messaging is not universally available. The platform must display per-country capability accurately.
- Amazon Bedrock availability is subject to AWS region support.
- SMS provider (Twilio) pricing and routing vary by country.
- Real SMS sending requires operator confirmation and must never be triggered by automated processes alone.
- Philippine A2P SMS requires sender ID registration.

### Assumptions
- Supabase provides sufficient real-time throughput for the expected message volume in early phases.
- Users on basic phones have SMS capability but no smartphone app.
- The primary development and staging environment will use simulation mode exclusively.
- Payment processing for credit top-up is deferred to a later phase (Phase 4+).

---

## 10. Open Decisions

| ID | Decision | Options | Owner | Due |
|---|---|---|---|---|
| OD-001 | Payment gateway for credit top-up | Stripe, PayMongo, deferred | Product | Phase 4 planning |
| OD-002 | Specific Amazon Bedrock model selection | Claude 3, Titan, etc. | Engineering | Phase 3 planning |
| OD-003 | Backend hosting platform | Render, Railway, Fly.io | DevOps | Phase 1 |
| OD-004 | Push notification service | Supabase Realtime, Web Push API, third-party | Engineering | Phase 2 |
| OD-005 | Classic Mode visual assets | Original-inspired originals vs licensed | Design/Legal | Phase 5 planning |
| OD-006 | Data retention period for messages | 90 days, 1 year, user-controlled | Product/Legal | Phase 1 |
| OD-007 | Philippine SMS sender ID registration | Pre-registered short code vs alphanumeric | Operations | Phase 2 |

---

## 11. Dependencies

| Dependency | Type | Impact |
|---|---|---|
| Supabase account and project setup | External service | Blocks Phase 1 |
| Amazon Bedrock access in chosen AWS region | External service | Blocks Phase 3 |
| Twilio account and phone number | External service | Blocks Phase 2 live SMS |
| Philippine sender ID registration | Regulatory/Operational | Blocks PH live SMS |
| Vercel account | External service | Blocks Phase 1 deployment |

---

## 12. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

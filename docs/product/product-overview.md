# Product Overview

**Document:** CHKR-PROD-002  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document provides a concise, structured overview of Chikka Reborn as a product. It is the reference point for anyone who needs to understand what the product is, who it serves, what it does, and how it is built — without reading the full requirements or architecture documentation.

## Scope

Covers all modules across all development phases. Phase-specific details are in `docs/product/product-roadmap.md`.

---

## 1. Product Summary

| Attribute | Value |
|---|---|
| Product Name | Chikka Reborn |
| Tagline | The Messenger That Refused to Die |
| Category | Messaging Platform |
| Context | Kiroween 2026 — RESURRECTION |
| Type | Web application (SPA) |
| Primary Markets | Philippines, Filipino diaspora, global |
| Status | Phase 0 — Foundation |

---

## 2. What Chikka Reborn Does

Chikka Reborn enables three fundamental communication patterns:

```
Pattern 1: Internet → SMS
┌─────────────────┐          ┌──────────────────┐
│  Chikka User    │──SMS────▶│  Basic Phone User │
│  (web browser)  │          │  (any mobile)     │
└─────────────────┘          └──────────────────┘

Pattern 2: SMS → Internet
┌─────────────────┐          ┌──────────────────┐
│  Chikka User    │◀─SMS─────│  Basic Phone User │
│  (web browser)  │          │  (any mobile)     │
└─────────────────┘          └──────────────────┘

Pattern 3: Chikka → Chikka (real-time)
┌─────────────────┐          ┌──────────────────┐
│  Chikka User A  │◀────────▶│  Chikka User B   │
│  (web browser)  │ WebSocket│  (web browser)   │
└─────────────────┘          └──────────────────┘
```

---

## 3. Module Overview

| ID | Module | Description | Phase |
|---|---|---|---|
| A | Authentication & User Management | Registration, login, profile, phone verification, account management | 1 |
| B | Contacts & Buddy List | Add Chikka users and SMS contacts, presence indicators, contact groups | 1–2 |
| C | Real-Time Chikka-to-Chikka Messaging | Instant messaging, typing indicators, read receipts, message history | 1 |
| D | Internet-to-SMS Messaging | Compose and send SMS to any phone number, segment preview, credit cost display | 2 |
| E | SMS-to-Internet Messaging | Receive SMS replies in conversation, inbound webhook processing | 2 |
| F | AI-Powered Chikka Assistant | Smart replies, translation, rewriting, tone adjustment, summary, SMS optimisation | 3 |
| G | Notifications | In-app badges, browser push notifications, delivery status alerts | 1–2 |
| H | SMS Credits & Cost Management | Credit balance, deduction, refund, top-up, per-country pricing | 2–4 |
| I | Privacy & Security | Profile visibility, data export, opt-out, message reporting | 1–2 |
| J | Administration Dashboard | Stats, user management, SMS audit logs, provider config, AI metrics | 2 |
| K | Classic & Modern Mode | Nostalgic Chikka UI and modern split-panel chat interface | 1, 5 |

---

## 4. Technology Stack

### Frontend

| Technology | Role |
|---|---|
| React 18 + TypeScript | UI framework |
| Vite | Build tool |
| Tailwind CSS + shadcn/ui | Styling and component library |
| React Router v6 | Client-side routing |
| TanStack Query v5 | Server state management |
| React Hook Form + Zod | Form handling and validation |
| Supabase JS SDK | Auth, Realtime subscriptions |

### Backend

| Technology | Role |
|---|---|
| Python 3.12+ | Language |
| FastAPI | API framework |
| Pydantic v2 | Data validation and serialisation |
| SQLAlchemy 2.x (async) | ORM and database access |
| Uvicorn | ASGI server |

### Infrastructure & Services

| Service | Role |
|---|---|
| Supabase PostgreSQL | Primary database |
| Supabase Auth | User authentication and JWT issuance |
| Supabase Realtime | WebSocket push for messages and notifications |
| Supabase Storage | Profile avatars, data exports |
| Supabase RLS | Row-level data access control |
| Amazon Bedrock | AI model inference (Phase 3+) |
| Twilio | Live SMS provider (Phase 2+) |
| MockSmsProvider | Simulation mode (all phases) |
| Vercel | Frontend hosting and CDN |
| Render / Railway / Fly.io | Backend hosting (TBD — OD-003) |

---

## 5. SMS Operating Modes

The SMS subsystem operates in exactly one of two modes at any time:

### Simulation Mode (default)
- Uses `MockSmsProvider`.
- No real SMS is sent.
- Every simulated message is permanently labelled **SIMULATED** in the UI.
- Realistic delivery status callbacks are simulated.
- No credit costs are incurred.
- Safe in all environments.

### Live Mode
- Uses `TwilioSmsProvider` (or a configured equivalent).
- Real SMS is sent to real phone numbers.
- Real delivery status tracked via provider callbacks.
- Credits are consumed.
- **Requires explicit operator approval to activate.**
- Never falls back silently to simulation if it fails.

---

## 6. AI Assistant Summary

The AI assistant (powered by Amazon Bedrock) provides seven features:

| Feature | What It Does |
|---|---|
| Smart Reply Suggestions | Generates 2–3 contextually appropriate reply options |
| Message Translation | Translates a message into a user-selected language |
| Message Rewriting | Rewrites a draft for clarity, grammar, or tone |
| Tone Adjustment | Shifts tone: formal, casual, friendly, professional |
| Conversation Summary | Summarises recent messages in a thread |
| SMS Length Optimisation | Shortens a message to fit within SMS segment limits |
| AI Message Composition | Composes a full message from a brief user prompt |

**Invariant:** AI-generated content is always reviewed and explicitly approved by the user before it is sent. There is no auto-send path. This is a permanent architectural constraint.

---

## 7. User Interface Modes

### Modern Mode (default, Phase 1)
- Split-panel layout: contact/conversation list left, active conversation right.
- Contemporary design using shadcn/ui and Tailwind CSS.
- Fully responsive: works on mobile, tablet, and desktop.

### Classic Chikka Mode (Phase 5)
- Nostalgic layout inspired by the original Chikka interface.
- Buddy list design resembling the original.
- Original-inspired design — not a reproduction of licensed assets.
- Clearly identified as an independent, inspired design.

---

## 8. Security and Privacy Posture

- All user data protected by Supabase Row Level Security.
- JWTs issued and managed by Supabase Auth; validated by FastAPI on every request.
- No provider credentials ever exposed to the frontend.
- Phone numbers masked in all logs (country code + last 4 digits only).
- SMS opt-out honoured immediately and permanently.
- AI calls never log message content — metadata only.
- HTTPS everywhere. No HTTP in production.

---

## 9. Deployment Overview

| Component | Host |
|---|---|
| Frontend | Vercel (global CDN) |
| Backend | Render / Railway / Fly.io (TBD) |
| Database + Auth | Supabase |
| Environments | Development, Staging, Production |

---

## 10. Development Phase Summary

| Phase | Focus | Key Deliverables |
|---|---|---|
| 0 | Foundation | Documentation, project setup, scaffolding, CI/CD |
| 1 | Core Platform | Auth, contacts, real-time messaging, Modern Mode |
| 2 | SMS Integration | Internet-to-SMS, SMS-to-Internet, credits, admin basics |
| 3 | AI Features | All 7 AI assistant features via Bedrock |
| 4 | Credits & Admin | Full credit management, payment gateway, complete admin dashboard |
| 5 | Classic Mode & Polish | Classic UI, WCAG audit, i18n, performance |
| 6 | Production Hardening | Security audit, load testing, Philippine SMS live, legal docs |

---

## 11. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

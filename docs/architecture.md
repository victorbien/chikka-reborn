# System Architecture

> **SUPERSEDED (November 2026).** Retained for history. The canonical version is in docs/architecture/ (system, application, frontend, backend, security). Requirement IDs here use the older scheme (e.g. FR-A-001); see the 'Was:' fields in docs/product/functional-requirements.md for the mapping.

**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Date:** November 2026  

---

## 1. Architectural Goals

The architecture must satisfy the following quality attributes, derived from the Non-Functional Requirements Specification (`docs/nfrs.md`):

| Quality Attribute | Architectural Driver |
|---|---|
| Real-time messaging | WebSocket-based push delivery via Supabase Realtime |
| Scalability | Stateless FastAPI backend; horizontal scale-out |
| Reliability | Retry queues, idempotency, graceful degradation |
| Security | RLS, JWT auth, webhook validation, secrets management |
| Maintainability | Modular monolith, layered architecture, strict typing |
| Testability | Service layer isolation, dependency injection, provider abstraction |
| SMS correctness | Provider-agnostic interface, honest status reporting |
| AI safety | Backend-proxied AI, mandatory user approval before send |

---

## 2. Architectural Style

### Modular Monolith

Both the frontend and backend are structured as **modular monoliths**. This means:

- A single deployable unit per tier (one frontend app, one backend process).
- Internal module boundaries are enforced by directory structure and import rules, not process boundaries.
- Modules can be extracted into separate services in the future if specific scaling or isolation requirements emerge — but no such extraction is planned or needed for the current phases.

**Rationale:** Microservices introduce operational complexity (distributed tracing, inter-service auth, network latency, deployment choreography) that is unjustified for a platform of this scale. A well-structured monolith is faster to build, easier to test, and simpler to operate.

### Layered Backend Architecture

The FastAPI backend follows a strict layered architecture:

```
HTTP Layer      →  Route Handlers (thin, no business logic)
Service Layer   →  Business logic, orchestration, validation
Repository Layer → Database access (SQLAlchemy)
Provider Layer  →  External service adapters (SMS, AI, Auth)
```

No layer may access a lower layer by skipping an intermediate layer (i.e. route handlers do not call the database directly).

---

## 3. System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL ACTORS                           │
│                                                                     │
│   [Internet User]    [Basic Phone User]    [Administrator]          │
│        │                    │                    │                  │
└────────┼────────────────────┼────────────────────┼──────────────────┘
         │                    │ SMS                 │
         │ HTTPS/WSS          │ (carrier network)   │ HTTPS
         ▼                    ▼                     ▼
┌────────────────┐   ┌────────────────┐   ┌────────────────────────┐
│  React SPA     │   │  SMS Provider  │   │  Admin Dashboard       │
│  (Vercel CDN)  │   │  (Twilio /     │   │  (same React SPA,      │
│                │   │   Mock)        │   │   admin routes)        │
└───────┬────────┘   └───────┬────────┘   └──────────┬─────────────┘
        │                    │                        │
        │ HTTPS / WSS        │ Webhooks (HTTPS POST)  │ HTTPS
        ▼                    ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                              │
│                    (hosted: Render/Railway/Fly.io)                  │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐ │
│  │ Auth Router │  │ Message      │  │ SMS Router │  │ AI Router │ │
│  │             │  │ Router       │  │            │  │           │ │
│  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  └─────┬─────┘ │
│         │                │                │               │        │
│  ┌──────▼──────────────────────────────────▼───────────────▼─────┐ │
│  │                     Service Layer                              │ │
│  │  AuthService  MessageService  SmsService  AiService           │ │
│  │  UserService  ConversationSvc CreditService NotificationSvc   │ │
│  └──────┬──────────────────────────┬──────────────┬─────────────┘ │
│         │                          │              │                │
│  ┌──────▼──────┐          ┌────────▼──────┐  ┌───▼───────────┐   │
│  │  Repository │          │ Provider Layer│  │ Background    │   │
│  │  Layer      │          │               │  │ Task Queue    │   │
│  │  (SQLAlchemy│          │ SmsProvider   │  │               │   │
│  │   async)    │          │ AiProvider    │  │               │   │
│  └──────┬──────┘          └────────┬──────┘  └───────────────┘   │
└─────────┼───────────────────────────┼───────────────────────────────┘
          │                           │
          ▼                           ▼
┌──────────────────────┐   ┌─────────────────────────────────────────┐
│   Supabase           │   │   External Providers                    │
│                      │   │                                         │
│  PostgreSQL          │   │  ┌─────────────────┐  ┌──────────────┐ │
│  Auth (JWT)          │   │  │ Twilio (SMS)     │  │ Amazon       │ │
│  Realtime (WS)       │   │  │ MockSmsProvider  │  │ Bedrock (AI) │ │
│  Storage             │   │  └─────────────────┘  └──────────────┘ │
│  RLS Policies        │   └─────────────────────────────────────────┘
└──────────────────────┘
```

---

## 4. Frontend Architecture

### Technology
React 18, TypeScript (strict), Vite, Tailwind CSS, shadcn/ui, React Router v6, TanStack Query v5, React Hook Form, Zod.

### Module Structure

```
frontend/
├── src/
│   ├── main.tsx                  # Application entry point
│   ├── App.tsx                   # Root component, routing
│   ├── components/               # Shared UI components
│   │   ├── ui/                   # shadcn/ui base components
│   │   └── common/               # App-specific shared components
│   ├── features/                 # Feature modules (one per product module)
│   │   ├── auth/                 # Module A
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── api.ts
│   │   │   └── types.ts
│   │   ├── contacts/             # Module B
│   │   ├── messaging/            # Module C — Chikka-to-Chikka
│   │   ├── sms-send/             # Module D — Internet-to-SMS
│   │   ├── sms-receive/          # Module E — SMS-to-Internet
│   │   ├── ai-assistant/         # Module F
│   │   ├── notifications/        # Module G
│   │   ├── credits/              # Module H
│   │   ├── privacy/              # Module I
│   │   ├── admin/                # Module J
│   │   └── modes/                # Module K
│   ├── lib/                      # Utilities, helpers, constants
│   │   ├── api-client.ts         # Axios/fetch wrapper with auth headers
│   │   ├── supabase.ts           # Supabase client instance
│   │   ├── websocket.ts          # WebSocket client manager
│   │   └── utils.ts
│   ├── hooks/                    # Global shared hooks
│   ├── stores/                   # Global client state (Zustand if needed)
│   ├── types/                    # Global TypeScript types
│   └── styles/                   # Global styles, Tailwind config extensions
```

### State Management Strategy

| State Type | Tool |
|---|---|
| Server state (API data) | TanStack Query |
| Form state | React Hook Form |
| Real-time messages | Supabase Realtime subscription via TanStack Query |
| Global UI state (theme, mode) | React Context or Zustand (if needed) |
| Local component state | useState / useReducer |

No Redux. No global state management beyond what Zustand or Context provides for genuinely global concerns.

### Real-Time Strategy (Frontend)

- Supabase Realtime subscriptions are used for new message delivery and typing indicators.
- TanStack Query cache is updated on Realtime events, keeping the UI consistent.
- WebSocket reconnection is managed by the Supabase client SDK with exponential backoff.

### Routing

```
/                     → Redirect to /app or /login
/login                → Auth: Login
/register             → Auth: Registration
/verify-email         → Auth: Email verification
/app                  → Authenticated shell
  /app/messages       → Conversation list
  /app/messages/:id   → Active conversation
  /app/contacts       → Contacts / Buddy list
  /app/sms/new        → New SMS compose
  /app/credits        → Credit balance and top-up
  /app/settings       → Account settings
  /app/settings/privacy → Privacy controls
/admin                → Admin Dashboard (admin role required)
  /admin/users
  /admin/sms-logs
  /admin/config
  /admin/ai-metrics
```

---

## 5. Backend Architecture

### Technology
Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x (async), Supabase Python client, asyncio throughout.

### Module Structure

```
backend/
├── main.py                       # FastAPI app factory, lifespan
├── config.py                     # Settings via pydantic-settings (env vars)
├── database.py                   # Async SQLAlchemy engine, session factory
├── dependencies.py               # Shared FastAPI dependencies (auth, db session)
├── api/
│   └── v1/
│       ├── router.py             # Aggregate router for v1
│       ├── auth.py               # /api/v1/auth/*
│       ├── users.py              # /api/v1/users/*
│       ├── contacts.py           # /api/v1/contacts/*
│       ├── conversations.py      # /api/v1/conversations/*
│       ├── messages.py           # /api/v1/messages/*
│       ├── sms.py                # /api/v1/sms/*
│       ├── webhooks.py           # /api/v1/webhooks/* (inbound SMS, delivery status)
│       ├── ai.py                 # /api/v1/ai/*
│       ├── credits.py            # /api/v1/credits/*
│       ├── notifications.py      # /api/v1/notifications/*
│       └── admin.py              # /api/v1/admin/*
├── services/
│   ├── auth_service.py
│   ├── user_service.py
│   ├── contact_service.py
│   ├── conversation_service.py
│   ├── message_service.py
│   ├── sms_service.py
│   ├── ai_service.py
│   ├── credit_service.py
│   ├── notification_service.py
│   └── admin_service.py
├── repositories/
│   ├── user_repository.py
│   ├── contact_repository.py
│   ├── conversation_repository.py
│   ├── message_repository.py
│   ├── sms_repository.py
│   └── credit_repository.py
├── providers/
│   ├── sms/
│   │   ├── base.py               # SmsProvider ABC
│   │   ├── mock_provider.py      # MockSmsProvider
│   │   └── twilio_provider.py    # TwilioSmsProvider
│   └── ai/
│       ├── base.py               # AiProvider ABC
│       └── bedrock_provider.py   # BedrockAiProvider
├── models/
│   ├── db/                       # SQLAlchemy ORM models
│   └── schemas/                  # Pydantic request/response schemas
├── tasks/                        # Background tasks (SMS retry, AI calls)
├── middleware/
│   ├── request_id.py             # Injects X-Request-ID
│   ├── logging.py                # Structured request logging
│   └── rate_limit.py             # Rate limiting middleware
└── utils/
    ├── phone.py                  # E.164 validation, masking
    ├── sms_segments.py           # Segment count calculation
    └── idempotency.py            # Idempotency key management
```

### Request Lifecycle

```
HTTP Request
    ↓
Middleware Stack (request ID, logging, rate limit, CORS)
    ↓
Route Handler (auth dependency → validates JWT → injects current user)
    ↓
Route Handler (calls service method with validated Pydantic input)
    ↓
Service Layer (business logic, orchestration)
    ↓
Repository Layer (async SQLAlchemy queries)
    ↓
Supabase PostgreSQL
    ↓
Service Layer (maps DB result to schema)
    ↓
Route Handler (returns Pydantic response model)
    ↓
HTTP Response (consistent JSON structure)
```

### WebSocket Handling

WebSocket connections for real-time messaging are managed through **Supabase Realtime** on the frontend, subscribing directly to PostgreSQL changes via Supabase's realtime publication. This removes the need for a custom WebSocket server in Phase 1.

For typing indicators (ephemeral, not persisted), the frontend uses Supabase Realtime broadcast channels.

In Phase 2+, if Supabase Realtime throughput proves insufficient, a custom FastAPI WebSocket endpoint (`/ws/conversations/{id}`) will be introduced with Redis pub/sub for cross-instance message fan-out.

---

## 6. SMS Subsystem Architecture

```
User Request (compose SMS)
    ↓
POST /api/v1/sms/send
    ↓
SmsService.send_message()
    ├── Validate phone number (E.164)
    ├── Check country capability config
    ├── Check user credit balance
    ├── Create OutboundMessage record (status: pending)
    ├── Deduct credits (status: reserved)
    ├── Generate idempotency key
    ↓
SmsProvider.send_message() [MockSmsProvider | TwilioSmsProvider]
    ↓
Provider Response
    ├── Success → Update record (status: accepted, provider_id: xxx)
    │           → Confirm credit deduction
    └── Failure → Update record (status: failed)
               → Refund reserved credits
               → Schedule retry (if eligible)
               → Notify user if permanently failed

Delivery Status Callback (webhook)
    ↓
POST /api/v1/webhooks/sms/status
    ├── Validate webhook signature
    ├── Parse provider event
    ├── Update OutboundMessage.status
    └── Notify user via Supabase Realtime

Inbound SMS (webhook)
    ↓
POST /api/v1/webhooks/sms/inbound
    ├── Validate webhook signature
    ├── Match sender to conversation
    ├── Create InboundMessage record
    └── Push to Supabase Realtime → Frontend
```

---

## 7. AI Subsystem Architecture

```
User Request (AI feature)
    ↓
POST /api/v1/ai/{feature}
    ↓
AiService.{feature}()
    ├── Validate input
    ├── Build prompt (static system prompt + structured user data)
    ├── Call AiProvider.{method}()
    │       ↓
    │   BedrockAiProvider
    │       ├── Construct Bedrock API request
    │       ├── Call AWS Bedrock endpoint
    │       └── Parse response
    ├── Log metadata (model, tokens, latency — NOT message content)
    └── Return suggestion to route handler

Route Handler
    └── Return suggestion to frontend
        Frontend displays in review panel
        User edits / accepts / dismisses
        User explicitly sends (separate action)
```

---

## 8. Authentication and Authorisation

### Authentication
- Supabase Auth manages all authentication (JWT issuance, refresh, social OAuth).
- The FastAPI backend validates Supabase JWTs on every authenticated request using the Supabase JWT secret.
- The frontend uses the Supabase JS client for auth state management and token storage.
- Tokens are stored in memory/session storage, never `localStorage` for the access token.

### Authorisation
- Row Level Security (RLS) policies in Supabase PostgreSQL enforce data access at the database level.
- The FastAPI service layer additionally enforces ownership checks before mutations.
- Admin routes require a `role = 'admin'` claim in the JWT (set via Supabase user metadata or custom claims).

### JWT Flow

```
Browser → Supabase Auth (login) → JWT (access + refresh tokens)
Browser → FastAPI (request + Bearer JWT)
FastAPI → Verify JWT signature with Supabase public key
FastAPI → Extract user_id and role from claims
FastAPI → Proceed with authorised request
```

---

## 9. Data Flow: Internet-to-SMS Message

```
1. User opens /app/sms/new
2. User enters recipient phone number
   → Frontend: validates E.164 format
   → Frontend: POST /api/v1/sms/capability?country=PH
   → Backend returns: outbound_enabled, inbound_enabled, credit_cost_per_segment
3. User types message body
   → Frontend: calculates segment count and credit cost in real time (no API call)
4. User clicks Send
   → Frontend: POST /api/v1/sms/send { to, body, idempotency_key }
   → Backend: validates, checks credits, calls SmsProvider
   → Backend: returns { message_id, status: "accepted" }
   → Frontend: shows status "Queued"
5. Provider sends delivery callback
   → POST /api/v1/webhooks/sms/status { provider_id, status: "delivered" }
   → Backend: updates OutboundMessage, publishes Realtime event
   → Frontend: updates message status in real time
```

---

## 10. Environment Configuration

All environments use the same configuration structure. Values differ per environment.

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend service role key (never in frontend) |
| `SUPABASE_JWT_SECRET` | For JWT validation in FastAPI |
| `VITE_SUPABASE_URL` | Frontend Supabase URL |
| `VITE_SUPABASE_ANON_KEY` | Frontend Supabase anon key |
| `VITE_API_BASE_URL` | Backend API URL |
| `SMS_PROVIDER_MODE` | `mock` or `live` |
| `TWILIO_ACCOUNT_SID` | Twilio account SID (backend only) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token (backend only) |
| `TWILIO_WEBHOOK_SECRET` | Twilio webhook signing secret (backend only) |
| `AWS_REGION` | AWS region for Bedrock |
| `AWS_ACCESS_KEY_ID` | AWS credentials (backend only) |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials (backend only) |
| `BEDROCK_MODEL_ID` | Model identifier for AI calls |
| `LOG_LEVEL` | Structured log level |
| `RATE_LIMIT_LOGIN` | Login attempts per window |

---

## 11. Cross-Cutting Concerns

### Request Tracing
Every request is assigned a `X-Request-ID` header (UUID). This ID is propagated through all log lines and included in all API responses, enabling end-to-end tracing of any request across logs.

### Structured Logging
All backend logs are emitted as JSON with: `timestamp`, `level`, `request_id`, `user_id` (masked where sensitive), `service`, `message`, `duration_ms`.

### Error Response Structure
All API errors follow:
```json
{
  "error": {
    "code": "INSUFFICIENT_CREDITS",
    "message": "You do not have enough credits to send this message.",
    "details": { "required": 2, "available": 1 }
  },
  "request_id": "uuid"
}
```

### Feature Flags
SMS mode (`mock` / `live`) is the primary runtime feature flag. It is read from the environment variable `SMS_PROVIDER_MODE` and validated at startup. Additional feature flags will be managed through the admin configuration table in the database.

---

## 12. Architectural Decisions Log (ADL)

| ID | Decision | Rationale | Date |
|---|---|---|---|
| ADL-001 | Modular monolith over microservices | Simpler to build, test, and operate at this scale | Nov 2026 |
| ADL-002 | Supabase Realtime for Phase 1 WebSocket | Eliminates custom WS server; acceptable for early scale | Nov 2026 |
| ADL-003 | Provider abstraction for SMS and AI | Enables provider swap without feature code changes | Nov 2026 |
| ADL-004 | Backend-proxied AI calls | Security: prevents credential exposure in frontend | Nov 2026 |
| ADL-005 | FastAPI layered architecture (handler → service → repo → provider) | Testability, separation of concerns, maintainability | Nov 2026 |
| ADL-006 | Supabase RLS as primary authorisation layer | Database-level enforcement; survives any bypass of application logic | Nov 2026 |
| ADL-007 | Async SQLAlchemy throughout backend | Non-blocking I/O; required for FastAPI async handlers | Nov 2026 |
| ADL-008 | Deferred custom WS server to Phase 2+ | Premature optimisation; Supabase Realtime is sufficient for Phase 1 | Nov 2026 |

---

## 13. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

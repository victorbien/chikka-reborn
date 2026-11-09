# Application Architecture

**Document:** CHKR-ARCH-002  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document describes the internal application architecture of Chikka Reborn — the layers, modules, data flow patterns, and cross-cutting concerns that apply across both the frontend and backend. It bridges the high-level system architecture (`docs/architecture/system-architecture.md`) with the component-level details in the frontend and backend architecture documents.

## Scope

Both tiers (frontend and backend). All phases.

---

## 1. Layered Architecture Overview

```mermaid
graph TB
    subgraph "Frontend - React SPA"
        UI[UI Layer\nReact Components\nshadcn/ui + Tailwind]
        FM[Feature Modules\nauth / contacts / messaging\nsms / ai / admin ...]
        SVC_F[Frontend Services\nAPI Client\nSupabase Client\nWebSocket Manager]
        STATE[State Layer\nTanStack Query\nReact Context / Zustand]
    end

    subgraph "Backend - FastAPI"
        ROUTES[HTTP Layer\nRoute Handlers\nPydantic I/O]
        SERVICES[Service Layer\nBusiness Logic\nOrchestration]
        REPOS[Repository Layer\nSQLAlchemy Async\nDB Queries]
        PROVIDERS[Provider Layer\nSmsProvider\nAiProvider]
    end

    subgraph "Data + External"
        DB[(Supabase PostgreSQL)]
        AUTH_SVC[Supabase Auth]
        RT[Supabase Realtime]
        SMS_P[SMS Provider\nMock or Twilio]
        AI_P[AI Provider\nAmazon Bedrock]
    end

    UI --> FM
    FM --> STATE
    FM --> SVC_F
    SVC_F --> ROUTES
    SVC_F --> RT
    SVC_F --> AUTH_SVC

    ROUTES --> SERVICES
    SERVICES --> REPOS
    SERVICES --> PROVIDERS
    REPOS --> DB
    PROVIDERS --> SMS_P
    PROVIDERS --> AI_P
```

---

## 2. Module Boundaries

Both tiers are organised as a **modular monolith**: one deployable unit per tier, with internal module boundaries enforced by directory structure.

### Frontend Modules

Each feature module in `frontend/src/features/` owns its own:
- UI components
- Custom hooks
- API call functions
- Local types

No module may import from another module's internal files. Shared code lives in `frontend/src/lib/` or `frontend/src/components/`.

### Backend Modules

Each domain in `backend/api/v1/` owns its route handler file. Business logic lives in `backend/services/`. Database access in `backend/repositories/`. External service calls in `backend/providers/`.

**Dependency direction:** Routes → Services → Repositories → Database. Routes → Services → Providers → External. No layer skips another.

---

## 3. Request-Response Lifecycle (Backend)

```mermaid
sequenceDiagram
    participant C as Client (Browser)
    participant MW as Middleware Stack
    participant R as Route Handler
    participant S as Service Layer
    participant RP as Repository
    participant DB as Supabase PostgreSQL

    C->>MW: HTTP Request + Bearer JWT
    MW->>MW: Assign X-Request-ID
    MW->>MW: Log request (masked PII)
    MW->>MW: Check rate limit
    MW->>R: Pass to route handler
    R->>R: Validate JWT (Supabase public key)
    R->>R: Parse + validate request body (Pydantic)
    R->>S: Call service method(user, validated_input)
    S->>RP: Query / mutation
    RP->>DB: Async SQL via SQLAlchemy
    DB-->>RP: Result set
    RP-->>S: Domain objects
    S-->>R: Response schema
    R-->>C: JSON response + request_id
```

---

## 4. Real-Time Message Delivery (Phase 1)

```mermaid
sequenceDiagram
    participant SA as Sender Browser
    participant API as FastAPI Backend
    participant DB as Supabase PostgreSQL
    participant RT as Supabase Realtime
    participant RA as Recipient Browser

    SA->>API: POST /api/v1/messages {body}
    API->>DB: INSERT INTO messages
    DB-->>API: New message row
    API-->>SA: 201 {message_id, status: sent}
    DB->>RT: Postgres NOTIFY (realtime publication)
    RT->>RA: WebSocket push: new message event
    RA->>RA: Update TanStack Query cache
    RA->>API: PATCH message status = delivered
    API->>DB: UPDATE messages SET status = delivered
    DB->>RT: Postgres NOTIFY
    RT->>SA: status update event
    SA->>SA: Update message status in UI
```

---

## 5. Authentication Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant SA as Supabase Auth
    participant API as FastAPI Backend
    participant DB as Supabase PostgreSQL

    B->>SA: POST /auth/v1/token (email + password)
    SA-->>B: access_token (JWT) + refresh_token
    B->>API: GET /api/v1/users/me\n Authorization: Bearer <access_token>
    API->>API: Decode + verify JWT\n(Supabase JWT secret)
    API->>API: Extract user_id, role from claims
    API->>DB: SELECT * FROM profiles WHERE id = user_id\n(RLS: id = auth.uid())
    DB-->>API: Profile row
    API-->>B: 200 {profile}
```

---

## 6. Error Handling Architecture

All errors follow a consistent structure regardless of where they originate.

### Error Response Schema (all environments)
```json
{
  "error": {
    "code": "INSUFFICIENT_CREDITS",
    "message": "You do not have enough credits to send this message.",
    "details": {
      "required": 2,
      "available": 1
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Error Handling Rules
- Route handlers never catch generic exceptions — they let a global exception handler produce the consistent structure.
- Services raise typed exceptions (e.g. `InsufficientCreditsError`, `PhoneNotVerifiedError`).
- The global exception handler maps typed exceptions to error codes and HTTP status codes.
- Stack traces never appear in API responses. They are logged server-side with the `request_id`.
- Provider errors (SMS, AI, DB) are wrapped in typed exceptions before propagating up.

---

## 7. Background Tasks

Long-running or non-blocking operations that must not delay the API response:

| Task | Trigger | Mechanism |
|---|---|---|
| SMS retry | Provider transient failure | FastAPI `BackgroundTasks` + scheduled retry |
| SMS delivery status poll | For providers without webhooks | Periodic background task |
| AI inference (Phase 3) | User AI request | FastAPI `BackgroundTasks` or async task |
| Data export generation | User export request | Background task, result to Storage |
| Notification delivery | New message, SMS status change | Triggered from service layer, non-blocking |

Phase 2+ may introduce a lightweight task queue (e.g. ARQ or Celery) if background task volume warrants it. This is an architectural decision pending evaluation — see ADL-009 in `docs/architecture/architecture-decisions.md`.

---

## 8. Feature Flag Architecture

The primary runtime feature flag is `SMS_PROVIDER_MODE` (`mock` | `live`).

Additional feature flags will be stored in a `platform_config` database table, editable via the admin dashboard without a code deploy. This allows:
- Enabling/disabling AI features per environment.
- Enabling/disabling browser push notifications.
- Toggling Classic Mode availability.

Feature flags are loaded at application startup and cached. Changes via admin dashboard invalidate the cache.

---

## 9. Cross-Cutting Concerns

| Concern | Implementation |
|---|---|
| Request tracing | `X-Request-ID` UUID assigned by middleware; propagated to all log lines and responses |
| Structured logging | JSON logs: `{timestamp, level, request_id, user_id, service, message, duration_ms}` |
| Rate limiting | Per-route middleware; limits defined in NFR-SEC-006 |
| CORS | Backend allows only configured frontend origins; wildcard never used in production |
| PII masking | Phone numbers masked in logs: country code + last 4 digits |
| Idempotency | SMS send operations carry client-generated idempotency keys |

---

## 10. Inter-Module Dependency Map

```
AUTH ──────────────────────────────────────┐
  │                                        │
  ├──▶ CONTACTS                            │
  │       └──▶ MSG (open conversation)     │
  │       └──▶ SMS (add SMS contact)       │
  │                                        │
  ├──▶ CREDIT ◀── SMS (deduction/refund)   │
  │                                        │
  ├──▶ NOTIF ◀── MSG, SMS (trigger notifs) │
  │                                        │
  ├──▶ PRIVACY                             │
  │                                        │
  └──▶ ADMIN ──▶ all modules (read/config) │
                                           │
AI ──▶ MSG, SMS (suggestions only) ────────┘
```

No circular dependencies. ADMIN has read access to all modules. AI is a pure suggestion layer — it does not write to conversations or trigger sends.

---

## 11. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

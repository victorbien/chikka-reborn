# System Architecture

**Document:** CHKR-ARCH-001  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document defines the top-level system architecture of Chikka Reborn. It describes the external actors, system boundaries, deployment topology, and the interaction patterns between all major components.

## Scope

Covers all environments (development, staging, production) and all phases. Phase-specific variations are noted inline.

---

## 1. Architectural Style

Chikka Reborn follows a **three-tier modular monolith** architecture:

| Tier | Component | Host |
|---|---|---|
| Presentation | React SPA | Vercel CDN |
| Application | FastAPI backend | Render / Railway / Fly.io (OD-003) |
| Data | Supabase PostgreSQL | Supabase managed cloud |

**Why modular monolith?**  
Microservices introduce distributed systems complexity — inter-service auth, distributed tracing, deployment choreography — that is not justified at this scale. A well-structured monolith is faster to build, easier to test, and simpler to operate. Module boundaries are enforced by directory structure and import rules, not process boundaries. Individual modules can be extracted into services in future if specific scaling requirements emerge.

---

## 2. System Context Diagram

```mermaid
C4Context
    title Chikka Reborn — System Context

    Person(internet_user, "Internet User", "Registered Chikka user on web browser")
    Person(phone_user, "Basic Phone User", "Mobile phone with SMS only, no internet required")
    Person(admin, "Administrator", "Platform operator with admin access")

    System(chikka, "Chikka Reborn", "Web messaging platform connecting internet users with SMS users, with real-time messaging and AI assistance")

    System_Ext(twilio, "Twilio SMS", "SMS provider — sends and receives SMS via carrier network")
    System_Ext(carrier, "Mobile Carrier Network", "Delivers SMS to handsets")
    System_Ext(bedrock, "Amazon Bedrock", "AI model inference — Claude 3 or equivalent")
    System_Ext(supabase_auth, "Supabase Auth", "JWT-based authentication and OAuth")
    System_Ext(google_oauth, "Google OAuth", "Social login provider")
    System_Ext(github_oauth, "GitHub OAuth", "Social login provider")

    Rel(internet_user, chikka, "Sends messages, manages contacts, uses AI features", "HTTPS / WSS")
    Rel(phone_user, carrier, "Sends and receives SMS", "GSM / carrier network")
    Rel(admin, chikka, "Manages platform via admin dashboard", "HTTPS")
    Rel(chikka, twilio, "Sends outbound SMS, receives delivery callbacks and inbound SMS", "HTTPS webhooks")
    Rel(twilio, carrier, "Routes SMS to/from mobile networks", "Carrier interconnect")
    Rel(carrier, phone_user, "Delivers SMS to handset", "GSM")
    Rel(chikka, bedrock, "Invokes AI model inference for assistant features", "HTTPS / AWS SDK")
    Rel(chikka, supabase_auth, "Authenticates users, issues JWTs", "HTTPS")
    Rel(supabase_auth, google_oauth, "Delegates OAuth", "HTTPS")
    Rel(supabase_auth, github_oauth, "Delegates OAuth", "HTTPS")
```

---

## 3. Container Diagram

```mermaid
C4Container
    title Chikka Reborn — Containers

    Person(user, "Internet User / Admin")

    Container(spa, "React SPA", "React 18, TypeScript, Vite", "Single-page application served from Vercel CDN")
    Container(api, "FastAPI Backend", "Python 3.12, FastAPI, SQLAlchemy", "REST API + WebSocket gateway. Stateless. Horizontally scalable.")
    Container(db, "Supabase PostgreSQL", "PostgreSQL 15", "Primary relational database with RLS")
    Container(auth, "Supabase Auth", "Supabase managed service", "JWT issuance, OAuth flows, session management")
    Container(realtime, "Supabase Realtime", "Supabase managed WebSocket", "Real-time message push to frontend clients")
    Container(storage, "Supabase Storage", "S3-compatible object store", "Profile avatars, data export archives")

    System_Ext(twilio, "Twilio SMS")
    System_Ext(bedrock, "Amazon Bedrock")

    Rel(user, spa, "Uses", "HTTPS")
    Rel(spa, api, "API calls", "HTTPS / JSON")
    Rel(spa, auth, "Login, token refresh", "HTTPS")
    Rel(spa, realtime, "Real-time message subscriptions", "WSS")
    Rel(spa, storage, "Avatar upload/download", "HTTPS")
    Rel(api, db, "Read/write via SQLAlchemy async", "PostgreSQL wire protocol / TLS")
    Rel(api, auth, "Validate JWT tokens", "HTTPS")
    Rel(api, twilio, "Send SMS, validate webhooks", "HTTPS")
    Rel(api, bedrock, "AI inference requests", "HTTPS / AWS SDK")
    Rel(twilio, api, "Inbound SMS + delivery callbacks", "HTTPS webhooks")
```

---

## 4. Deployment Architecture

```mermaid
graph TB
    subgraph "User Devices"
        B[Browser / Mobile Browser]
        P[Basic Phone - SMS only]
    end

    subgraph "Vercel CDN - Global Edge"
        V[React SPA\nStatic Assets]
    end

    subgraph "Backend Hosting - TBD OD-003"
        API[FastAPI\nUvicorn ASGI\n2+ instances]
    end

    subgraph "Supabase Cloud"
        DB[(PostgreSQL)]
        AUTH[Auth Service]
        RT[Realtime WS]
        STORE[Storage]
    end

    subgraph "AWS"
        BEDROCK[Amazon Bedrock\nClaude 3 / equivalent]
    end

    subgraph "Twilio"
        SMS_OUT[Outbound SMS]
        SMS_IN[Inbound Webhook]
    end

    subgraph "Carrier Network"
        CARRIER[Mobile Carrier]
    end

    B -->|HTTPS| V
    B -->|HTTPS API| API
    B -->|WSS| RT
    P -->|SMS| CARRIER
    CARRIER -->|SMS deliver| P
    API -->|PostgreSQL TLS| DB
    API -->|JWT validate| AUTH
    API -->|HTTPS| BEDROCK
    API -->|HTTPS| SMS_OUT
    SMS_IN -->|HTTPS POST| API
    SMS_OUT --> CARRIER
    CARRIER --> P
```

---

## 5. Communication Patterns

| Pattern | Protocol | Direction | Notes |
|---|---|---|---|
| User ↔ Frontend | HTTPS | Bidirectional | Served from Vercel edge |
| Frontend → Backend API | HTTPS/JSON | Client → Server | JWT Bearer token on all auth routes |
| Frontend ↔ Supabase Realtime | WSS | Bidirectional | Real-time message delivery, typing indicators |
| Backend → Supabase DB | PostgreSQL/TLS | Server → DB | Async SQLAlchemy |
| Backend → Twilio | HTTPS | Server → Provider | Outbound SMS send |
| Twilio → Backend | HTTPS POST | Provider → Server | Delivery status + inbound SMS webhooks |
| Backend → Amazon Bedrock | HTTPS/AWS SDK | Server → Provider | AI inference |
| User → Supabase Auth | HTTPS | Client → Auth | Login, OAuth, token refresh |

---

## 6. SMS Architecture Summary

Two modes, never mixed:

| Aspect | Simulation Mode | Live Mode |
|---|---|---|
| Provider | `MockSmsProvider` | `TwilioSmsProvider` |
| Real messages sent | No | Yes |
| UI label | "SIMULATED" badge | Status per provider event |
| Credits consumed | No | Yes |
| Activation | Default | Requires operator approval + re-auth |
| Silent fallback to mock | **Never permitted** | N/A |

---

## 7. AI Architecture Summary

- All AI calls proxied through the FastAPI backend. Frontend never calls Bedrock directly.
- Provider abstraction: `BedrockAiProvider` implements `AiProvider` ABC.
- AI responses returned as suggestions. User must explicitly accept before message is sent.
- No auto-send path exists. This is a permanent architectural constraint.
- AI call failures degrade gracefully — core messaging is never blocked.

---

## 8. Security Boundary Summary

| Boundary | Enforcement |
|---|---|
| User data access | Supabase RLS on every table |
| API authentication | JWT validation on every protected route |
| Webhook integrity | Provider signature validation before processing |
| Secret management | Environment variables only; never in code or frontend bundles |
| Logging | PII masked; no message content in logs |

---

## 9. Scalability Path

| Phase | WebSocket Strategy | Scale Approach |
|---|---|---|
| 1 | Supabase Realtime | Suitable for < ~1,000 concurrent users |
| 2+ | Evaluate Supabase limits | Upgrade plan or add custom WS layer |
| Future | FastAPI WebSocket + Redis pub/sub | Multi-instance horizontal scale |

The architecture is designed so that swapping from Supabase Realtime to a custom WebSocket layer requires changes only to the frontend subscription code and a new backend WebSocket endpoint — no changes to the message data model.

---

## 10. Architectural Decisions Index

All architectural decisions are recorded in `docs/architecture/architecture-decisions.md`.

Key decisions affecting this document:

| ADL ID | Decision |
|---|---|
| ADL-001 | Modular monolith over microservices |
| ADL-002 | Supabase Realtime for Phase 1 WebSocket |
| ADL-003 | Provider abstraction for SMS and AI |
| ADL-004 | Backend-proxied AI calls |
| ADL-006 | Supabase RLS as primary authorisation layer |

---

## 11. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft with Mermaid diagrams |

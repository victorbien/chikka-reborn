# Chikka Reborn 💬

**The Messenger That Refused to Die.**

> A Kiroween 2026 project — RESURRECTION category.

---

## What is Chikka Reborn?

Chikka was a pioneering Filipino messaging platform that bridged the gap between internet users and ordinary mobile phone users through SMS. It let anyone with a computer send messages to mobile phones — even to people who had never installed Chikka. The service was discontinued in 2018.

**Chikka Reborn** revives that original concept as a modern, globally accessible messaging platform, enhanced with real-time communication, artificial intelligence, and multilingual support.

> This is an independent, Chikka-inspired project. It is not an official relaunch of the original Chikka service and is not affiliated with or endorsed by the original owners or their telecom partners.

---

## Core Principles

> "Everyone should be able to communicate, whether they have a smartphone, an internet connection, or just a basic mobile phone."

- Internet users can message SMS users.
- SMS users can reply back through the platform.
- Chikka users can message each other in real time.
- AI assistance makes communication easier across languages and contexts.
- The platform works globally, with special attention to Philippine SMS requirements.

---

## Features

| Module | Description |
|---|---|
| Authentication & User Management | Secure sign-up, login, profile management |
| Contacts & Buddy List | Add, manage, and organise contacts |
| Real-Time Chikka-to-Chikka Messaging | Instant messaging between platform users |
| Internet-to-SMS Messaging | Send messages from the web to any mobile phone |
| SMS-to-Internet Messaging | Receive replies from SMS users on the platform |
| AI-Powered Chikka Assistant | Smart replies, translation, rewriting, summarisation |
| Notifications | Real-time push and in-app notifications |
| SMS Credits & Cost Management | Credit balance, usage tracking, top-up |
| Privacy & Security | End-to-end controls, data protection, consent |
| Administration Dashboard | Platform management, monitoring, audit logs |
| Classic & Modern Mode | Nostalgic Chikka UI or modern chat interface |

---

## Technology Stack

### Frontend
- React + TypeScript
- Vite
- Tailwind CSS + shadcn/ui
- React Router
- TanStack Query
- React Hook Form + Zod

### Backend
- Python + FastAPI
- Pydantic
- SQLAlchemy
- REST APIs + WebSockets

### Database & Auth
- Supabase PostgreSQL
- Supabase Auth
- Supabase Realtime
- Supabase Row Level Security

### AI
- Amazon Bedrock
- Model/provider abstraction layer

### SMS
- Provider-independent gateway interface
- MockSmsProvider (simulation mode)
- TwilioSmsProvider (live mode)
- Inbound webhooks, delivery callbacks, retry logic

### Testing
- Pytest (backend)
- Playwright (end-to-end)
- React Testing Library (frontend)

### Deployment
- Vercel (frontend)
- Render / Railway / Fly.io (FastAPI backend)
- Supabase (database and auth)

---

## Project Structure

```
chikka-reborn/
├── README.md
├── docs/
│   ├── prd.md                        # Product Requirements Document
│   ├── frs.md                        # Functional Requirements Specification
│   ├── nfrs.md                       # Non-Functional Requirements Specification
│   ├── architecture.md               # System Architecture
│   ├── database-design.md            # Database Design
│   ├── api-design.md                 # API Design
│   ├── testing-strategy.md           # Testing Strategy
│   ├── deployment-strategy.md        # Deployment Strategy
│   ├── roadmap.md                    # Feature Development Roadmap
│   └── risks-and-dependencies.md     # Risks and Technical Dependencies
├── .kiro/
│   └── steering/
│       ├── project-overview.md       # Project context for Kiro
│       ├── development-principles.md # Coding and architecture standards
│       ├── sms-guidelines.md         # SMS implementation rules
│       └── ai-guidelines.md         # AI feature rules
├── frontend/                         # React application (app shell + design system)
├── backend/                          # FastAPI application (foundation)
└── supabase/                         # Migrations, seed, SQL tests, database tools
```

---

## Development Phases

| Phase | Name | Focus |
|---|---|---|
| 0 | Foundation | Documentation, architecture, project setup |
| 1 | Core Platform | Auth, profiles, Chikka-to-Chikka messaging |
| 2 | SMS Integration | Internet-to-SMS, SMS-to-Internet, simulation mode |
| 3 | AI Features | Smart replies, translation, rewriting, summaries |
| 4 | Credits & Admin | Billing, cost management, admin dashboard |
| 5 | Classic Mode & Polish | Nostalgic UI, accessibility, internationalisation |
| 6 | Production Hardening | Security audit, load testing, deployment |

---

## SMS Modes

### Simulation Mode
Uses `MockSmsProvider`. No real SMS is sent. All simulated messages are clearly labelled. Supports error and retry scenarios. No cost incurred.

### Live Mode
Uses a real configured provider (e.g. Twilio). Real messages are sent and received. Webhook signatures are validated. Delivery status is tracked per provider event, not by acceptance alone.

> The application never claims a message was delivered merely because the provider accepted it.

---

## AI Assistant

The AI assistant (powered by Amazon Bedrock) supports smart replies, translation, tone adjustment, rewriting, conversation summaries, and SMS length optimisation.

**AI-generated content must always be reviewed and approved by the user before sending. The AI assistant never transmits a message automatically.**

---

## Getting Started

> Built so far: the foundation (FastAPI backend, React app shell, design system, database schema) and **Module A, authentication and user management**: registration, email verification, sign-in with lockout, sign-out, password reset, sessions, profile setup and editing, profile photo, presence, mobile number verification (simulation) and account deletion. Also built: **Module B, contacts and buddy list**: discovery, requests, groups, favourites, blocking, presence display and recent activity (SMS contacts come with Phase 2). See [docs/api/contacts-api.md](docs/api/contacts-api.md). And **Module C, real-time Chikka messaging**: conversations, history, delivery state, unread counts, search, emoji, attachments and archive over REST, with live updates through a WebSocket gateway at `/ws/v1` (one backend instance; see [docs/api/messaging-api.md](docs/api/messaging-api.md) and [docs/api/realtime-api.md](docs/api/realtime-api.md)). See [docs/api/authentication-api.md](docs/api/authentication-api.md) and the implementation status in [docs/product/frs/module-a-auth.md](docs/product/frs/module-a-auth.md).

See [docs/roadmap.md](docs/roadmap.md) for the planned development sequence.

### Quick start (Windows PowerShell)

```powershell
scripts\setup.ps1            # venv, dependencies, copies .env.example files
scripts\dev-backend.ps1      # http://localhost:8000  (docs at /docs)
scripts\dev-frontend.ps1     # http://localhost:5173  (second terminal)
scripts\check.ps1            # lint, format, types, tests, build for both apps
scripts\e2e-local.ps1        # real processes end to end: PGlite, fake Supabase, API, frontend client
```

Sign-in needs Supabase Auth: set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` (only for projects on the legacy HS256 secret; signing-key projects are verified through their JWKS) (and `SUPABASE_SERVICE_ROLE_KEY` for photos and account deletion) in `backend/.env`, and use the email templates in `supabase/templates/` so links come back to the app. Mobile verification runs in simulation: no text message is sent and the code appears in a panel labelled SIMULATED.

Full guide: [docs/deployment/local-development.md](docs/deployment/local-development.md). Per-app guides: [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md).

### Environment variables

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`. Everything is optional for a first start. Reference: [docs/deployment/environment-configuration.md](docs/deployment/environment-configuration.md). SMS defaults to `SMS_PROVIDER_MODE=mock` (simulation); `live` is refused unless `SMS_LIVE_CONFIRMED=true`.

### Frontend

Requires Node.js 22.19+ (Vite 8 and Vitest 5 declare this; 22.17 builds and tests pass but npm warns).

```powershell
cd frontend
npm ci
npm run dev         # http://localhost:5173
npm run lint
npm run test        # vitest --run
npm run build       # tsc --noEmit + vite build
```

The selected display mode is stored in `localStorage` (`chikka.displayMode`). The frontend holds no provider credentials; only `VITE_`-prefixed public values.

### Backend

Requires Python 3.12.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
.\.venv\Scripts\python.exe -m pytest
```
### Database (no Docker needed for a quick check)

Requires Node.js 20+. This applies all migrations, the development seed and the SQL tests to a throwaway in-process PostgreSQL. It sends nothing anywhere.

```powershell
cd supabase\tools
npm ci
npm test            # migrations + SQL tests
npm run seed        # migrations + fictional development data
```

For local Supabase, hosted staging and production steps, see [docs/database/database-setup-guide.md](docs/database/database-setup-guide.md). Simulation is the default SMS mode; nothing in the database setup enables live sending.

---

## Documentation Index

Canonical documentation lives in these folders:

| Area | Path |
|---|---|
| Product (vision, requirements, features, roadmap) | [docs/product/](docs/product/) |
| Architecture and decisions | [docs/architecture/](docs/architecture/) |
| UI/UX and screens | [docs/design/](docs/design/) |
| API reference | [docs/api/](docs/api/) |
| Database, migrations, RLS | [docs/database/](docs/database/) |
| Quality and testing | [docs/quality/](docs/quality/) |
| Deployment and operations | [docs/deployment/](docs/deployment/) |
| Project management (risks, backlog, decision log) | [docs/project-management/](docs/project-management/) |

The ten older single-file documents directly under `docs/` (`prd.md`, `frs.md`, and so on) are marked SUPERSEDED and kept for history only.

---

## Kiroween 2026

This project was built as part of **Kiroween 2026** under the **RESURRECTION** category — bringing back something that was lost, reimagined for today.

---

*Chikka Reborn is an independent project inspired by the original Chikka service. All original Chikka branding, trademarks, and intellectual property belong to their respective owners.*

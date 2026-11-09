---
inclusion: always
---

# Chikka Reborn — Project Overview

## What This Project Is

Chikka Reborn is a modern revival of the original Chikka messaging platform — a pioneering Filipino service that connected internet users with mobile phone users via SMS. The original service was discontinued in 2018.

This project is built for **Kiroween 2026** under the **RESURRECTION** category.

> This is an independent, Chikka-inspired project. It is not an official relaunch. It is not affiliated with or endorsed by the original owners or their telecom partners. Use original branding and assets unless necessary IP permissions have been obtained.

## Central Product Principle

> "Everyone should be able to communicate, whether they have a smartphone, an internet connection, or just a basic mobile phone."

## Core Capabilities

1. Internet-to-SMS messaging — send messages from a web browser to any mobile phone.
2. SMS-to-Internet messaging — SMS users can reply and interact through the platform.
3. Real-time Chikka-to-Chikka messaging — instant messaging between registered platform users.
4. AI-assisted communication — smart replies, translation, rewriting, tone adjustment, summarisation.
5. Multilingual communication support.
6. International messaging with country-aware capability handling.
7. Secure account and contact management.

## Modules

| ID | Module |
|---|---|
| A | Authentication and User Management |
| B | Contacts and Buddy List |
| C | Real-Time Chikka-to-Chikka Messaging |
| D | Internet-to-SMS Messaging |
| E | SMS-to-Internet Messaging |
| F | AI-Powered Chikka Assistant |
| G | Notifications |
| H | SMS Credits and Cost Management |
| I | Privacy and Security |
| J | Administration Dashboard |
| K | Classic Chikka Mode and Modern Mode |

## Technology Stack

### Frontend
- React, TypeScript, Vite
- Tailwind CSS, shadcn/ui
- React Router, TanStack Query
- React Hook Form, Zod

### Backend
- Python, FastAPI, Pydantic
- SQLAlchemy
- REST + WebSockets

### Database & Auth
- Supabase PostgreSQL
- Supabase Auth, Realtime, RLS, Storage

### AI
- Amazon Bedrock (model/provider abstraction)

### SMS
- Provider-independent interface
- MockSmsProvider (simulation)
- TwilioSmsProvider (live)

### Testing
- Pytest, Playwright, React Testing Library

### Deployment
- Vercel (frontend), hosted environment (backend), Supabase (DB/auth)

## Repository Layout

```
chikka-reborn/
├── README.md
├── docs/               # All project documentation
├── .kiro/steering/     # Kiro context files (this directory)
├── frontend/           # React application
├── backend/            # FastAPI application
└── supabase/           # Migrations, seeds, RLS policies
```

## Development Phases

| Phase | Focus |
|---|---|
| 0 | Documentation, architecture, project setup |
| 1 | Auth, profiles, Chikka-to-Chikka messaging |
| 2 | Internet-to-SMS, SMS-to-Internet, simulation mode |
| 3 | AI features |
| 4 | Credits, billing, administration |
| 5 | Classic Mode, accessibility, i18n |
| 6 | Production hardening |

## Key Documentation

All detailed documentation is in `docs/`. Do not make architectural or product decisions that contradict those documents without reviewing and updating them first.

| Document | Path |
|---|---|
| Product Requirements | `docs/prd.md` |
| Functional Requirements | `docs/frs.md` |
| Non-Functional Requirements | `docs/nfrs.md` |
| Architecture | `docs/architecture.md` |
| Database Design | `docs/database-design.md` |
| API Design | `docs/api-design.md` |
| Testing Strategy | `docs/testing-strategy.md` |
| Deployment Strategy | `docs/deployment-strategy.md` |
| Roadmap | `docs/roadmap.md` |
| Risks & Dependencies | `docs/risks-and-dependencies.md` |

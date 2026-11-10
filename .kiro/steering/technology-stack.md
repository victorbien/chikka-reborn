---
inclusion: always
---

# Technology Stack

Rationale: `docs/architecture/architecture-decisions.md`. Local setup: `docs/deployment/local-development.md`.

## Approved Stack

| Area | Technology | Purpose |
|---|---|---|
| Frontend build | React, TypeScript, Vite | UI, strict typing, fast builds |
| Styling/UI | Tailwind CSS, shadcn/ui | Utility styling, accessible primitives |
| Routing | React Router | Client routing |
| Server state | TanStack Query | Fetching, caching, mutations |
| Forms | React Hook Form, Zod | Forms and schema validation |
| Backend | Python, FastAPI, Pydantic | Async REST/WebSocket API, validation |
| ORM | SQLAlchemy (async) | Database access via repositories |
| Database/Auth | Supabase PostgreSQL, Auth, Realtime, RLS, Storage | Data, identity, live updates, files |
| AI | Amazon Bedrock via abstraction layer | Assistant features |
| SMS | `SmsProvider` interface: MockSmsProvider (simulation), TwilioSmsProvider (live) | Messaging |
| Testing | Pytest, Playwright, React Testing Library | Backend, E2E, component tests |
| Deployment | Vercel (frontend), hosted backend, Supabase | Hosting |

## Approved Alternatives

- Another SMS provider is allowed if it implements `SmsProvider`.
- Another AI model is allowed behind `AiProvider` (configuration change only).
- Vitest is acceptable for frontend unit tests alongside React Testing Library.

## Restrictions

- No new libraries or frameworks without a documented reason (ADR or decision-log entry) and pinned versions.
- No Redux, CSS-in-JS, or other UI kits next to shadcn/ui.
- No microservices, message brokers, or extra datastores without an ADR.
- No vendor SDK imports outside `integrations/`.
- No raw SQL built from user input. Use parameterised queries.
- Prefer well-maintained packages; flag unusual or typosquat-like names.
- Secrets only via environment variables.

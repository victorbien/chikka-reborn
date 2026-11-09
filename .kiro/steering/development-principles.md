---
inclusion: always
---

# Chikka Reborn — Development Principles

These standards apply to all code written for this project. Follow them consistently.

## Architecture

- Use a **modular monolith** for both frontend and backend. Do not introduce microservices unless a specific, documented scaling or isolation requirement demands it.
- Separate concerns: frontend, backend, infrastructure, and database logic must not bleed into one another.
- Follow **SOLID principles** where the language and context make them appropriate.
- Prefer composition over inheritance.
- Design modules to be independently testable.

## Naming and Code Quality

- Use clear, intention-revealing names for variables, functions, classes, and files.
- Avoid abbreviations unless they are universally understood in the domain (e.g. `sms`, `api`, `id`).
- Apply consistent naming conventions per language:
  - Python: `snake_case` for variables and functions, `PascalCase` for classes.
  - TypeScript/React: `camelCase` for variables and functions, `PascalCase` for components and types.
- Keep functions small and focused on a single responsibility.
- Remove dead code. Do not comment out large blocks — delete them and rely on version control.

## Typing and Validation

- All Python functions must have full type annotations.
- All FastAPI endpoints must use Pydantic models for request bodies and response schemas.
- All TypeScript code must be strictly typed. Avoid `any`.
- All form inputs must be validated with Zod schemas before submission.
- Never trust data from external sources (webhooks, SMS providers, user input) without explicit validation.

## Security

- Apply **secure-by-default** practices.
- Use environment variables for all secrets, API keys, and provider credentials. Never hardcode them.
- Never expose provider credentials in frontend code.
- Use Supabase Row Level Security (RLS) for all data access policies.
- Sanitise all user-generated content before storing or rendering it.
- Use parameterised queries. Never construct SQL strings from user input.
- Validate and verify all webhook signatures before processing events.
- Use HTTPS everywhere.
- Apply rate limiting on authentication and SMS-sending endpoints.

## Error Handling

- All API endpoints must return consistent error response structures.
- Use structured error responses: `{ "error": { "code": "...", "message": "...", "details": {} } }`.
- Log errors with sufficient context for debugging (request ID, user ID where safe, timestamp, error type).
- Never leak stack traces or internal system details to API consumers.
- Handle network failures, provider failures, and database errors explicitly — do not let them silently fail.

## API Design

- All REST endpoints follow the conventions defined in `docs/api-design.md`.
- Use versioned API routes: `/api/v1/...`.
- Use HTTP methods semantically (GET reads, POST creates, PUT/PATCH updates, DELETE removes).
- Return appropriate HTTP status codes.
- Provide pagination for all list endpoints.
- Include a `request_id` in all responses for traceability.

## Frontend Standards

- Every user-facing state must be handled: loading, empty, success, error.
- Use TanStack Query for all server state. Do not store server data in component state.
- Use React Hook Form + Zod for all forms.
- Use shadcn/ui components as the base. Extend them — do not rebuild primitives.
- Components must be responsive: design mobile-first, verify on desktop.
- Follow WCAG 2.1 AA accessibility guidelines:
  - All interactive elements must be keyboard-navigable.
  - Use semantic HTML.
  - Provide `alt` text for all images.
  - Ensure sufficient colour contrast.
- Do not use inline styles. Use Tailwind utility classes.

## Backend Standards

- All FastAPI route handlers must be thin — delegate business logic to service layers.
- Use dependency injection for database sessions, authentication, and shared services.
- Use async/await throughout the FastAPI application.
- Never perform blocking I/O in async route handlers.
- Use background tasks or queues for non-blocking operations (e.g. sending SMS, AI calls).

## Database

- All schema changes must be managed as Supabase migrations.
- Never modify the database schema manually in production.
- Always define RLS policies alongside table creation.
- Use UUIDs as primary keys.
- Include `created_at` and `updated_at` timestamps on all tables.
- Soft-delete sensitive records where appropriate (add `deleted_at`).

## Testing

- Write tests alongside feature implementation — not as an afterthought.
- Follow the testing strategy defined in `docs/testing-strategy.md`.
- Maintain meaningful test coverage for business logic, API endpoints, and critical user flows.
- Tests must be deterministic. Do not write tests that depend on external services without mocking.

## What Not to Do

- Do not present placeholder functionality as fully implemented.
- Do not simulate SMS delivery and report it as real.
- Do not claim AI-generated content has been sent without user approval.
- Do not skip error handling to keep code shorter.
- Do not add features, abstractions, or complexity beyond what the current task requires.
- Do not introduce new libraries or frameworks without documenting the reason.
- Do not apply destructive database operations, production deployments, or real SMS campaigns without explicit human approval.

## Required Human Approval Before

- Destructive database operations (DROP, TRUNCATE, bulk DELETE).
- Schema changes applied to a production database.
- Deploying to a production environment.
- Sending real SMS messages to real phone numbers.
- Any action that incurs real financial cost.
- Removing or modifying authentication or authorisation controls.

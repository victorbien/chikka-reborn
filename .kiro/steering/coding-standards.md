---
inclusion: always
---

# Coding Standards

Complements `development-principles.md`. API details: `docs/api-design.md`, `docs/api/api-overview.md`.

## Naming

- Python: `snake_case` functions/variables/modules, `PascalCase` classes, `UPPER_SNAKE` constants.
- TypeScript: `camelCase` variables/functions, `PascalCase` components/types, `UPPER_SNAKE` constants.
- Frontend files: components `PascalCase.tsx`; hooks `useThing.ts`; other files `kebab-case.ts`.
- Names reveal intent. Avoid abbreviations except `sms`, `api`, `id`, `url`.

## Directories

```
backend/app/{core,integrations,modules/<name>,api}   backend/tests/{unit,integration}
frontend/src/{features/<name>,components/ui,components/shared,lib,hooks,routes}
supabase/{migrations,seed,policies}
```

Tests mirror source structure. Feature code stays inside its feature folder.

## Formatting and Linting

- Python: Ruff (lint + format), mypy strict on `app/`.
- TypeScript: ESLint, Prettier, `tsc --noEmit` with `strict: true`.
- Linters and type checks must pass before work is considered done. Do not disable rules without a justifying comment.
- Delete dead code; do not comment it out.

## TypeScript

- No `any`; use `unknown` and narrow. Derive types from Zod schemas (`z.infer`).
- Prefer function components, named exports, and explicit prop types.
- Validate all external data at the boundary.

## Python

- Full type annotations on every function. Pydantic models for all request/response bodies and settings.
- `async`/`await` throughout; no blocking I/O in handlers.
- Small single-purpose functions. Prefer composition over inheritance.

## Error Handling

- Raise typed domain exceptions in services; map them to HTTP errors in one central handler.
- Error shape: `{ "error": { "code": "...", "message": "...", "details": {} }, "request_id": "..." }`.
- Never leak stack traces or internals. Never swallow exceptions silently; log with request ID and error type.
- Frontend: handle every failure path with a user-readable message.

## API Conventions

- Routes under `/api/v1/`, plural nouns, semantic HTTP methods and status codes.
- Paginate every list endpoint. Include `request_id` in all responses.
- Mutations that send SMS require an idempotency key.

## Reusable Components

- Extend shadcn/ui; do not rebuild primitives.
- Extract a shared component when used by two or more features. Components are typed, accessible, responsive, and take data via props.
- Shared status UI (delivery badge, SIMULATED label, AI-assisted badge) exists once and is reused everywhere.

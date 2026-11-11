# Chikka Reborn frontend

React, TypeScript and Vite. Implemented: app shell, shared component library, and Module A screens (register, sign in, forgot and reset password, email verification, profile setup, profile settings with photo, status, mobile number, sessions and account deletion).

The access token is kept in memory only; the refresh token is an httpOnly cookie set by the API, so nothing sensitive is stored in `localStorage`.

## Setup

Requires Node.js 22.19+ (22.17 builds and passes tests, but npm prints engine warnings).

```powershell
cd frontend
npm ci
copy .env.example .env.local
```

## Run

```powershell
npm run dev        # http://localhost:5173
```

The home page calls `GET /api/v1/health` on `VITE_API_BASE_URL` (default `http://localhost:8000`) and shows a readable offline state with retry if the backend is not running.

## Quality checks

```powershell
npm run lint
npm run format:check   # npm run format to fix
npm run typecheck
npm run test           # vitest --run
npm run build
```

## Layout

```text
src/
  app/          App, providers (theme + TanStack Query)
  components/   ui (primitives), shared (domain components), common, layout, navigation
  features/     auth/, profile/, system/ (api, schemas, hooks, components per feature)
  hooks/        reusable hooks (useHealth)
  lib/          env, api client + errors, error handling, query client, display mode
  services/     typed API calls built on the client
  styles/       Tailwind entry and design tokens
  routes/       route table and pages
  types/        API types
```

Only `VITE_`-prefixed values reach the browser. Never put secrets there.

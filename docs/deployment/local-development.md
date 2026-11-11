# Local Development Guide

**Document:** CHKR-DEPLOY-001  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Step-by-step instructions for setting up and running Chikka Reborn locally. After following this guide, a developer should have a fully working frontend and backend on their machine with simulation SMS mode and mocked AI.

## Scope

Development environment only. All local development uses simulation SMS mode. No real SMS messages are sent during local development.

---

## 1. Prerequisites

| Tool | Minimum Version | Install |
|---|---|---|
| Node.js | 20.x LTS | https://nodejs.org |
| Python | 3.12 | https://python.org |
| Git | 2.40+ | https://git-scm.com |
| Supabase CLI | Latest | `npm install -g supabase` |
| Docker Desktop | Latest | https://docker.com (optional, for backend containerisation) |

Verify versions:
```powershell
node --version    # v20.x.x
python --version  # Python 3.12.x
git --version
supabase --version
```

---

## 2. Clone the Repository

```powershell
git clone https://github.com/your-org/chikka-reborn.git
cd chikka-reborn
```

---

## 3. Supabase Local Setup

Chikka Reborn uses Supabase for the database, auth, and realtime. For local development, use the Supabase CLI to run a local Supabase instance.

```powershell
# Start local Supabase (Docker required)
supabase start

# This starts: PostgreSQL, Auth, Realtime, Storage, Studio
# Studio available at: http://localhost:54323
```

After first start, note the output values:
```
API URL: http://localhost:54321
DB URL: postgresql://postgres:postgres@localhost:54322/postgres
Studio URL: http://localhost:54323
anon key: eyJhbGciOiJIUzI1NiIs...
service_role key: eyJhbGciOiJIUzI1NiIs...
JWT secret: super-secret-jwt-token-with-at-least-32-characters-long
```

Apply migrations:
```powershell
supabase db push
```

Seed country capabilities:
```powershell
supabase db execute --file supabase/seed.sql
```

**Alternative: Use a shared dev Supabase project**  
If your team has a shared development Supabase project, skip local Supabase setup and use the shared project's credentials in your `.env` files.

---

## 4. Backend Setup

```powershell
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows PowerShell

# Install dependencies (runtime + test and lint tools)
pip install -r requirements-dev.txt

# Copy environment template
copy .env.example .env
```

Edit `backend/.env` (all optional for a first start; see `backend/.env.example`):
```env
# Supabase (use local Supabase values from step 3, or shared dev project)
SUPABASE_URL=http://localhost:54321
SUPABASE_JWT_SECRET=<JWT secret from supabase start>
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres

# SMS — always simulation for local development
SMS_PROVIDER_MODE=mock

# App
LOG_LEVEL=DEBUG
```

Start the backend:
```powershell
uvicorn app.main:app --reload --port 8000
```

Verify:
```powershell
curl http://localhost:8000/api/v1/health
# {"status":"ok","service":"chikka-reborn-api","sms_mode":"simulation","database":"ok",...}
```

API documentation: http://localhost:8000/docs (disabled when `APP_ENV=production`).

Without `DATABASE_URL` the app still starts and reports `"database":"not_configured"`. Without `SUPABASE_JWT_SECRET`, protected routes return 503 (authentication fails closed).

Backend auto-reloads on file changes via `--reload`.

---

## 5. Frontend Setup

```powershell
cd frontend

# Install dependencies
npm install

# Copy environment template
copy .env.example .env.local
```

Edit `frontend/.env.local`:
```env
# Supabase (use local or shared dev project values)
VITE_SUPABASE_URL=http://localhost:54321
VITE_SUPABASE_ANON_KEY=<anon key from supabase start>

# Backend API
VITE_API_BASE_URL=http://localhost:8000
```

Start the frontend dev server:
```powershell
npm run dev
```

App available at: `http://localhost:5173`

---

### Shortcut scripts

```powershell
scripts\setup.ps1          # venv, dependencies, copies .env.example files
scripts\dev-backend.ps1    # uvicorn with reload on :8000
scripts\dev-frontend.ps1   # Vite on :5173
scripts\check.ps1          # lint, format, types, tests and build for both apps
```

---

## 6. Running Tests Locally

### Backend Tests
```powershell
cd backend

# All tests
pytest

# Specific file
pytest tests/integration/test_health.py

# With coverage
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

### Frontend Tests
```powershell
cd frontend

# All tests (single run — not watch mode)
npm run test
```

### E2E Tests (requires staging, not local)
```powershell
cd frontend

# Point Playwright at staging URL
PLAYWRIGHT_BASE_URL=https://staging.chikka-reborn.app npx playwright test
```

---

## 7. Simulating Inbound SMS Locally

Since no real SMS webhook arrives during local development, use the simulation endpoint:

```powershell
# Requires: admin JWT token + simulation mode
curl -X POST http://localhost:8000/api/v1/sms/simulate/inbound \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "from_phone": "+639171234567",
    "to_number": "+14155551234",
    "body": "Maayos naman! Salamat."
  }'
```

This triggers the full inbound SMS processing flow including Realtime push to the browser.

---

## 8. Development Workflow

```
1. Pull latest from main
   git pull origin main

2. Create feature branch
   git checkout -b feature/my-feature

3. Make changes (backend + frontend as needed)

4. Run tests
   cd backend && pytest
   cd frontend && npm run test

5. Lint and type check (or run everything: scripts\check.ps1)
   cd backend && ruff check . && ruff format --check . && mypy
   cd frontend && npm run lint && npm run format:check && npm run typecheck

6. Commit
   git add <specific files>
   git commit -m "feat: short description"

7. Push and open PR
   git push -u origin feature/my-feature
```

---

## 9. Common Issues

| Issue | Cause | Fix |
|---|---|---|
| `supabase start` fails | Docker not running | Start Docker Desktop first |
| `401 Unauthorized` on all API calls | Wrong JWT secret in `.env.local` | Copy exact value from `supabase start` output |
| Frontend cannot connect to backend | `VITE_API_BASE_URL` wrong | Set to `http://localhost:8000` |
| Realtime messages not arriving | Realtime not enabled on table | Run `supabase db push` to apply publications |
| `ModuleNotFoundError` in backend | venv not activated | `.venv\Scripts\activate` |
| Browser shows a CORS error | Frontend origin not in `CORS_ORIGINS` | Add it (explicit origins only; `*` is rejected) |
| Backend refuses to start with `SMS_LIVE_CONFIRMED` error | `SMS_PROVIDER_MODE=live` without operator confirmation | Use `mock` locally |
| Port 5173 already in use | Another Vite server running | `npx kill-port 5173` then `npm run dev` |

---

## 10. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

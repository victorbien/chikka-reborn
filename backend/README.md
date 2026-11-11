# Chikka Reborn backend

FastAPI foundation. No business features yet (Phase 1 adds auth, profiles and chat).

## Setup

Requires Python 3.12.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env
```

The app starts with an empty `.env`: without `DATABASE_URL` it reports the database as `not_configured`, and protected routes return 503 until `SUPABASE_JWT_SECRET` is set (it fails closed).

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

| URL | Purpose |
|---|---|
| `GET /api/v1/health` | Liveness and configuration summary (always 200 while up) |
| `GET /api/v1/health/ready` | Readiness (503 if a configured dependency is down) |
| `/docs`, `/redoc`, `/api/v1/openapi.json` | API documentation (disabled when `APP_ENV=production`) |

## Quality checks

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --cov=app
```

## Layout

```text
app/
  api/v1/          routers (thin) and api/deps.py (settings, DB session, auth)
  core/            config, logging, middleware, exceptions, request context, JWT security
  database/        async SQLAlchemy engine and session scope
  models/          ORM base (schema is owned by supabase/migrations)
  schemas/         Pydantic request/response models
  services/        business rules
  repositories/    the only layer that touches SQLAlchemy
  modules/         feature modules (empty until Phase 1)
  integrations/    SMS and AI provider interfaces (empty until Phase 2)
  main.py          application factory
```

Every response carries a `request_id` (also sent as `X-Request-ID`). Errors use `{"error": {"code", "message", "details"}, "request_id"}`.

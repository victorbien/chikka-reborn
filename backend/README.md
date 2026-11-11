# Chikka Reborn backend

FastAPI backend. Implemented: foundation and Module A (authentication and user management). API reference: `docs/api/authentication-api.md`.

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

`tests/flows/` needs Node.js and `npm ci` in `supabase/tools` (PGlite database server); otherwise those tests are skipped. `tests/support/fake_supabase.py` is a test double of the Supabase Auth and Storage endpoints and is never imported by `app/`.

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
  modules/         audit, rate_limits, profiles, auth (router, schemas, service, repository, models)
  integrations/    AuthProvider (Supabase Auth), StorageProvider, OtpDelivery (simulated/live)
  main.py          application factory
```

Every response carries a `request_id` (also sent as `X-Request-ID`). Errors use `{"error": {"code", "message", "details"}, "request_id"}`.

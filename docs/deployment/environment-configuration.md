# Environment Configuration

**Document:** CHKR-DEPLOY-002  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Defines every environment variable required by Chikka Reborn, its purpose, which environment it belongs to, and where it is stored.

## Scope

All three environments: development, staging, production.

---

## 1. Environment Overview

| Environment | Purpose | SMS Mode | AI Mode |
|---|---|---|---|
| `development` | Local developer machines | simulation only | mocked (no Bedrock) |
| `staging` | Integration tests, E2E, demos | simulation only | real Bedrock |
| `production` | Live platform | configurable | real Bedrock |

---

## 2. Secret Storage by Environment

| Environment | Storage Method |
|---|---|
| Development | `.env.local` (gitignored) |
| Staging | Hosting platform environment variables UI |
| Production | Hosting platform environment variables UI |

`.env.local` files are listed in `.gitignore`. They are never committed. `.env.example` files (committed, no secret values) document every required variable.

---

## 3. Backend Environment Variables

### Required — All Environments

| Variable | Description | Example |
|---|---|---|
| `SUPABASE_URL` | Supabase project API URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend service role key — bypasses RLS | `eyJhbGci...` |
| `SUPABASE_JWT_SECRET` | Used to verify Supabase JWTs in FastAPI | `super-secret-...` |
| `SMS_PROVIDER_MODE` | `mock` or `live` | `mock` |
| `LOG_LEVEL` | Log verbosity | `INFO` |

### Required — Live SMS Mode Only

| Variable | Description |
|---|---|
| `TWILIO_ACCOUNT_SID` | Twilio account identifier |
| `TWILIO_AUTH_TOKEN` | Twilio API authentication token |
| `TWILIO_PHONE_NUMBER` | Platform's outbound Twilio number (E.164) |
| `TWILIO_WEBHOOK_SECRET` | Signing secret for validating Twilio webhooks |

These variables are validated at startup when `SMS_PROVIDER_MODE=live`. The application fails to start without them if live mode is configured.

### Required — AI Features (Phase 3+)

| Variable | Description |
|---|---|
| `AWS_REGION` | AWS region where Bedrock is available (e.g. `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | IAM user access key — Bedrock invoke permissions only |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key |
| `BEDROCK_MODEL_ID` | Model identifier (e.g. `anthropic.claude-3-haiku-20240307-v1:0`) |

### Optional — Tuning

| Variable | Default | Description |
|---|---|---|
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Pool overflow connections |
| `RATE_LIMIT_LOGIN` | `5` | Max failed logins per 15 min per IP |
| `RATE_LIMIT_SMS_DAILY` | `500` | Max SMS sends per user per day |
| `RATE_LIMIT_AI_HOURLY` | `50` | Max AI requests per user per hour |
| `SMS_MAX_RETRIES` | `3` | Max SMS retry attempts before permanently_failed |
| `SMS_RETRY_BASE_DELAY_S` | `30` | Base retry delay in seconds |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed CORS origins |

---

## 4. Frontend Environment Variables

All frontend variables are prefixed with `VITE_` — they are bundled into the frontend at build time.

> **Security note:** Only the `VITE_SUPABASE_ANON_KEY` and `VITE_SUPABASE_URL` contain service-specific values. The anon key is intentionally public — it is row-level-security-enforced and safe to expose. No other secrets belong in frontend variables.

| Variable | Description | Example |
|---|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | Supabase public anon key | `eyJhbGci...` |
| `VITE_API_BASE_URL` | Backend API base URL | `https://api.chikka-reborn.app` |

---

## 5. `.env.example` Files

Two example files are committed to the repository. They document every variable with placeholder values.

### `backend/.env.example`

```env
# ─── Supabase ────────────────────────────────────────────────
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

# ─── SMS ─────────────────────────────────────────────────────
SMS_PROVIDER_MODE=mock
# Required only when SMS_PROVIDER_MODE=live:
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
TWILIO_WEBHOOK_SECRET=

# ─── AI (Phase 3+) ───────────────────────────────────────────
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
BEDROCK_MODEL_ID=

# ─── Application ─────────────────────────────────────────────
LOG_LEVEL=DEBUG
CORS_ORIGINS=http://localhost:5173
DB_POOL_SIZE=5
RATE_LIMIT_LOGIN=5
RATE_LIMIT_SMS_DAILY=500
RATE_LIMIT_AI_HOURLY=50
```

### `frontend/.env.example`

```env
# ─── Supabase ────────────────────────────────────────────────
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key

# ─── API ─────────────────────────────────────────────────────
VITE_API_BASE_URL=http://localhost:8000
```

---

## 6. Startup Validation

The FastAPI backend validates required environment variables at startup via `pydantic-settings`. If any required variable is missing, the application exits immediately with a clear error before accepting any requests.

```
ERROR: Configuration error: SUPABASE_URL is required but not set.
Ensure all required environment variables are defined in .env.local or the hosting platform.
```

This prevents the application from running in a silently broken state.

---

## 7. Per-Environment Variable Values

| Variable | Development | Staging | Production |
|---|---|---|---|
| `SUPABASE_URL` | Local or dev project | Staging project | Production project |
| `SMS_PROVIDER_MODE` | `mock` | `mock` | `mock` (default) or `live` (requires approval) |
| `LOG_LEVEL` | `DEBUG` | `INFO` | `INFO` |
| `CORS_ORIGINS` | `http://localhost:5173` | `https://staging.chikka-reborn.app` | `https://chikka-reborn.app` |
| `VITE_API_BASE_URL` | `http://localhost:8000` | `https://api-staging.chikka-reborn.app` | `https://api.chikka-reborn.app` |

---

## 8. Rotation Policy

| Secret | Rotation Trigger | Method |
|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | Team member departure; suspected exposure | Rotate in Supabase dashboard; update hosting env var |
| `SUPABASE_JWT_SECRET` | Suspected compromise | Rotate in Supabase dashboard; update backend env var; all sessions invalidated |
| `TWILIO_AUTH_TOKEN` | Annually; suspected exposure | Rotate in Twilio console; update hosting env var |
| `TWILIO_WEBHOOK_SECRET` | Annually; provider allows rotation | Rotate in Twilio console; update hosting env var |
| `AWS_ACCESS_KEY_ID` / `SECRET` | Quarterly; team member departure | Rotate in IAM; update hosting env var |

---

## 9. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

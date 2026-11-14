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
| `SUPABASE_JWT_SECRET` | Legacy shared secret; verifies HS256 access tokens. Optional on projects using signing keys | `super-secret-...` |
| `SUPABASE_JWKS_URL` | Optional. Public keys for ES256/RS256 access tokens. Defaults to `SUPABASE_URL/auth/v1/.well-known/jwks.json` | `https://xxx.supabase.co/auth/v1/.well-known/jwks.json` |
| `SMS_PROVIDER_MODE` | `mock` or `live` | `mock` |
| `LOG_LEVEL` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO` |
| `APP_ENV` | `development`, `test`, `staging` or `production`. API docs are disabled in `production` | `development` |
| `DATABASE_URL` | Supabase PostgreSQL connection string. `postgresql://` is upgraded to the asyncpg driver. Optional at startup: when unset the health check reports `not_configured` | `postgresql://postgres:...@db.xxx.supabase.co:5432/postgres` |
| `SMS_LIVE_CONFIRMED` | Must be `true` for `SMS_PROVIDER_MODE=live`; otherwise startup fails. Never set it in development | `false` |
| `SUPABASE_ANON_KEY` | Public anon key; identifies the project to Supabase Auth for user-level calls (sign-up, sign-in, refresh). Without it and `SUPABASE_URL`, auth endpoints answer 503 | `eyJhbGci...` |
| `APP_SECRET_KEY` | Keys the HMACs for rate-limit subjects and mobile OTP hashes. Required (32+ characters) in `staging` and `production`; development uses a per-process random key | 64 random characters |
| `FRONTEND_BASE_URL` | SPA origin used in email links (`/auth/verify-email`, `/auth/reset-password`) | `http://localhost:5173` |
| `COOKIE_SECURE` | Override for the refresh cookie `Secure` flag. Default: on in `staging`/`production`, off in local development | (unset) |
| `TERMS_VERSION`, `PRIVACY_VERSION` | Notice versions recorded with registration consent | `2026-11-01` |
| `AVATAR_BUCKET` | Supabase Storage bucket for profile photos | `avatars` |
| `ATTACHMENT_BUCKET` | Private Storage bucket for message attachments (created by migration `20261111000003`) | `message-attachments` |

### Required — Live SMS Mode Only

| Variable | Description |
|---|---|
| `TWILIO_ACCOUNT_SID` | Twilio account identifier |
| `TWILIO_AUTH_TOKEN` | Twilio API auth token. Also the key that signs Twilio webhooks, so there is no separate webhook secret |
| `SMS_PUBLIC_BASE_URL` | Public HTTPS origin of this backend (for example `https://api.example.com`). Twilio signs the exact URL it calls, so the signature check uses this value, never the `Host` header |

Sender numbers are not environment variables. They are non-secret settings stored on the provider row (`provider_configurations.settings.sender_numbers`) and edited by administrators. Sending also needs, per country, a capability row marked `supported` with recorded verification, a configured price, and (for the Philippines) an approved sender registration. See [sms-live-activation.md](sms-live-activation.md).

These variables are validated at startup when `SMS_PROVIDER_MODE=live`. The application fails to start without them. It never falls back to simulation.

### Optional — SMS subsystem

| Variable | Default | Description |
|---|---|---|
| `SMS_MOCK_WEBHOOK_SECRET` | random per process | Key for the simulation's webhook signer. Set it when several instances share one simulation |
| `SMS_WORKER_ENABLED` | `true` | Runs the in-process worker (dispatch, retries, reconciliation, simulated callbacks). Tests turn it off |
| `SMS_WORKER_POLL_SECONDS` | `1` | How often the worker looks for due work when nothing wakes it |
| `SMS_AMBIGUOUS_WINDOW_SECONDS` | `900` | How long a message with an unknown outcome waits for proof before it is marked failed |
| `SMS_QUEUE_MAX_AGE_SECONDS` | `86400` | A message still queued after this long (for example during a provider outage) is marked failed |
| `SMS_ATTESTATION_VERSION` | `2026-11-01` | Version of the sender-permission wording recorded with each consent |

Retry attempts, backoff and rate limits are not environment variables: they live in `provider_configurations` and `system_settings` so administrators can change them (`max_retry_attempts`, `retry_base_seconds`, `retry_cap_seconds`, `sms_user_limit_per_hour`, `sms_recipient_limit_per_hour`).
### Optional - Notifications and email

Notification email defaults to the mock provider: nothing is sent to a real mailbox. `EMAIL_PROVIDER_MODE=smtp` needs `SMTP_HOST` and `EMAIL_FROM_ADDRESS` and fails at startup without them; it never falls back to the mock.

| Variable | Default | Description |
|---|---|---|
| `EMAIL_PROVIDER_MODE` | `mock` | `mock` or `smtp` |
| `EMAIL_FROM_ADDRESS` | none | Sender address. Required for `smtp` |
| `SMTP_HOST` | none | SMTP server. Required for `smtp` |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | none | Credentials, if the server needs them. Backend only, never logged |
| `SMTP_STARTTLS` | `true` | Upgrade the connection with STARTTLS |
| `NOTIFICATIONS_WORKER_ENABLED` | `true` | Runs the dispatcher that announces notifications to open sessions and sends email. Tests turn it off |
| `NOTIFICATIONS_WORKER_POLL_SECONDS` | `1` | How often the dispatcher looks for new work |

Simulated credit amounts are not environment variables: `system_settings.demo_grant_units` (default 5000, so 50 credits) and `sms_demo_units_per_segment` (default 100) are administrator settings, and each user sets their own low-balance threshold in notification settings.

### Optional - AI assistant

The assistant defaults to the mock provider: it calls nothing external and returns canned demo drafts, which the UI labels as a demo. `AI_PROVIDER_MODE=bedrock` needs all three Bedrock values below; startup fails without them and never falls back to the mock. Credentials are backend-only.

| Variable | Default | Description |
|---|---|---|
| `AI_PROVIDER_MODE` | `mock` | `mock` or `bedrock` |
| `BEDROCK_REGION` | none | AWS region where the model is enabled (for example `us-east-1`). Required for `bedrock` |
| `BEDROCK_MODEL_ID` | none | Bedrock model identifier. Required for `bedrock`. Check that it handles Filipino and the regional languages you offer |
| `BEDROCK_API_KEY` | none | Bedrock API key, sent as a bearer token to the Converse API. Required for `bedrock`. Never logged, never sent to the browser |
| `AI_TIMEOUT_SECONDS` | `15` | Per-request timeout for the model call |
| `AI_MAX_OUTPUT_TOKENS` | `600` | Upper bound on the model's answer length |
| `AI_COST_PER_1K_INPUT_USD` | none | Optional list price per 1,000 input tokens. With the output price, lets the admin dashboard show an approximate AI cost. Unset means no cost is shown |
| `AI_COST_PER_1K_OUTPUT_USD` | none | Optional list price per 1,000 output tokens |

The kill switch (`system_settings.ai_enabled`) and the per-user hourly limit (`system_settings.ai_user_limit_per_hour`, default 30) are runtime settings, not environment variables. Each user also has to turn the assistant on for their own account (`profiles.ai_enabled`, default off).

### Optional — Tuning

| Variable | Default | Description |
|---|---|---|
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size (1-50) |
| `DB_MAX_OVERFLOW` | `20` | Pool overflow connections |
| `RATE_LIMIT_LOGIN` | `5` | Max failed logins per 15 min per IP |
| `RATE_LIMIT_AI_HOURLY` | `50` | Max AI requests per user per hour |
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
| `VITE_APP_ENV` | `development`, `test`, `staging` or `production` (default `development`) | `production` |

Values are validated at startup with Zod; an invalid URL or environment name stops the app with a readable message. Blank values (as left by copying `.env.example`) count as unset.

---

## 5. `.env.example` Files

Two example files are committed (`backend/.env.example` and `frontend/.env.example`; the real files are `backend/.env` and `frontend/.env.local`) to the repository. They document every variable with placeholder values.

### `backend/.env.example`

> The committed file currently contains only the variables the code reads (foundation plus Module A: `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `APP_SECRET_KEY`, `FRONTEND_BASE_URL`, `COOKIE_SECURE`, `TERMS_VERSION`, `PRIVACY_VERSION`, `AVATAR_BUCKET`, `ATTACHMENT_BUCKET`). Twilio, AWS/Bedrock, service-role and rate-limit variables are added in the phase that first reads them, so the example never lists settings that do nothing.

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
SMS_PUBLIC_BASE_URL=

# ─── AI (Phase 3+) ───────────────────────────────────────────
EMAIL_PROVIDER_MODE=mock
# Required only when EMAIL_PROVIDER_MODE=smtp:
EMAIL_FROM_ADDRESS=
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=

AI_PROVIDER_MODE=mock
# Required only when AI_PROVIDER_MODE=bedrock:
BEDROCK_REGION=
BEDROCK_MODEL_ID=
BEDROCK_API_KEY=

# ─── Application ─────────────────────────────────────────────
LOG_LEVEL=DEBUG
CORS_ORIGINS=http://localhost:5173
DB_POOL_SIZE=5
RATE_LIMIT_LOGIN=5
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
| `TWILIO_AUTH_TOKEN` (also signs webhooks) | Annually, or at once if exposed | Rotate in the Twilio console; update the hosting env var; restart. Webhooks signed with the old token fail until then |
| `BEDROCK_API_KEY` | Quarterly; team member departure | Rotate in IAM; update hosting env var |

---

## 9. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

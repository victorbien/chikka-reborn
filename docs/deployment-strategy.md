# Deployment Strategy

> **SUPERSEDED (November 2026).** Retained for history. The canonical version is in docs/deployment/deployment-guide.md. Requirement IDs here use the older scheme (e.g. FR-A-001); see the 'Was:' fields in docs/product/functional-requirements.md for the mapping.

**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Date:** November 2026  

---

## 1. Overview

Chikka Reborn uses a three-tier deployment model:

| Tier | Technology | Host |
|---|---|---|
| Frontend (React SPA) | Vite build → static assets | Vercel |
| Backend (FastAPI) | Python ASGI app | Render / Railway / Fly.io (TBD — see OD-003) |
| Database & Auth | PostgreSQL + Auth + Realtime | Supabase |

All three tiers are independently deployable. The frontend never needs to be redeployed when only the backend changes, and vice versa.

---

## 2. Environments

| Environment | Purpose | SMS Mode | AI Mode | Notes |
|---|---|---|---|---|
| **Development** | Local developer machines | Simulation | Mocked | No real external calls |
| **Staging** | Integration testing, E2E tests, demos | Simulation | Real (Bedrock) | Mirrors production config |
| **Production** | Live platform | Configurable | Real (Bedrock) | Live SMS requires operator approval |

### Environment Isolation Rules

- Development, staging, and production each have **separate Supabase projects** with separate databases.
- Development and staging environments **must never** use live SMS mode without explicit operator approval.
- Production API keys and secrets **must never** be used in development or staging.
- The backend reads `SMS_PROVIDER_MODE` at startup and validates it. If `live` is set in a non-production environment, the application logs a prominent warning but continues (to support intentional staging live-SMS tests with approval).

---

## 3. Frontend Deployment (Vercel)

### Build Process

```bash
# Build command
npm run build          # vite build → dist/

# Output directory
dist/

# Environment variables (set in Vercel dashboard)
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
VITE_API_BASE_URL
```

### Deployment Triggers

| Event | Action |
|---|---|
| Push to `main` | Auto-deploy to production (after E2E tests pass) |
| Push to `staging` branch | Auto-deploy to staging |
| Pull request opened | Deploy preview environment (Vercel preview URLs) |

### Vercel Configuration

- **Framework preset:** Vite
- **Root directory:** `frontend/`
- **Build command:** `npm run build`
- **Output directory:** `dist`
- **SPA routing:** `vercel.json` rewrites all paths to `index.html`

```json
// frontend/vercel.json
{
  "rewrites": [{ "source": "/((?!api/).*)", "destination": "/index.html" }],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; connect-src 'self' https://*.supabase.co wss://*.supabase.co https://api.chikka-reborn.app; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; font-src 'self'"
        }
      ]
    },
    {
      "source": "/assets/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }
      ]
    }
  ]
}
```

---

## 4. Backend Deployment (FastAPI)

### Containerisation

The FastAPI application is packaged as a Docker container.

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fail fast if required env vars are missing
RUN python -c "from config import Settings; Settings()"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### Hosting Platform Selection (Open Decision OD-003)

Three platforms are under consideration. The decision will be made before Phase 1 development:

| Platform | Pros | Cons |
|---|---|---|
| **Render** | Simple, Git-connected, managed TLS, free tier | Cold starts on free tier |
| **Railway** | Fast deploys, good DX, generous free tier | Smaller ecosystem than Render |
| **Fly.io** | Global edge deployment, persistent volumes, WebSocket support | More configuration required |

**Recommendation:** Render for Phase 1 (simplicity, managed TLS, GitHub integration). Migrate to Fly.io if global edge latency becomes a requirement in Phase 3+.

### Deployment Process

1. Push to `main` triggers CI pipeline.
2. CI runs all tests and build checks.
3. On success, Docker image is built and pushed to a container registry (Docker Hub or GitHub Container Registry).
4. Hosting platform pulls the new image and performs a rolling deploy.
5. Health check at `/health` is polled — if it fails, the deploy is rolled back automatically.

### Zero-Downtime Deployment

- Rolling deploys: the old instance continues to serve requests until the new instance passes health checks.
- Database migrations are applied **before** the new application code is deployed (backward-compatible migrations only).
- Breaking schema changes require a multi-step deploy: add new column → deploy → migrate data → remove old column → deploy.

---

## 5. Database Deployment (Supabase)

### Migration Application

```bash
# Apply migrations to staging
supabase db push --project-ref <staging-ref>

# Apply migrations to production (requires explicit operator command)
supabase db push --project-ref <production-ref>
```

Migrations are **never applied automatically** to production. A human operator runs the migration command after reviewing the migration file.

### Migration Safety Checklist

Before any production migration:
- [ ] Migration has been applied and verified on staging.
- [ ] Migration is backward-compatible with the currently deployed application version.
- [ ] A rollback plan exists if the migration needs to be reversed.
- [ ] Point-in-time recovery is confirmed available for the production database.
- [ ] Maintenance window communicated to users if the migration is expected to cause downtime.

### Supabase Project Structure

| Project | Environment | Notes |
|---|---|---|
| `chikka-reborn-dev` | Development | Shared among developers |
| `chikka-reborn-staging` | Staging | Mirrors production schema |
| `chikka-reborn-prod` | Production | Production data; restricted access |

---

## 6. Secrets Management

All secrets are environment variables. They are never stored in version control.

### Per-Environment Secret Storage

| Environment | Secrets Location |
|---|---|
| Development | `.env.local` file (gitignored) |
| Staging | Hosting platform environment variable UI |
| Production | Hosting platform environment variable UI |

### Required Secrets Per Environment

```
# Supabase
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_JWT_SECRET

# Frontend (VITE_ prefix = bundled into client)
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
VITE_API_BASE_URL

# SMS (backend only)
SMS_PROVIDER_MODE               # 'mock' or 'live'
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER
TWILIO_WEBHOOK_SECRET

# AI (backend only)
AWS_REGION
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
BEDROCK_MODEL_ID

# Application
LOG_LEVEL
```

### Secrets Rotation Policy

- Supabase service role key: rotate if any team member leaves or if a leak is suspected.
- Twilio auth token: rotate annually or on suspected leak.
- AWS credentials: use IAM roles with minimal permissions; rotate access keys quarterly.
- Webhook signing secrets: rotate when the SMS provider allows; update environment variable immediately.

---

## 7. CI/CD Pipeline Summary

```
┌─────────────────────────────────────────────────────────────────┐
│  Pull Request                                                   │
│                                                                 │
│  1. Lint (ESLint, Ruff)                                        │
│  2. Type check (tsc --noEmit, mypy)                            │
│  3. Backend tests (pytest)                                      │
│  4. Frontend tests (vitest)                                     │
│  5. Build frontend (vite build)                                 │
│  6. Build backend Docker image                                  │
│  7. Vercel preview deploy                                       │
│                                                                 │
│  All steps must pass → PR can be merged                        │
└─────────────────────────────────────────────────────────────────┘
                             │
                             │ Merge to main
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Main Branch                                                    │
│                                                                 │
│  1. All PR steps (repeated)                                    │
│  2. Push Docker image to registry                              │
│  3. Deploy to staging (Render/Railway/Fly.io)                  │
│  4. Run E2E tests (Playwright) against staging                 │
│  5. All E2E tests pass                                         │
│                                                                 │
│  ↓ Automatic (Phase 1) or Manual gate (Phase 2+)              │
│                                                                 │
│  6. Deploy frontend to Vercel production                       │
│  7. Deploy backend to production                               │
│  8. Health check confirmation                                  │
│  9. Smoke test (automated: ping /health, send test Chikka msg) │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Monitoring and Observability

### Health Checks

- `/health` endpoint returns service status, database connectivity, and SMS provider mode.
- Hosting platform polls `/health` every 30 seconds.
- Supabase dashboard monitors database performance.

### Logging

- All backend logs are structured JSON, shipped to the hosting platform's log aggregation service.
- Log levels: `DEBUG` (development only), `INFO` (staging/production), `WARNING`, `ERROR`.
- Errors are tagged with `request_id` for cross-service tracing.

### Alerting (Phase 2+)

- Alert on: 5xx error rate > 1% over 5 minutes.
- Alert on: `/health` check failure for > 2 consecutive checks.
- Alert on: SMS permanent failure rate > 5%.
- Alert on: credit account balance anomalies.
- Alerting tool: hosting platform native alerts or a lightweight service like Better Uptime.

### Performance Monitoring (Phase 2+)

- Backend: consider Sentry or OpenTelemetry for distributed tracing.
- Frontend: Vercel Analytics for Core Web Vitals.

---

## 9. Rollback Procedures

### Frontend Rollback
Vercel maintains a deployment history. Rollback is a single click in the Vercel dashboard or:
```bash
vercel rollback <deployment-url>
```

### Backend Rollback
The previous Docker image is retained in the container registry. Rollback by deploying the previous image tag via the hosting platform dashboard or CLI.

### Database Rollback
- Supabase provides point-in-time recovery (PITR).
- If a migration caused data issues: restore from PITR backup and re-apply only the safe migrations.
- Additive migrations (ADD COLUMN, CREATE TABLE) are easily reversible.
- Destructive migrations require the pre-migration backup to be available.

---

## 10. Production Launch Checklist

Before any production launch or major feature release:

**Infrastructure**
- [ ] All environment variables set and verified in production.
- [ ] HTTPS configured and certificate valid.
- [ ] CORS configured to allow only the production frontend domain.
- [ ] Rate limiting active on all sensitive endpoints.
- [ ] Webhook endpoints reachable from provider IPs.

**Database**
- [ ] All migrations applied and verified on staging first.
- [ ] Point-in-time recovery confirmed enabled.
- [ ] RLS policies reviewed and tested.
- [ ] Backup retention confirmed.

**SMS**
- [ ] SMS mode is `mock` unless live SMS has been explicitly approved.
- [ ] Twilio webhook URL updated to production endpoint.
- [ ] Webhook signature validation confirmed working.
- [ ] Philippine sender ID registration confirmed (for PH live SMS).

**AI**
- [ ] Bedrock access confirmed in target AWS region.
- [ ] IAM permissions scoped to Bedrock inference only.
- [ ] Token usage limits configured.

**Security**
- [ ] CSP headers verified.
- [ ] Security headers present (X-Frame-Options, X-Content-Type-Options).
- [ ] No secrets in version control (automated secret scanning).
- [ ] Dependency vulnerability scan passes.

**Monitoring**
- [ ] Health check alert configured.
- [ ] Log aggregation confirmed.
- [ ] Error alerting configured.

---

## 11. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

# Deployment Guide

**Document:** CHKR-DEPLOY-003  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Step-by-step deployment procedures for all environments. Covers frontend (Vercel), backend (hosting platform TBD), database migrations (Supabase), and the production launch checklist.

## Scope

Staging and production deployments. Local setup is in `docs/deployment/local-development.md`.

---

## 1. Deployment Architecture

```
GitHub Repository
       │
       ├── PR opened → CI Pipeline → Preview Deploy (Vercel)
       │
       └── Merge to main → CI Pipeline → Deploy to Staging
                                              │
                                        E2E Tests Pass
                                              │
                                      Deploy to Production
                                     (auto Phase 1, manual gate Phase 2+)
```

---

## 2. Frontend Deployment (Vercel)

### Initial Setup (one-time)

1. Connect GitHub repository to Vercel project.
2. Set root directory: `frontend/`
3. Set framework preset: `Vite`
4. Set build command: `npm run build`
5. Set output directory: `dist`
6. Add environment variables in Vercel dashboard (see `docs/deployment/environment-configuration.md`).

### Deployment Triggers

| Event | Action |
|---|---|
| Pull request opened | Vercel preview deployment (unique URL per PR) |
| Push to `main` | Deploy to production (after CI + E2E pass) |
| Push to `staging` branch | Deploy to staging |

### `vercel.json`

```json
{
  "rewrites": [
    { "source": "/((?!api/).*)", "destination": "/index.html" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Strict-Transport-Security", "value": "max-age=31536000; includeSubDomains" },
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; connect-src 'self' https://*.supabase.co wss://*.supabase.co https://api.chikka-reborn.app; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'none'"
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

### Manual Rollback

```powershell
# Via Vercel CLI
vercel rollback <previous-deployment-url>

# Or via Vercel dashboard: Deployments → select previous → Promote to Production
```

---

## 3. Backend Deployment

### Container Build

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Validate config at build time (fails fast if required vars are missing in CI)
# Note: in production, env vars are injected at runtime, not build time
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

Build and push:
```powershell
docker build -t chikka-reborn-backend:$VERSION ./backend
docker tag chikka-reborn-backend:$VERSION ghcr.io/your-org/chikka-reborn-backend:$VERSION
docker push ghcr.io/your-org/chikka-reborn-backend:$VERSION
```

### Hosting Platform (OD-003 — TBD)

The deployment command varies by platform. All three candidates support rolling deploys:

**Render:**
```bash
# Auto-deploys on push to main via GitHub integration
# Or via Render CLI:
render deploy --service-id <service-id>
```

**Railway:**
```bash
railway up --service backend
```

**Fly.io:**
```bash
fly deploy --app chikka-reborn-backend
```

### Zero-Downtime Deploy

All three platforms support rolling deploys by default. The new container is started, health-checked, and traffic is shifted to it before the old container is terminated.

Health check used by the platform:
```
GET /health → { "status": "healthy" }
```

If `/health` does not return healthy within 60 seconds, the deploy is rolled back automatically.

### Manual Backend Rollback

```bash
# Render: revert to previous deploy via Render dashboard or CLI
# Railway: railway rollback --service backend
# Fly.io: fly releases → fly deploy --image <previous-image-tag>
```

---

## 4. Database Migrations

Migrations are **never applied automatically**. A human operator runs the migration command.

### Staging
```powershell
# Verify migration content first
cat supabase\migrations\<new-migration>.sql

# Apply
supabase db push --project-ref <staging-project-ref>

# Verify application is healthy after migration
curl https://api-staging.chikka-reborn.app/health
```

### Production

```powershell
# Pre-migration checklist:
# [ ] Migration applied and verified on staging for > 24 hours
# [ ] Migration is backward-compatible with deployed code
# [ ] PITR backup confirmed available
# [ ] Off-peak window chosen
# [ ] Engineering lead sign-off obtained

supabase db push --project-ref <production-project-ref>

# Post-migration health check:
curl https://api.chikka-reborn.app/health
```

See `docs/database/database-migrations.md` for destructive migration protocol.

---

## 5. CI/CD Pipeline

### GitHub Actions Workflow Skeleton

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, staging]
  pull_request:

jobs:
  lint-and-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Backend lint
        run: cd backend && pip install ruff mypy && ruff check . && mypy .
      - name: Frontend lint
        run: cd frontend && npm ci && npm run lint && npm run type-check

  backend-tests:
    runs-on: ubuntu-latest
    needs: lint-and-typecheck
    steps:
      - uses: actions/checkout@v4
      - name: Run pytest
        run: cd backend && pip install -r requirements.txt && pytest --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  frontend-tests:
    runs-on: ubuntu-latest
    needs: lint-and-typecheck
    steps:
      - uses: actions/checkout@v4
      - name: Run vitest
        run: cd frontend && npm ci && npm run test -- --run

  build:
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]
    steps:
      - uses: actions/checkout@v4
      - name: Build frontend
        run: cd frontend && npm ci && npm run build
      - name: Build backend Docker image
        run: docker build -t chikka-backend ./backend

  deploy-staging:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to staging
        run: echo "Deploy to staging platform"
      - name: Run E2E tests
        run: cd frontend && npx playwright test --project=chromium

  deploy-production:
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    # Phase 1: automatic after E2E pass
    # Phase 2+: add manual approval gate here
    steps:
      - name: Deploy to production
        run: echo "Deploy to production platform"
```

---

## 6. Production Launch Checklist

Run before any production deployment or major feature release.

### Infrastructure
- [ ] All environment variables set and verified in production hosting platform
- [ ] HTTPS configured; SSL certificate valid and auto-renewing
- [ ] CORS configured to allow only `https://chikka-reborn.app`
- [ ] Rate limiting active and tested
- [ ] Health check alert configured on hosting platform
- [ ] Webhook URLs updated to production endpoints in Twilio dashboard (if live mode)

### Database
- [ ] All migrations applied and verified on staging for > 24 hours
- [ ] Point-in-time recovery confirmed enabled on production Supabase project
- [ ] RLS policies reviewed; all tests pass
- [ ] Backup retention period confirmed

### SMS
- [ ] `SMS_PROVIDER_MODE=mock` unless live SMS explicitly approved
- [ ] If live mode: Twilio webhook URLs updated to production
- [ ] If live mode: webhook signature validation confirmed working
- [ ] Philippines: sender ID registration status confirmed

### AI
- [ ] Bedrock model ID and region confirmed and tested
- [ ] AWS IAM permissions scoped to Bedrock inference only
- [ ] Per-user AI rate limits configured

### Security
- [ ] CSP headers verified in browser developer tools
- [ ] Security headers confirmed: X-Frame-Options, X-Content-Type-Options, HSTS
- [ ] No secrets in version control (automated scan passes)
- [ ] Dependency vulnerability scan: no critical/high findings

### Monitoring
- [ ] `/health` endpoint monitoring configured
- [ ] Alert on 5xx error rate > 1% configured
- [ ] Log aggregation confirmed working
- [ ] Error alerting configured and tested

### Legal (Phase 6)
- [ ] Privacy Policy published and linked from registration screen
- [ ] Terms of Service published and linked from registration screen
- [ ] Cookie policy in place (if applicable)

---

## 7. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

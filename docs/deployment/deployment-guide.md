# Deployment Guide

**Document:** CHKR-DEPLOY-003
**Project:** Chikka Reborn
**Version:** 2.0
**Status:** Prepared. Nothing has been deployed from this guide yet.
**Last Revised:** November 2026

Related: [checklist](deployment-checklist.md), [rollback](rollback-procedure.md), [troubleshooting](troubleshooting.md), [monitoring](monitoring-and-logging.md), [Supabase](supabase-setup.md), [Twilio](twilio-configuration.md), [Bedrock](bedrock-setup.md), [variables](environment-configuration.md).

---

## 1. Architecture and the constraints that shape it

```
Browser ──https──> Vercel (static SPA, frontend/dist)
   │
   ├──https + wss──> Backend container (FastAPI, ONE process) ──> Supabase Postgres / Auth / Storage
   │                        ▲   │
   │      Twilio webhooks ──┘   └──> Twilio, Bedrock, SMTP (outbound)
```

Four constraints decide how this is hosted:

1. **One backend process.** The SMS worker, notification worker, presence registry and WebSocket hub run in memory inside the API process. A second process would double-run workers (safe, rows are leased) but would split presence and real-time pushes. The image therefore starts uvicorn with `--workers 1`. Scale up the instance, not out, until cross-instance fan-out exists (see [sms-live-activation.md](sms-live-activation.md), Known limitations).
2. **Same-site domains.** The refresh token is a `SameSite=Lax` httpOnly cookie set by the API. A browser does not send it on a cross-site `fetch`, so the SPA and API must share a registrable domain, for example `app.example.com` and `api.example.com`. `*.vercel.app` plus a platform domain such as `*.onrender.com` will sign users out on every reload. Use a custom domain you own.
3. **WebSockets.** The platform must keep long-lived WebSocket connections (`/ws/v1`) and not time them out below about 60 seconds of idle. Clients are told to ping every 25 seconds, and the server closes a connection that is silent for 60.
4. **Public webhooks.** Twilio must reach `https://<api domain>/api/v1/webhooks/twilio/*`. These routes are authenticated by signature, not by login, and must not sit behind a login wall, IP allow-list that excludes Twilio, or a CDN that rewrites the URL or body.

The hosting platform for the backend is still open (OD-003). Any container host that satisfies the four constraints works (for example Render, Railway or Fly.io). The steps below are platform-neutral; platform-specific names are in section 3.4.

## 2. Frontend on Vercel

### 2.1 What is configured in the repository

| Concern | Where | Behaviour |
|---|---|---|
| Build | `frontend/vercel.json`: `npm ci`, `npm run build`, output `dist`, framework `vite` | `build` runs `tsc --noEmit` then `vite build` |
| Node version | `frontend/package.json` `engines.node` `>=22.12` | Vercel uses a matching Node version |
| Routing | `vercel.json` rewrite `/(.*)` to `/index.html` | React Router deep links work on reload. Real files (`/assets/*`, `/favicon.svg`) are served first |
| Production API URL | `VITE_API_BASE_URL` | Compiled into the bundle. WebSocket URL is derived from it (`wss://`) |
| Build guard | `vite.config.ts` + `src/lib/env-rules.ts` | A build with `VITE_APP_ENV` `staging` or `production` fails if `VITE_API_BASE_URL` is missing, not https, or a local host. The runtime parser applies the same rule |
| Security headers | `vercel.json` | CSP, HSTS, `X-Frame-Options: DENY`, `nosniff`, referrer and permissions policies |
| Caching | `vercel.json` | `/assets/*` immutable for a year (hashed names). Everything else `no-cache` |
| Static assets | `frontend/public/` | `favicon.svg`, `robots.txt` (disallows crawling: this is a private app) |
| Error handling | `components/common/ErrorBoundary.tsx`, `routes/RouteErrorPage.tsx`, `lib/error-handling.ts` | Render crashes and route errors show a readable page. Reports omit messages and payloads |

The Content-Security-Policy allows `connect-src 'self' https: wss:` because the API origin is not known until deployment. After the API domain exists, tighten it to that origin (section 2.3).

### 2.2 One-time project setup

1. In Vercel: **Add New -> Project**, import `victorbien/chikka-reborn`.
2. **Root Directory:** `frontend`. Leave the other fields as detected (they come from `vercel.json`).
3. **Environment Variables** (Production scope; add a Preview scope for staging):

   | Name | Value |
   |---|---|
   | `VITE_API_BASE_URL` | `https://<api domain>` (no trailing slash) |
   | `VITE_APP_ENV` | `production` (or `staging`) |

   Template: `frontend/production.env.example`. Do not add any other secret. Anything `VITE_`-prefixed is public.
4. **Domains:** add `app.<your domain>` and set its DNS as Vercel instructs. HTTPS certificates are issued automatically.
5. **Git:** production branch `main`. Pull requests get preview URLs. A preview URL is a different origin, so it cannot sign in against the production API (CORS and cookies). Use staging variables for previews.

### 2.3 Tighten the CSP after the API domain is known

Edit the `connect-src` directive in `frontend/vercel.json`:

```
connect-src 'self' https://<api domain> wss://<api domain>
```

Keep `img-src ... https:` while signed Supabase Storage URLs are used for avatars and attachments, or narrow it to `https://<project-ref>.supabase.co`. Verify in the browser console that no `Content-Security-Policy` violation appears while signing in, chatting and uploading.

### 2.4 Verify the build locally before pushing

```powershell
scripts\verify-hosted-build.ps1 -ApiUrl https://api.example.com
```

It checks that a hosted build without an API URL, or with an http URL, is refused; that a valid build compiles the URL in; and that the bundle contains none of the backend secret names.

## 3. Backend

### 3.1 What is configured in the repository

| Concern | Where | Behaviour |
|---|---|---|
| Image | `backend/Dockerfile` | `python:3.12-slim`, pinned requirements, non-root user, no tests or `.env` in the image (`.dockerignore`) |
| Server | `CMD` | `uvicorn app.main:app --workers 1 --proxy-headers --no-server-header`, graceful shutdown 20 s, port from `PORT` (default 8000) |
| Preflight | `python -m app.preflight`, run before the server | Refuses to start on an unsafe hosted configuration. Prints setting names only, never values |
| Proxy trust | `FORWARDED_ALLOW_IPS` | uvicorn only believes `X-Forwarded-For` from these addresses. Per-IP rate limits and audit rows depend on it |
| CORS | `CORS_ORIGINS` | Exact origins, wildcard rejected at startup, credentials allowed for those origins. WebSocket upgrades check `Origin` against the same list |
| Body limits | `app/core/body_limit.py` | 1 MB default, 64 KB webhooks, 3 MB avatar, 11 MB attachments. Larger or oversized chunked bodies get 413 |
| Headers | `app/core/middleware.py` | `nosniff`, `no-referrer`, `X-Frame-Options: DENY`, HSTS when cookies are secure |
| Logging | `app/core/logging.py` | One JSON object per line on stdout, with `request_id`. No bodies, tokens, or unmasked phone numbers. Exceptions are logged by type only |
| Health | `/healthz` (liveness), `/readyz` (503 when the database is down) | Also under `/api/v1/health` and `/api/v1/health/ready` |
| Workers | `SMS_WORKER_ENABLED`, `NOTIFICATIONS_WORKER_ENABLED` (default true) | Run inside the API process. No separate worker service is needed |
| Database | `DATABASE_URL` | Async SQLAlchemy pool. Prepared statements are off, so the Supabase transaction pooler works |
| API docs | disabled when `APP_ENV=production` | `/docs`, `/redoc` and the OpenAPI file are not served |

### 3.2 Database connection

Use the Supabase **Connect** panel. Prefer the **Session pooler** or the **Direct connection** (port 5432). The transaction pooler (port 6543) also works. Create a dedicated Postgres role for the backend if you can; the backend must read and write `public` tables and read `auth.users`. Keep `DB_POOL_SIZE + DB_MAX_OVERFLOW` below the plan's connection limit. Supabase requires TLS; the application does not yet enforce it itself (audit finding SEC-014), so confirm that the connection string comes from Supabase and not an unencrypted proxy.

### 3.3 Build, run and test the image

```powershell
docker build -t chikka-reborn-backend:<version> backend
# Smoke test with a throwaway, non-secret configuration:
docker run --rm -p 8000:8000 -e APP_ENV=staging -e APP_SECRET_KEY=<32+ chars> `
  -e DATABASE_URL=... -e SUPABASE_URL=... -e SUPABASE_ANON_KEY=... -e SUPABASE_SERVICE_ROLE_KEY=... `
  -e CORS_ORIGINS=https://app.example.com -e FRONTEND_BASE_URL=https://app.example.com `
  chikka-reborn-backend:<version>
```

If the preflight prints `BLOCKING:` lines the container exits 1 before serving. That is intended.

The image has not been built in this repository's working environment (no Docker daemon was running). The first build on your CI or host is the first test of the Dockerfile.

### 3.4 Hosting platform settings

Whatever the platform, set:

| Setting | Value |
|---|---|
| Build | Dockerfile at `backend/Dockerfile`, build context `backend/` |
| Instances | 1 (see section 1) |
| Health check path | `/readyz` (or `/healthz` if you want the instance to stay in rotation during a database outage) |
| Custom domain | `api.<your domain>`, HTTPS only, HTTP redirected |
| Idle/WebSocket timeout | at least 60 s |
| Environment | every variable in `backend/production.env.example`, in the platform's secret store |
| `FORWARDED_ALLOW_IPS` | the platform proxy's address range from its documentation. Use `*` only when the container is reachable solely through that proxy |
| Deploy hook | manual, from a tagged commit (section 6) |

### 3.5 Webhook endpoints

| Provider | Direction | URL |
|---|---|---|
| Twilio | Inbound SMS | `POST https://<api domain>/api/v1/webhooks/twilio/inbound` (set in the Twilio console) |
| Twilio | Delivery status | `POST https://<api domain>/api/v1/webhooks/twilio/status?sms_id=<id>` (sent per message by the backend; nothing to configure) |

`SMS_PUBLIC_BASE_URL` must equal the public origin exactly as Twilio calls it, because Twilio signs the full URL. Details: [twilio-configuration.md](twilio-configuration.md). In simulation mode the webhook route is `/api/v1/webhooks/mock/*` and is signed by an in-process key; the `twilio` route returns 404 until live mode is on.

## 4. Supabase, SMS, AI

These have their own documents because each has approval gates:

- Supabase project, migrations, redirect URLs, RLS verification, storage: [supabase-setup.md](supabase-setup.md).
- Twilio account, sender, country rules, signature validation, test procedure: [twilio-configuration.md](twilio-configuration.md). **Live SMS stays off** (`SMS_PROVIDER_MODE=mock`) until that document's gates are met.
- Amazon Bedrock access, region, IAM, limits: [bedrock-setup.md](bedrock-setup.md). The first deployment can run `AI_PROVIDER_MODE=mock`.

## 5. Order of operations for a first deployment

1. Supabase project created and configured; migrations applied to **staging** first (approval needed for production).
2. Backend deployed to staging with simulation providers. Smoke test (section 7).
3. Frontend staging deployed against the staging API. Smoke test again, including sign-up by email, chat between two accounts, and a simulated SMS.
4. Repeat for production with the production Supabase project.
5. Only then, and only with the written approvals described in the Twilio and Bedrock documents, switch a provider to live.

## 6. Releases

- Tag the commit (`v0.x.y`). Build the image from the tag. Record the image tag and the Vercel deployment URL in the release notes.
- Migrations are applied by a person, never by the deploy: see [supabase-setup.md](supabase-setup.md) section 3. Use expand-then-contract changes so the previous backend version keeps working against the new schema, which is what makes rollback possible.
- Order: migration (additive) -> backend -> frontend. Reverse for removals.
- Rollback: [rollback-procedure.md](rollback-procedure.md).

CI is not yet defined in the repository (no `.github/workflows`). `scripts\check.ps1` runs the same lint, type, test and build steps locally. Add CI before the first production release so the checklist's test gates are enforced automatically.

## 7. Smoke tests after a deployment

Run in order against the deployed URLs. Record each result with the date, the URL and the request ID of any failure.

| # | Check | Expected |
|---|---|---|
| 1 | `GET https://<api>/healthz` | 200, `"status":"ok"` |
| 2 | `GET https://<api>/readyz` | 200, `"database":"ok"` |
| 3 | `curl -I https://<api>/healthz` | `strict-transport-security`, `x-frame-options: DENY`, `x-request-id` present; no `server` header |
| 4 | `GET https://<api>/docs` (production) | 404 |
| 5 | `GET https://<api>/api/v1/users/me` without a token | 401 with the error envelope |
| 6 | Preflight: container log shows `preflight ok` | present, no `BLOCKING` |
| 7 | CORS: `curl -i -X OPTIONS https://<api>/api/v1/auth/login -H "Origin: https://evil.example" -H "Access-Control-Request-Method: POST"` | no `access-control-allow-origin` header |
| 8 | CORS from the real origin: same request with `Origin: https://<app>` | `access-control-allow-origin: https://<app>` and `allow-credentials: true` |
| 9 | Open `https://<app>/`, then reload on `/login` | SPA loads, deep link does not 404 |
| 10 | `curl -I https://<app>/` | CSP, HSTS, `x-frame-options` present |
| 11 | Register a test account | Confirmation email arrives from Supabase (check spam), link opens `https://<app>/auth/verify-email?...` and signs in |
| 12 | Reload the page while signed in | Stays signed in (proves the cookie is sent: same-site domains) |
| 13 | Two accounts chat | Message arrives in real time (proves WebSocket and `Origin` check) |
| 14 | Upload an avatar and an attachment | Both display (proves Storage and signed URLs) |
| 15 | Simulated SMS to `+12025550100` | Shows SIMULATED, reaches `delivered` through a signed mock callback |
| 16 | Unsigned POST to `/api/v1/webhooks/twilio/status` | 404 in simulation, 403 `invalid_signature` in live |
| 17 | Password reset email | Link opens `https://<app>/auth/reset-password?...`, sets a new password, other sessions end |
| 18 | Audit and logs | Logs are JSON with `request_id`; no email, phone number or token appears |

A deployment is "verified" only when every row has a recorded result. Mark rows that could not be run as not verified rather than passed.

## 8. Revision History

| Version | Date | Notes |
|---|---|---|
| 1.0 | November 2026 | Initial draft (architect) |
| 2.0 | November 2026 | Rewritten for the implemented system: one worker, same-site domains, preflight, real vercel.json, smoke tests. Replaces the stale Dockerfile (`main:app`, two workers), CSP and `/health` examples |

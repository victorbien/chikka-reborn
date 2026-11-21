# Deployment Checklist

Use one copy per deployment. Record who ticked each box, the date and the evidence (URL, log line, screenshot). A box that could not be checked stays open and is written up as "not verified".

**Environment:** staging / production **Version tag:** ______ **Image tag:** ______ **Vercel URL:** ______ **Operator:** ______ **Approver (production):** ______

## A. Approvals (production only)

- [ ] Named person approved this production deployment (name, date)
- [ ] Approved the production migration push, if any migrations are new
- [ ] Live SMS: separate written approval, or confirmed **off**
- [ ] Anything with real cost (Twilio funds, Bedrock, SMTP volume): approved, or confirmed off

## B. Source and secrets

- [ ] Working tree is the tagged commit; `git status` clean
- [ ] `git grep` for credential patterns finds nothing; `.env` files are not tracked (`git ls-files | Select-String "\.env"` lists only `.env.example` files)
- [ ] Secrets exist only in the Vercel project (public values only) and the backend secret store
- [ ] Secrets that were ever shared or once sat in a tracked file are rotated (see test-report DEF-01)
- [ ] `pip-audit -r backend/requirements.txt` and `npm audit --omit=dev` show no high or critical findings

## C. Tests and builds

- [ ] Backend: `pytest` passes, `ruff check`, `ruff format --check`, `mypy app` clean
- [ ] Frontend: `eslint`, `prettier --check`, `tsc --noEmit`, `vitest --run` pass
- [ ] SQL: `node supabase/tools/run-db.mjs --tests` ends `ALL OK`
- [ ] `scripts\verify-hosted-build.ps1` ends `ALL OK`
- [ ] Playwright journeys pass on the release candidate (`scripts\e2e-browser.ps1`)
- [ ] Docker image builds from `backend/Dockerfile` and starts with the target configuration

## D. Supabase

- [ ] Correct project (staging vs production) confirmed by project ref
- [ ] Backups on, PITR on (production); restore point time noted: ______ UTC
- [ ] Migrations applied in order (list the last one): ______
- [ ] `20261120000001` follow-up: legacy `avatar_path` rows cleared, constraint validated
- [ ] RLS verification queries (supabase-setup.md section 4) all return zero rows
- [ ] Buckets `avatars` and `message-attachments` exist, private, no client policies
- [ ] Auth: Site URL, redirect URLs, templates, custom SMTP, confirmation on
- [ ] Data API disabled or exposing no schema (SEC-002)

## E. Backend

- [ ] All variables from `backend/production.env.example` set; no placeholder left
- [ ] `APP_ENV` is `staging` or `production`; `APP_SECRET_KEY` 48+ random characters, unique per environment
- [ ] `CORS_ORIGINS` lists only the real app origin(s), https
- [ ] `FRONTEND_BASE_URL` equals the app origin; app and API share a registrable domain
- [ ] `FORWARDED_ALLOW_IPS` set to the platform proxy; one instance
- [ ] HTTPS enforced on the API domain (HTTP redirects or is refused)
- [ ] Container log shows `preflight ok` and no `BLOCKING`
- [ ] `/healthz` and `/readyz` return 200; platform health check uses `/readyz`
- [ ] Platform WebSocket idle timeout is 60 s or more
- [ ] Logs reach the log service; a sample line has `request_id` and no personal data

## F. Frontend

- [ ] Vercel root directory `frontend`; `VITE_API_BASE_URL` and `VITE_APP_ENV` set for this environment
- [ ] Custom domain with HTTPS; same registrable domain as the API
- [ ] CSP `connect-src` tightened to the API origin; no CSP violations in the browser console
- [ ] `curl -I` shows CSP, HSTS, `x-frame-options`, `nosniff`; assets are `immutable`, HTML is `no-cache`

## G. SMS (all environments)

- [ ] `SMS_PROVIDER_MODE=mock` and `SMS_LIVE_CONFIRMED=false`, **or** every gate in twilio-configuration.md section 0 is ticked
- [ ] If live: sender registered per country, consent flow reviewed, webhook URL set on each sender number, `SMS_PUBLIC_BASE_URL` exact, unsigned webhook returns 403, one approved test message verified end to end, pause switch located

## H. AI

- [ ] `AI_PROVIDER_MODE=mock`, **or** bedrock-setup.md section 6 is complete (model access, least-privilege key with an expiry, AWS budget alert)

## I. Privacy and legal (production)

- [ ] Terms and Privacy Notice published and linked from the sign-up form (SEC-009)
- [ ] Retention jobs exist or the gap is accepted in writing (SEC-007)
- [ ] Data export and deletion position decided and documented (SEC-008)

## J. Smoke tests

- [ ] All 18 rows of deployment-guide.md section 7 have a recorded result

## K. After deployment

- [ ] Alerts from monitoring-and-logging.md section 10 are active and one test alert fired
- [ ] Rollback target recorded: previous image tag ______, previous Vercel deployment ______
- [ ] Release notes list the deployed URLs and the verification results, including anything not verified

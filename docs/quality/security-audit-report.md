# Security and Privacy Audit Report

**Date:** 20 November 2026
**Scope:** `backend/`, `frontend/`, `supabase/` (migrations, seed, SQL tests) and the documentation in `docs/`, at the current working tree.
**Method:** source review, targeted probes against a locally built app, dependency audits, secret scans of the working tree and all 16 commits, and the existing SQL, backend and E2E test suites. No hosted environment, live provider or third-party service was tested.

This report is an engineering review. It is not a legal or standards assessment and does not claim compliance with any law or standard (for example the Philippine Data Privacy Act, GDPR, OWASP ASVS or ISO 27001). Privacy findings below identify engineering gaps only; whether they matter legally needs a separate assessment by qualified people.

## 1. Summary

| Severity | Found | Fixed in this change | Open |
|---|---|---|---|
| Critical | 0 | 0 | 0 |
| High | 1 | 1 | 0 |
| Medium | 8 | 0 | 8 |
| Low | 6 | 0 | 6 |

The authentication, authorisation, SMS, AI and database designs are mostly sound. The one High finding (SEC-001) let a signed-in user make the backend sign a storage URL for an object outside their own avatar folder. It is fixed in code and in a new migration. The migration is tested locally and has not been applied to any hosted database.

### Evidence for what held up

| Area | What was checked | Result |
|---|---|---|
| Authentication enforcement | Every OpenAPI operation was called without a token on a locally built app | 102 of 115 return 401. The rest are the 4 health checks, 6 public auth endpoints, `/auth/refresh` (403 without the CSRF header) and the 2 webhook routes (signature-authenticated) |
| Token verification | `core/security.py` | Algorithm is bound to key type, audience required, `exp`/`sub`/`session_id` required, issuer checked for ES256/RS256. Session liveness and account status are re-read from the database on every request |
| Roles | `api/deps.py`, `modules/admin/*`, `private.is_admin()` | Role comes from `profiles`, never from JWT claims. All admin routes use `AdminUserDep`. Denials are audited. Admins cannot restrict themselves or other admins |
| RLS | All 30 tables in `supabase/migrations` | Every table has RLS enabled. Clients have column-level grants only, `anon` has none, server-only tables have no client grants. `supabase/tests/database/*.test.sql` passes (`node run-db.mjs --tests`) |
| SQL injection | Every `text(f"...")` in repositories | Interpolated parts are constants, allow-listed column names or generated placeholders. Values are bound parameters. LIKE patterns are escaped |
| Webhooks | `modules/sms/webhooks.py`, `integrations/sms/twilio.py` | Signature checked on raw bytes before parsing, constant-time compare, URL built from configuration, fails closed, events de-duplicated by provider ID, 64 KB cap |
| Idempotency | `modules/sms/service.py` | Unique key per sender, request hash conflict returns 409, concurrent duplicates resolved through the unique constraint |
| Opt-out and consent | `modules/sms/service.py`, `webhooks.py` | STOP keywords recorded globally per number, checked on every send, consent required per recipient where the country needs it |
| AI | `modules/ai/*` | System prompts are constants, user content is JSON data, context is limited, masked and labelled, output is parsed and bounded, nothing is sent without user action, prompts and drafts are not logged or stored (only a hash) |
| Secrets | Working tree and `git rev-list --all` | No credential-shaped strings in tracked files or history. `.env` files are git-ignored. `.env.example` is blank |
| Dependencies | `npm audit --omit=dev`; `pip-audit -r requirements.txt --no-deps` | 0 known vulnerabilities in both. Transitive Python packages were not audited |
| Frontend rendering | Search for `dangerouslySetInnerHTML`, `innerHTML`, `eval`, web storage | None in application code. Access token is held in memory, refresh token is an httpOnly cookie. External links use `rel="noreferrer noopener"` |
| Uploads | `chat/attachments.py`, `profiles/avatar.py` | Type from content signature, Pillow decode, pixel limits, size limits, EXIF stripped for static images, private buckets |

## 2. Findings

### SEC-001 (High, fixed): Client-writable avatar path can sign or delete other storage objects

- **Description:** `profiles.avatar_path` was writable by any signed-in user through the Supabase Data API (column grant) and had no format constraint. The backend passed the stored value to `StorageProvider.signed_url()` and `delete()` using the service-role key. The HTTP client collapses `..` segments, so a path such as `../message-attachments/<conversation_id>/<file>.pdf` addressed a different bucket, and `<other_user_id>/<file>.webp` addressed another user's photo.
- **Affected component:** `supabase/migrations/20261110000002_profiles.sql` (grant), `backend/app/integrations/storage_provider.py`, and the avatar signing and deletion code in `modules/profiles`, `modules/contacts`, `modules/chat` and `modules/auth/account_service.py`.
- **Risk:** An attacker who knows an object path could obtain a signed download URL for a private chat attachment, or read another user's photo regardless of that user's profile visibility. Replacing their own avatar afterwards would make the backend delete the previously stored object, which could destroy another user's file. Paths are random but are known to current and former conversation members, and attachments deleted for everyone stay in storage.
- **Verification (before the fix):** As user A call the Data API: `PATCH /rest/v1/profiles?id=eq.<A>` with `{"avatar_path": "../message-attachments/<conversation_id>/<file>.pdf"}`, then `GET /api/v1/users/me`. `avatar_url` would be a signed URL for that object. I confirmed the path collapse locally (`httpx.Request("POST", ".../sign/avatars/..%2F...")` resolves to `/sign/message-attachments/...`) and the grant in the migration. I did not run the full chain against a hosted Supabase project.
- **Remediation applied:**
  1. `app/core/storage_paths.py` adds `owned_avatar_path()`, which accepts only `<owner_id>/<32 hex>.webp`. All avatar signing and deletion go through it, so a malformed or foreign path means "no avatar".
  2. `SupabaseStorageProvider` rejects empty, absolute, backslash and `.`/`..` segments for every upload, delete and sign call.
  3. Migration `20261120000001_profiles_avatar_path_guard.sql` revokes `UPDATE (avatar_path)` from `authenticated` and adds `ck_profiles_avatar_path`. The constraint is `NOT VALID` so existing rows do not block the migration. Operators should list and null any legacy violations, then run `validate constraint` (query is in the migration header).
- **Tests:** `backend/tests/unit/test_storage_paths.py` (traversal, foreign folder, wrong extension, provider makes no HTTP call for a bad path), `supabase/tests/database/04_rls_isolation.test.sql` (client update is refused). Full backend suite: 697 passed, 2 skipped (Twilio credentials). SQL tests: all pass. Ruff and mypy clean.
- **Still required:** apply the migration to staging, then production, with approval.

### SEC-002 (Medium, open): Supabase Data API and Auth are reachable without the backend

- **Description:** The design routes all writes through FastAPI, but `authenticated` users hold direct column grants and `public_profiles` is selectable, and Supabase Auth accepts sign-ups directly with the public anon key. Direct calls skip backend rate limits, input cleaning, consent capture and audit logging.
- **Affected component:** `supabase/migrations/*` (grants, `public_profiles` view), `supabase/config.toml` (`[auth] enable_signup = true`), hosted project settings.
- **Risk:** (a) A signed-in user can page through `public_profiles` and collect usernames, display names, avatars and countries of every account with visibility `everyone`, without the 20 per minute search limit. (b) `display_name`, `bio` and `status_message` can be written without `clean_text`. React escapes output, so this is not a script risk in the SPA, but the values appear in notification emails and titles. (c) Accounts created straight through Auth have no terms or privacy consent row.
- **Verification:** With a valid user JWT and the anon key, `GET {SUPABASE_URL}/rest/v1/public_profiles?select=*&limit=1000`. Check the hosted project's API settings for exposed schemas. Not run against a hosted project.
- **Remediation:** Disable the Data API for this project, or expose no schema, since the frontend uses no Supabase client (`frontend/package.json` has none). Revoke the remaining client write grants once the Data API is off or unneeded. Create users only through the backend (service-role admin create) or add a before-user-created Auth hook that records consent. Keep RLS as the second layer.

### SEC-003 (Medium, open): No request body size limit

- **Description:** Nothing caps request bodies globally. Starlette reads the whole body before Pydantic validates it. Only the webhook route checks `Content-Length`, and a chunked body skips that check because `request.body()` reads everything first. Multipart uploads are spooled before the 10 MB read cap applies.
- **Affected component:** `app/main.py`, `app/core/middleware.py`, `modules/sms/webhook_router.py`, `modules/chat/router.py`.
- **Risk:** An unauthenticated client can send a very large body to `/auth/login`, `/auth/register` or a webhook and exhaust memory or disk.
- **Verification:** Send a multi-hundred-megabyte `POST /api/v1/auth/login` with `Transfer-Encoding: chunked` and watch process memory.
- **Remediation:** Add an ASGI middleware that counts streamed bytes and returns 413 (for example 64 KB for JSON and webhooks, 12 MB for the two upload routes). Also set the reverse proxy's body limit.

### SEC-004 (Medium, open): Client IP trust depends on undocumented proxy settings

- **Description:** Per-IP limits for login, registration, reset and SMS use `request.client.host`. The documented container command (`docs/deployment-strategy.md`, `docs/deployment/deployment-guide.md`) is `uvicorn main:app --host 0.0.0.0 --workers 2` with no `--proxy-headers` or `--forwarded-allow-ips`. The module path in those documents (`main:app`) also differs from the code (`app.main:app`).
- **Affected component:** `api/deps.py` (`get_request_meta`), deployment docs.
- **Risk:** Behind a load balancer every client appears as the balancer. Twenty failed logins from anywhere then lock sign-in for everyone for 15 minutes (`LOGIN_PER_IP`). If the setting is widened to trust any forwarder, a client can spoof its IP and dodge every per-IP limit.
- **Verification:** In staging, send requests through the proxy with different `X-Forwarded-For` values and read the audit rows' `ip_prefix`.
- **Remediation:** Document and set `--proxy-headers --forwarded-allow-ips=<proxy address>`. Add a startup check or health detail that warns when all requests share one address.

### SEC-005 (Medium, open): Webhook rate limit runs before signature verification

- **Description:** `WebhookService.handle` counts a per-IP hit (600 per minute) before it verifies the signature.
- **Affected component:** `modules/sms/webhooks.py`.
- **Risk:** With SEC-004 unresolved, unsigned traffic can use up the shared budget and make genuine Twilio callbacks return 429. Delivery receipts and STOP replies would be delayed.
- **Verification:** Send 601 unsigned POSTs to `/api/v1/webhooks/twilio/status` from one address, then a correctly signed one.
- **Remediation:** Verify the signature first (it is cheap and uses no database), then rate limit only valid or repeated-invalid sources. Add a network allow-list or provider IP check at the proxy.

### SEC-006 (Medium, open): Browser security headers are mostly absent

- **Description:** The API sets only `X-Content-Type-Options` and `Referrer-Policy`. The frontend has no `vercel.json`, no `<meta>` policy and no headers config, so no Content-Security-Policy, `frame-ancestors`/`X-Frame-Options`, HSTS or `Permissions-Policy`.
- **Affected component:** `app/core/middleware.py`, `frontend/index.html`, deployment configuration.
- **Risk:** No second line of defence against XSS from a future bug, and the app can be framed (clickjacking on actions such as send or delete).
- **Verification:** `curl -I` the deployed SPA and API and list the headers.
- **Remediation:** Add `frontend/vercel.json` headers: CSP (`default-src 'self'`, `connect-src` for the API and WebSocket, `img-src` for the Storage host, `frame-ancestors 'none'`), HSTS, `Permissions-Policy`. Add HSTS and `Cache-Control: no-store` on API responses with tokens.

### SEC-007 (Medium, open): Retention rules exist in the schema but no job enforces them

- **Description:** `provider_webhooks.purge_after` and `audit_logs.retain_until` default to 90 days. The table comment says a scheduled job purges them, but no job exists in the backend or `supabase/`. Raw inbound SMS (full text and unmasked sender number) stay in `provider_webhooks` indefinitely. Expired notifications, AI assistance logs and read attachments have no purge either.
- **Affected component:** `supabase/migrations/20261110000008_message_deliveries.sql`, `20261110000011_ai_reports_audit.sql`, backend workers.
- **Risk:** Personal data is kept longer than the stated policy. The unmasked sender numbers and message bodies in a server-only table are the most sensitive.
- **Verification:** `select count(*) from public.provider_webhooks where purge_after < now()` on a long-running database. Search the repository for a scheduler (none found).
- **Remediation:** Add an idempotent purge worker (or `pg_cron` migration) per data type, run it with the service role, audit each run, and document the periods in `docs/`. Delete the SMS body from `raw_payload` once an event is processed if the 90-day raw copy is not needed.

### SEC-008 (Medium, open): No data export, and account deletion leaves authored content

- **Description:** The privacy module (Module I) has no export endpoint. Account deletion scrubs the profile, releases phone numbers and ends sessions, but keeps messages the user wrote (shown as "Deleted user"), SMS conversations, consent rows and ledger rows. The docstring says the auth email is replaced, and `disable_user` is documented to do so, which I did not verify against Supabase. Avatar deletion that fails is only logged ("purge pending") and no job picks it up.
- **Affected component:** `modules/auth/account_service.py`, `modules/privacy` (absent), `integrations/auth_provider.py`.
- **Risk:** Users cannot get their data, and message bodies and SMS content remain after deletion with no stated basis or period.
- **Verification:** Delete a test account, then read `messages` and `auth.users` for that user ID. Search for an export route (none in the 115 operations).
- **Remediation:** Decide and document what is kept and why. Add an authenticated, rate-limited export (profile, contacts, messages, SMS, consents) and a deletion option for authored content. Add the avatar purge to the SEC-007 job.

### SEC-009 (Medium, open): Terms and Privacy Notice are accepted but not published

- **Description:** The sign-up form says "I accept the Terms of Service and the Privacy Notice", and the backend records `terms` and `privacy` consent with version `2026-11-01`. The frontend has no Terms or Privacy Notice page or link, and `docs/` has none.
- **Affected component:** `frontend/src/features/auth/components/RegisterForm.tsx`, routes.
- **Risk:** The consent record points at documents users cannot read, so it does not show informed acceptance.
- **Verification:** Open the register page and look for a link. Search `frontend/src/routes`.
- **Remediation:** Publish both pages (reviewed by someone qualified), link them from the form and footer, and tie `TERMS_VERSION` and `PRIVACY_VERSION` to the published text. Show a re-acceptance prompt when the version changes.

### SEC-010 (Low, open): HS256 tokens are accepted without an issuer check

- **Description:** With the legacy shared secret the issuer is `None`, so `iss` is not checked. Audience and signature are.
- **Affected component:** `core/security.py` (`_verification_key`).
- **Risk:** Low. Only the project's own secret signs these tokens. It matters if the secret is reused across projects.
- **Verification:** Sign an HS256 token with the secret and a foreign `iss`; it is accepted.
- **Remediation:** Pass `settings.auth_issuer` for HS256 as well when `SUPABASE_URL` is set. Prefer moving to asymmetric signing keys and removing `SUPABASE_JWT_SECRET`.

### SEC-011 (Low, open): Unauthenticated information disclosure

- **Description:** `/api/v1/health`, `/healthz` and `/readyz` return environment name, version and SMS mode. OpenAPI and `/docs` are on in every environment except `production`, including `staging`.
- **Affected component:** `schemas/health.py`, `core/config.py` (`docs_enabled`).
- **Risk:** Helps targeting. Staging may hold realistic data.
- **Verification:** `curl` the endpoints without a token.
- **Remediation:** Return only `status` on public health routes. Enable docs only for `development` and `test`.

### SEC-012 (Low, open): Attachment hardening gaps

- **Description:** Animated images (GIF, animated PNG or WebP) are stored as uploaded, so EXIF and location metadata remain. PDFs are checked by signature only and are served through signed URLs that the SPA opens in a new tab.
- **Affected component:** `modules/chat/attachments.py`, `frontend/.../AttachmentView.tsx`.
- **Risk:** Location metadata can reach the recipient. A malicious PDF reaches the recipient's viewer. The private bucket and short signed URLs limit exposure to conversation members.
- **Verification:** Upload a GIF with a metadata block and download it.
- **Remediation:** Strip metadata from animated formats, serve downloads with `Content-Disposition: attachment` and `Content-Type` fixed from the stored type, and consider malware scanning before enabling PDFs in production.

### SEC-013 (Low, open): Phone-number ownership can be probed

- **Description:** Starting verification for a number already verified by another account returns `409 phone_unavailable`. The same number on a free account returns success.
- **Affected component:** `modules/auth/phone_service.py`.
- **Risk:** A signed-in user can learn whether a number is registered. Limited by 3 code requests per 30 minutes per user, but registered-number enumeration remains.
- **Verification:** Request a code for a number known to be verified elsewhere and compare the responses.
- **Remediation:** Return the same response in both cases and send the owner a notice, or accept the exposure and document it.

### SEC-014 (Low, open): Database TLS is not enforced by the application

- **Description:** `database/session.py` does not set `ssl` in `connect_args`. TLS depends on the driver default and the host.
- **Affected component:** `app/database/session.py`.
- **Risk:** A misconfigured or non-Supabase host could be reached unencrypted.
- **Verification:** Run with `DATABASE_URL` pointing at a Postgres that allows non-TLS and check `pg_stat_ssl`.
- **Remediation:** Require TLS outside development (`ssl="require"` or a verified context).

### SEC-015 (Low, open): Real credentials sit in two local env files

- **Description:** The root `.env` and `backend/.env` hold real values, including the service-role key and database URL. Both are git-ignored and absent from all 16 commits. `docs/quality/test-report.md` (DEF-01) records an earlier case where real values were in `.env.example`, with rotation recommended. I could not tell from the repository whether rotation happened.
- **Affected component:** local workspace, `.env`.
- **Risk:** Low in the repository. Duplicated secrets raise the chance of accidental sharing or a stray backup.
- **Verification:** `git check-ignore -v .env backend/.env`, `git log --all -- .env`, and the secret-pattern scan in section 1.
- **Remediation:** Keep secrets in one file or a secret manager, confirm the DEF-01 rotation, and rotate again if either file was ever shared.

## 3. Items reviewed with no finding

- **Session management:** logout, global sign-out, revoke-other and password reset end sessions and live WebSockets. Refresh cookie is httpOnly, path-scoped, `SameSite=Lax` and needs a custom header (CSRF).
- **Password reset:** neutral responses, per-IP and per-email limits, one-time link, all sessions revoked afterwards, security notification created.
- **OTP:** 6 digits from `secrets`, keyed hash, 10 minute expiry, 5 attempts, 60 second resend, per-user limits, codes never logged. In simulation mode the code is shown to the requester by design and is labelled SIMULATED, and a simulated verification does not unlock live sending.
- **Conversation membership:** every read and write calls a membership check and returns the same 404 for "not yours" and "does not exist". Attachments can only be linked by their uploader to the same conversation.
- **Contact privacy:** lookup by email, number or username returns the same empty result for missing, private, undiscoverable or blocked accounts, and is limited to 20 per minute through the API (see SEC-002 for the Data API path).
- **SMS abuse and destinations:** E.164 validation, country capability checks, hourly, daily, per-IP and per-recipient limits, sender verification, global pause, and live mode needing both configuration and a typed environment confirmation.
- **Credentials in the browser:** none. Provider secrets are `SecretStr`, backend-only.
- **Error handling:** one error envelope, no stack traces, validation errors omit submitted values, log formatter writes the exception type only.
- **CORS:** explicit origins only (wildcard rejected), credentials allowed for those origins, WebSocket checks `Origin`.

## 4. Not assessed

- The hosted Supabase project (Data API exposure, Auth settings, storage policies, backups, TLS), the hosting platform, the reverse proxy and DNS.
- Live Twilio and Bedrock behaviour, and the email provider.
- Penetration testing, load testing, transitive Python dependencies, and browser-side behaviour of the built bundle.
- Accessibility, and any legal or regulatory conformity.

## 5. Recommended order of work

1. Apply `20261120000001` to staging, validate legacy rows, then production (approval required).
2. SEC-002 and SEC-004: lock down the Data API and Auth sign-up, and set proxy trust. These change what an attacker can reach.
3. SEC-003, SEC-005, SEC-006: body limit, webhook ordering, headers.
4. SEC-007 to SEC-009: retention job, export and deletion policy, published notices.
5. Low findings.

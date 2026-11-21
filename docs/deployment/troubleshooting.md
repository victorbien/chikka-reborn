# Troubleshooting Guide

Every API error response carries `request_id` and the same ID is in the server log line for that request (`X-Request-ID` header too). Start there: ask the user for the ID, then search the logs for it.

## 1. The backend will not start

The container prints the reason and exits 1. The preflight prints setting **names**, never values.

| Message | Cause | Fix |
|---|---|---|
| `BLOCKING: DATABASE_URL is not set` (or another `... is not set`) | Missing secret | Add it in the platform secret store, redeploy |
| `BLOCKING: APP_ENV must be 'staging' or 'production'` | Variable missing or `development` | Set `APP_ENV` |
| `BLOCKING: CORS_ORIGINS contains a non-https or local origin` | `localhost` or `http://` origin left in | List only real https origins |
| `BLOCKING: FRONTEND_BASE_URL's origin is not listed in CORS_ORIGINS` | Mismatch (path, `www`, port) | Make the origin identical, scheme and host included |
| `BLOCKING: COOKIE_SECURE=false ...` | Override left from local development | Unset `COOKIE_SECURE` |
| `configuration is invalid: app_secret_key: ...` | `APP_SECRET_KEY` missing or under 32 characters | Generate 48+ characters |
| `... SMS_PROVIDER_MODE=live requires SMS_LIVE_CONFIRMED=true` | Live requested without operator confirmation | Intended. Confirm per environment, or set `mock` |
| `... SMS_PROVIDER_MODE=live requires TWILIO_ACCOUNT_SID, ...` | Missing live credentials | Add them, or set `mock`. It never falls back to simulation |
| `... AI_PROVIDER_MODE=bedrock requires BEDROCK_...` | Missing Bedrock settings | Add them, or set `mock` |
| `CORS_ORIGINS must list explicit origins; '*' is not allowed` | Wildcard | List origins |
| Starts, then health check fails | Wrong `PORT`, or the platform probes a different path | Probe `/healthz` on the injected `PORT` |

## 2. Users cannot stay signed in

Symptom: sign-in works, a reload signs the user out (or `POST /auth/refresh` returns 401/403).

1. **Different registrable domains** (for example `*.vercel.app` and `*.onrender.com`). The `SameSite=Lax` refresh cookie is not sent. Put both on subdomains of one domain you own.
2. **403 `csrf_required`:** the request lacks `X-Chikka-CSRF: 1`. Usually a proxy or CDN stripping custom headers, or an old frontend build. Check the request in the browser network tab.
3. **Cookie not stored:** the API response is over http (TLS terminated incorrectly), or `COOKIE_SECURE` forces secure on an http origin. The API must be reached over https.
4. **CORS preflight failing:** `CORS_ORIGINS` does not exactly match `Origin`. Credentials require an explicit origin.
5. Cookie `Path` is `/api/v1/auth`, so a platform that adds a path prefix to the API breaks it. Serve the API at the root of its domain.

## 3. Browser shows CORS errors

- The failing origin must be in `CORS_ORIGINS` exactly (scheme, host, port; no trailing slash).
- A 413, 429, 5xx or a platform-level error page also appears as a CORS error if it did not come from the app. Check the status in the network tab and the response headers for `x-request-id`; if it is missing, the response came from the proxy, not FastAPI.
- Preview deployments have other origins and will not work against the production API. Use the staging environment for previews.

## 4. Real-time chat does not update

| Check | Meaning |
|---|---|
| WebSocket closes at once | The `Origin` is not in `CORS_ORIGINS`, or auth failed (token expired, account not active or onboarded) |
| Connects, drops after about a minute | Platform idle timeout is below 60 s, or the proxy does not forward upgrade headers |
| Works for some users only | More than one backend instance. Real-time pushes only reach clients on the same instance. Run one |
| `wss://` fails, `ws://` impossible | `VITE_API_BASE_URL` must be https; the WebSocket URL is derived from it |

The REST API is the source of truth: reloading shows messages even when the socket is down.

## 5. Everyone gets 429 "Too many sign-in attempts"

All requests appear to come from one address, so the per-IP limits (20 failed sign-ins per 15 minutes, webhooks 600 per minute) hit everyone. Set `FORWARDED_ALLOW_IPS` to the platform proxy addresses so `X-Forwarded-For` is trusted. Verify with audit rows (`ip_prefix` should vary) after two requests from different networks. Wait 15 minutes or clear the counters (`rate_limit_counters`, with approval) to recover.

## 6. Emails do not arrive, or links go to the wrong place

Sign-up confirmation and password reset are sent by **Supabase Auth**, not by the backend.

- Not arriving: custom SMTP is not configured (the default sender is for testing and heavily limited), the sender domain lacks SPF/DKIM, or the message is in spam.
- Link goes to `localhost`: Supabase **Site URL** is wrong.
- "Redirect URL not allowed": add `https://<app>/auth/verify-email` and `/auth/reset-password` to Supabase Redirect URLs.
- Link opens the app but verification fails with "invalid or expired": links are single-use and expire after an hour; email scanners that pre-open links can consume them. Request a new one.
- Notification emails (not auth) come from the backend: `EMAIL_PROVIDER_MODE=mock` sends none.

## 7. Database

| Symptom | Cause / fix |
|---|---|
| 503 `database_not_configured` | `DATABASE_URL` empty. Preflight should have caught it |
| `/readyz` 503, `/healthz` 200 | Database unreachable. Check Supabase status, credentials, connection limit (`DB_POOL_SIZE + DB_MAX_OVERFLOW` per instance), IP restrictions |
| `prepared statement ... does not exist` | A pooler in transaction mode and a changed driver setting. The code disables the statement cache; do not re-enable it |
| `permission denied for table/column` after a migration | A grant or policy was missed. Compare with `supabase/tests/database` and the RLS verification queries |
| Backend works locally, fails on the host with TLS errors | Wrong connection string host. Copy it from Supabase Connect |

## 8. SMS

| Symptom | Cause / fix |
|---|---|
| Messages stay `queued` | `SMS_WORKER_ENABLED=false`, the worker crashed (check logs for `worker`), or sending is paused (SMS administration) |
| 503 `sms_mode_mismatch` | Environment says one mode, the active provider row in the database says another. An administrator activates the matching provider |
| 503 `live_not_confirmed` | Live mode without an operator confirmation recorded. Use the activate endpoint with the environment name |
| 503 `sms_unconfigured` | No active provider row |
| 422 `consent_required` | The sender has not confirmed permission for that recipient |
| 422 `recipient_opted_out` | The recipient sent STOP. Cannot be overridden by the sender |
| Country unavailable | The capability row is not verified/supported. Publish a verified version (twilio-configuration.md section 5) |
| 503 `sender_capacity` | Not enough sender numbers for concurrent conversations with that country |
| Webhook 403 `invalid_signature` | `SMS_PUBLIC_BASE_URL` differs from the URL Twilio calls (scheme, host, port, path, or a proxy rewriting it), wrong Auth Token (subaccount mix-up), or the body was altered by a proxy |
| Webhook 503 `webhook_unavailable` | Validation could not run. Check the Twilio secret. It fails closed on purpose |
| Webhook 404 | The route's provider is not the running one (`twilio` route in simulation mode, or `mock` in live mode) |
| Delivered never appears | Delivery receipts are not available on that route. The UI shows "sent, delivery unconfirmed". Never mark delivered by hand |
| Replies land in "unrouted" | No active reply route for that (platform number, sender). Review in SMS administration; inbound is kept 90 days, never shown to users |

## 9. AI

| Symptom | Cause / fix |
|---|---|
| 502 `ai_unavailable`, log `bedrock error` status 403 | Key invalid or expired, model not enabled in that region, or IAM lacks `bedrock:InvokeModel` for that model or inference profile |
| 502 with status 429 | Throttled. Lower the request rate or raise the Bedrock quota |
| 502 timeouts | Raise `AI_TIMEOUT_SECONDS` (max 60) or choose a faster model |
| 403 `ai_not_enabled` | The user has not turned the assistant on |
| 503 `ai_disabled_by_admin` | `system_settings.ai_enabled` is false |
| 429 on AI | Hourly per-user limit reached (default 30) |
| Backend refuses to start with `bedrock` | One of region, model ID, API key missing |

## 10. Uploads and images

- 413 `payload_too_large`: attachment over about 11 MB request size or avatar over 3 MB. The file limits are 10 MB and 2 MB.
- Avatar or attachment shows initials or a broken link: signed URLs expire; reload. If every image fails, check the buckets exist and are private, the service-role key is set, and the CSP `img-src` allows the Storage host. A log line `ignored malformed avatar path` means a stored `avatar_path` does not match `<user id>/<32 hex>.webp` and is deliberately ignored.

## 11. Frontend

| Symptom | Fix |
|---|---|
| Vercel build fails with `Invalid frontend environment configuration` | Set `VITE_API_BASE_URL` to an https public URL for staging and production builds |
| Blank page, console error about env | Same variable missing in a build that skipped the guard (check `VITE_APP_ENV`) |
| 404 on reload of a deep link | `vercel.json` rewrite not applied: confirm Root Directory is `frontend` |
| Old UI after a deploy | Browser cached `index.html`: it is `no-cache`, so check a CDN or service worker in front |
| CSP violation in console | Add the blocked origin to the right directive in `vercel.json`, rebuild |
| "Something went wrong" page | The error boundary caught a render error. The console shows only the error name and request ID |

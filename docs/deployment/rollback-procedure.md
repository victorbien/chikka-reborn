# Rollback Procedure

Decide quickly, act on the smallest piece that fixes the problem, then verify and write it up. Order of preference: **configuration switch, then frontend, then backend, then database**. The database is last because it is the only step that can lose data.

## 0. Triage (2 minutes)

| Symptom | First move |
|---|---|
| Real SMS going wrong (wrong recipients, duplicates, cost) | Section 4 immediately, before anything else |
| Users cannot sign in or the page is blank right after a frontend deploy | Section 1 |
| 5xx, failing health check or errors right after a backend deploy | Section 2 |
| Data wrong or missing after a migration | Section 3. Stop writes first |
| Secret exposed | Rotate it (section 6), then decide on a rollback |

Write down the time (UTC), the request IDs of failures and who is acting. Announce the rollback to the people involved.

## 1. Frontend (Vercel)

Vercel keeps every deployment, so this is instant and loses nothing.

1. Vercel -> Project -> Deployments -> choose the last known-good production deployment -> **Promote to Production** (or `vercel rollback <deployment url>`).
2. Verify: `curl -I https://<app>/` shows the old build's assets, sign in works, deep link reload works.
3. Note: rolled-back frontends talk to the current API. If the API change was not backward-compatible, roll back the backend too.

## 2. Backend

1. Redeploy the **previous image tag** on the platform (record it in the checklist before every release, section K). Do not rebuild from source during an incident.
2. Environment variables: if the failure follows a config change, restore the previous values from the platform's history and restart.
3. Verify: `/readyz` 200, container log `preflight ok`, smoke tests 1 to 8 and 12 to 13 in the deployment guide.
4. The previous backend must work with the current schema. That holds when the last migration was additive (expand-then-contract). If it was not, go to section 3.

## 3. Database

Never edit an applied migration. Roll forward when you can.

1. **Prefer a forward fix:** a new migration that reverses or repairs the change (for example re-adding a column, dropping a bad constraint). Test it on a throwaway database with `node supabase/tools/run-db.mjs --tests`, then on staging, then apply with approval.
2. **Point-in-time recovery** only for data loss or corruption, and only with approval from the owner, because it discards every write after the restore point for the restored database. Steps: pause writes (set the backend to maintenance by scaling it to zero, or enable SMS pause plus a platform maintenance page), note the target time from the checklist, restore to a **new** project or branch where the platform allows it, compare, then switch `DATABASE_URL` and the Supabase variables. Messages, credit ledger and audit rows written after the restore point are lost; reconcile them from provider logs (Twilio message log) afterwards.
3. Migration `20261120000001` specifically: if the avatar check rejects legitimate rows, drop only the constraint (`alter table public.profiles drop constraint ck_profiles_avatar_path;`) in a new migration, fix the data, and re-add it. Do **not** re-grant `UPDATE (avatar_path)` to `authenticated`: that reopens audit finding SEC-001.
4. After any database action, run the RLS verification queries in supabase-setup.md section 4 and the smoke tests.

## 4. SMS and AI switches (no deploy needed)

| Goal | Action | Effect |
|---|---|---|
| Stop all outbound SMS now | SMS administration -> **Pause all sending** (or `PUT /api/v1/admin/sms/outbound-paused` with `{"paused": true}`) | New sends are refused; queued messages wait |
| Leave live mode | Set `SMS_PROVIDER_MODE=mock`, `SMS_LIVE_CONFIRMED=false`, restart | Messages queued for the live provider are held, never sent through simulation, and expire to `failed` after `SMS_QUEUE_MAX_AGE_SECONDS` |
| Stop a compromised Twilio account | Suspend or rotate the Auth Token in the Twilio console, then update `TWILIO_AUTH_TOKEN` | Webhooks signed with the old token start failing, which is intended |
| Stop AI | Set `system_settings.ai_enabled` to false, or `AI_PROVIDER_MODE=mock` and restart | AI features report unavailable. Sending messages is unaffected |
| Stop a single abusive user | Admin -> restrict user | Sessions end and sign-in is blocked |

## 5. After the rollback

1. Run the smoke tests and record results.
2. Confirm no stuck work: SMS delivery health, unrouted inbound queue, notification backlog.
3. Check the credit ledger and message counts for the window of the incident.
4. Write a short incident note: timeline, cause, what was rolled back, data affected, follow-ups. Add a regression test for the cause.

## 6. Secret rotation

| Secret | Where to rotate | Then |
|---|---|---|
| Supabase service-role key | Supabase -> Settings -> API | Update backend secret, restart |
| Database password | Supabase -> Settings -> Database | Update `DATABASE_URL`, restart |
| `APP_SECRET_KEY` | Generate new | Update, restart. Pending phone codes and rate-limit counters reset; sessions are not affected |
| Twilio Auth Token | Twilio console | Update `TWILIO_AUTH_TOKEN`, restart. Webhook signatures use the new token at once |
| Bedrock API key | IAM -> the dedicated user | Generate new, update, restart, delete the old key |
| SMTP password | SMTP provider | Update, restart |

Rotate immediately if a value appears in a log, chat, ticket, screenshot or repository.

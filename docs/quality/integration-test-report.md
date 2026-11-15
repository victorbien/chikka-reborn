# Integration Test Report

Date: 15 November 2026. Scope: Phases 1 to 5 as implemented (auth, contacts, chat, SMS in simulation, AI, notifications, credits, administration, Classic and Modern modes).

## Summary

All five critical user journeys pass against the running system: real backend process, real PostgreSQL schema with every migration and RLS, the simulated SMS provider, the simulated AI provider, and the frontend's own API client, session store and real-time client. One usability defect was found and fixed, and one duplicate control was removed. Several gaps remain and are listed below, mainly that no browser (DOM) end-to-end suite exists.

| Suite | Command | Result |
|---|---|---|
| Backend unit, integration and flow tests (PGlite database, fake Supabase Auth and Storage) | `pytest` in `backend/` | 678 passed, 2 skipped (Twilio test credentials not configured) |
| Frontend unit and component tests | `npx vitest --run` in `frontend/` | 301 passed, 15 skipped (the live suites, which need a running stack) |
| Cross-stack journeys | `scripts/e2e-local.ps1` | 15 passed (5 journeys in `journeys.test.ts`, 10 auth and profile checks in `live-api.test.ts`) |
| Static checks | `ruff`, `mypy`, `tsc --noEmit`, `eslint`, `prettier --check` | Clean |

## How the journeys were run

`scripts/e2e-local.ps1` starts PGlite with all migrations, a fake Supabase Auth and Storage server, and `uvicorn app.main:app` in simulation mode. It then runs `frontend/src/test/live/` with a cookie-aware `fetch`, one `ApiClient` and `SessionStore` per simulated browser, and the real `RealtimeClient` over a WebSocket. Every person is a separate "browser" with its own cookies and token. Data is fictional.

## Journey results

| # | Journey | Result | What was verified end to end |
|---|---|---|---|
| 1 | New user | Pass | Register, sign-in refused until the email link is used, verify, profile starts un-onboarded, onboarding sets username and mode, dashboard queries (credits, notifications, unread, SMS status, contacts) all answer, the saved interface mode follows the user to a second device, global sign-out ends the other device and its session store becomes signed-out |
| 2 | Chikka messaging | Pass | Exact-username search, request, accept, both buddy lists, chat before acceptance refused, open conversation is idempotent, send, same client id does not duplicate, recipient receives `message.created` over the socket, unread count and a notification without message text, read marks clear the count, reply, sender receives the reply and `message.status_changed`, identical ordered history for both, a non-participant gets 404 or 403 |
| 3 | SMS | Pass | Mobile number verified through the simulated inbox, countries list, quote (segments, encoding, cost, balance, consent), send refused without consent, consent, same idempotency key sends once, status moves forward only through accepted and sent to delivered, the same changes arrive over the socket, demo credits fall by exactly the quoted cost, an administrator's simulated reply lands in the same SMS conversation as an unread simulated message with a notification |
| 4 | AI | Pass | AI is off until the user opts in, translate returns a draft and sends nothing, the draft is edited, the decision is recorded, the message is sent over the Chikka channel and no SMS exists, administrator AI metrics hold counts but not the text, reply suggestions send nothing |
| 5 | Administration | Pass | A message to the reserved failing number fails with a readable reason and a notification, credits are refunded and nothing stays reserved, a normal user gets 403 on the dashboard, the dashboard counts simulated and live apart, the SMS list masks numbers and hides bodies, message detail shows delivery attempts and the failure, provider overview exposes no secrets, the audit trail has the SMS records and the denied attempt, and holds no numbers or text |

## Integration requirements

| Requirement | Evidence |
|---|---|
| API contracts | A script compared every frontend API call with the generated OpenAPI paths: 98 calls matched, none without a backend route. Thirty frontend interfaces were compared with their response schemas: no frontend field is missing on the backend. Status and event names agree (chat `sent/delivered/read`, SMS `queued/retrying/accepted/sent/delivered/undelivered/failed/received`, notification types, real-time event types) |
| Authentication propagation | Token in memory, refresh cookie with CSRF header, refresh retry on 401, WebSocket first-frame auth, global sign-out ends other devices (journey 1, flow tests) |
| Database relationships and RLS | The flow tests run on a real PostgreSQL schema with every migration, including cross-user read and forged-row checks for profiles, contacts, chat and the audit log (I did not audit that every table has such a test) |
| Real-time events | Chat created, status changed, SMS created and updated, and notification events were received by a real client in journeys 2 and 3 |
| Provider integration | Simulation provider: signed inbound and status callbacks, replays, out-of-order and failure scenarios. Live Twilio paths run only against a faked Twilio in `test_sms_live.py`; the real Twilio test-credential tests are skipped |
| Error handling | Outage, rate-limit, lockout and rollback paths in `test_failure_paths.py`, plus the error envelope handling in the frontend tests |
| Notifications | New message, SMS reply, SMS failure and contact request notifications were seen by the recipient, without message text |
| Credit transactions | Spend equals the quote, duplicate sends charge once, failure refunds, nothing remains reserved |
| AI service integration | Opt-in, drafts only, metadata-only logging, provider outage leaves chat working |

## Defects found and fixed

| ID | Finding | Fix |
|---|---|---|
| IR-1 | The administrator's "Simulate a reply" form required the platform sender number, but the administrator only ever sees masked sender numbers, and the page text pointed to a "sender number shown on the conversation's route" that is not shown anywhere. The reply step of journey 3 could not be completed from the UI. | `to_number` is now optional on `POST /api/v1/admin/sms/simulate/inbound`. When omitted, the single active route for `from_phone` is used; `422 no_active_route` or `route_not_unique` otherwise. The form, schema and API type were updated, with backend and frontend tests and `docs/api/sms-api.md`. |
| IR-2 | Duplicate control: the interface mode could be set from the profile form's "Interface" select and from the new "Messenger style" section. After a header toggle the select showed a stale value. | The select was removed from the profile form. The header toggle and "Messenger style" are the two entry points and both save through one hook. |

## Open items (not fixed)

| ID | Item | Impact | Suggested action |
|---|---|---|---|
| IR-3 | There is no browser end-to-end suite. Playwright is not installed. The journeys above exercise the service layer, not the rendered pages, clicks or viewport behaviour. Component tests cover the UI against mocked HTTP. | The UI-to-API wiring of each page is verified only by component tests | Add Playwright (needs an ADR and a pinned version) and run the five journeys against the same local stack |
| IR-4 | No public landing page. `/` requires sign-in and redirects to the sign-in page. | Journey 1 step 1 opens the sign-in page | Decide whether a landing page is in scope; no document requires one |
| IR-5 | Backend endpoints with no frontend caller: administrator credit adjustments and per-user credit views, administrator notices, `PUT /admin/sms/capabilities/{country}` (capabilities are read-only in the UI), `GET /sms/capability`, `GET /sms/messages/{id}`. | Administrators need the API directly for these | Add UI when scheduled, or record them as API-only |
| IR-6 | `/admin/sms` is outside `AdminLayout`, so it has no administration tabs, repeats the role check, and requests monitoring data before the role is known. | Cosmetic; the backend still refuses non-administrators | Move the route under `AdminLayout` |
| IR-7 | Two frontend tests with 10 second budgets (`auth-pages` sign-in, `sms-pages` compose) failed once during a full run while stale background processes were using the machine, and passed when re-run. | Possible flake on slow machines | Raise the timeouts or speed up those tests if it recurs in CI |
| IR-8 | The database is PGlite and Supabase Auth and Storage are a test double. Behaviour that depends on real Supabase (email delivery, JWT signing keys, Storage policies, Realtime) is not exercised. | Environment differences may appear on first deployment | Run the same journeys against a Supabase staging project |
| IR-9 | Live SMS (Twilio) and live AI (Bedrock) were not exercised against the real services. | None in simulation; required before production | Run with Twilio test credentials and a Bedrock key when available |

## Not claimed

The application should not be treated as production-ready on this evidence alone. The journeys pass in simulation mode, on a local stack, through the service layer. IR-3, IR-8 and IR-9 need to be closed before the journeys count as verified in a browser and on the real services.

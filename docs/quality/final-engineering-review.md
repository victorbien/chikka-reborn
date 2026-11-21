# Final Engineering Review

Review date: 22 November 2026. Reviewer: independent pass over the working tree at commit `a1f9c5a` plus uncommitted changes (logo assets, `AppLayout.tsx`, `AuthLayout.tsx`, `StyleGuide.tsx`, `index.html`, `backend/app/integrations/ai/base.py`).

## 1. Verdict

**Not production-ready. Ready for a simulation-mode demo and for a staging deployment with simulated SMS and AI.**

The code is well structured and well tested. Live SMS and Bedrock have never been exercised against the real services, nothing has been applied to a hosted Supabase project, and several MUST requirements are not built. Those gaps are listed below and are not hidden by the passing test counts.

How evidence was gathered: I ran the suites listed in section 3 myself. Everything marked "not re-verified" is taken from the project's own reports (`docs/quality/*.md`) and from reading code, not from running it.

## 2. Feature classification

| Feature | Class | Basis |
|---|---|---|
| Registration, verification, login, lockout, reset, sessions, logout | Complete (against a fake Supabase Auth) | Tests pass. Real GoTrue never exercised |
| Social login (FR-A-003, SHOULD) | Not implemented | Documented in `module-a-auth.md` |
| Profile, avatar, presence, privacy, account deletion | Complete | Deviations documented |
| Mobile number verification | Simulated | OTP shown in a SIMULATED panel. Live delivery returns 503 |
| Contacts: discovery, requests, groups, favourites, blocking | Complete | |
| SMS contacts (FR-B-002, MUST) | Partially complete | SMS recipients are handled through the SMS module. The contact-list integration is documented as "not yet" |
| Contact mute, import | Not implemented | |
| Chikka-to-Chikka chat: send, history, receipts, typing, unread, attachments, archive | Complete | WebSocket gateway, single backend instance only |
| Message delete (FR-C-005, SHOULD), edit, pin | Not implemented | No endpoint and no UI |
| Outbound SMS in simulation | Simulated (complete) | Mock provider, SIMULATED labels, zero real cost |
| Outbound SMS live (Twilio) | Blocked by external configuration | Tested only against an in-process fake Twilio. Sandbox test skipped. Philippine sender registration not verified |
| Inbound SMS and delivery callbacks | Complete in simulation. Live unverified | Signature check on raw bytes, dedupe, unrouted queue |
| Consent, opt-out (STOP/START), country capabilities | Complete | Philippines is seeded as `not_registered` with a DB check constraint |
| Credits ledger (reserve, deduct, refund, release) | Complete for the demo ledger | Simulated credits only. Live ledger and top-up not built |
| Credit top-up (FR-H-004, SHOULD, Phase 4) | Not implemented | Documented as out of MVP |
| AI assistant (replies, translate, rewrite, tone, summary, SMS optimise, compose) | Simulated | Default and only exercised provider is the mock |
| Bedrock integration | Blocked by external configuration | Adapter exists and is unit-tested with stubs. Never called |
| Notifications (in-app, email, browser) | Partially complete | Browser notifications use the in-page Notification API. There is no Web Push, so nothing arrives when the tab is closed. Email is mock by default |
| Data export (FR-I-002, MUST) | Not implemented | No endpoint, no UI, no documentation of a manual process |
| Message reporting (FR-I-004, MUST) | Partially complete | `abuse_reports` table, RLS and admin counts exist. No endpoint or UI creates a report |
| Admin dashboard, users, SMS monitoring, providers, capabilities, audit log | Complete | 10 admin and 8 SMS-admin routes |
| Classic and Modern Mode | Complete | Mode stored in `localStorage` |
| Internationalisation (Phase 5) | Not verified | Translation of messages exists. I did not audit UI translation |
| Accessibility | Partially complete | No automated axe scan. Manual assistive-technology testing not done |

## 3. Test results (run by me)

| Suite | Result |
|---|---|
| Backend `pytest` with coverage | 717 passed, 2 skipped, 0 failed, 93% line coverage (7 min) |
| Ruff lint and format | Clean (186 files) |
| mypy (strict) | No issues in 142 source files |
| Frontend `vitest --run` | 319 passed, 15 skipped, 0 failed |
| Frontend coverage | 89.8% lines, 87.9% statements, 79.2% branches |
| `tsc --noEmit`, ESLint | Exit 0 for both |
| Database SQL tests (`supabase/tools`, `npm test`) | All 17 migrations applied, all 5 SQL test files pass |
| Playwright browser suite (Chromium) | 48 passed, 0 failed (3.8 min). First attempt was blocked by a process on port 5173. Re-run after the port was free |

Skipped tests:

- 2 backend tests need Twilio test credentials.
- 15 frontend tests in `src/test/live/` need a running stack. The project says they pass under `scripts/e2e-local.ps1`. I did not run that.

Coverage against the testing rules: backend overall (93%) and business logic pass. `modules/sms/webhooks.py` is 77%, `modules/sms/gateway.py` 79% and `app/preflight.py` 65%. The first is status-transition logic, which needs 85%. Frontend (89.8%) passes the 70% floor.

## 4. Requirements traceability matrix

The routes are the actual FastAPI routes under `backend/app/modules/*`. Tests are in `backend/tests/{unit,flows,integration}`, `frontend/src/**/*.test.tsx`, `frontend/e2e/*.e2e.ts` and `supabase/tests/database`. I mapped at module level and spot-checked the named requirements. I did not trace every acceptance criterion to an individual test.

| Req | Implementation | API | Frontend | Automated tests | Status |
|---|---|---|---|---|---|
| FR-A-001, 002, 004, 005, 006, 009 | `modules/auth` | `/auth/*` (login, logout, verify-email, resend-verification, reset-password, sessions) | `features/auth` | Backend flows, `auth.e2e.ts` (4) | Complete |
| FR-A-003 | None | None | None | None | Not implemented |
| FR-A-007 | `modules/profiles` | `/profile` | `features/profile` | Backend, `profile.e2e.ts` (4) | Complete |
| FR-A-008 | `modules/profiles`, `integrations/otp_delivery.py` | `/profile/phone`, `/profile/phone/verify` | `PhoneSection.tsx` | Backend, `profile.e2e.ts` | Simulated |
| FR-B-001, 003, 004 | `modules/contacts` | `/contacts*`, `/contacts/blocks` | `features/contacts` | Backend, `contacts.e2e.ts` (3) | Complete |
| FR-B-002 | `modules/sms` (recipient handling) | `/sms/*` | `features/sms` | Partial | Partially complete |
| FR-B-005 | `modules/contacts` | `/contacts/groups*` | `features/contacts` | Backend | Complete |
| FR-C-001, 002, 004, 006 | `modules/chat` | `/conversations*` | `features/chat` | Backend flows, `chat.e2e.ts` (4) | Complete |
| FR-C-003 | `api/websocket.py`, `chat.typing` | `/ws/v1` | `features/chat` | Backend | Complete (not persisted) |
| FR-C-005 | None | None | None | None | Not implemented |
| FR-D-001, 002, 003, 004, 005 | `modules/sms/service.py`, `engine.py`, `segments.py` | `/sms/quote`, `/sms/messages*`, `/sms/conversations*` | `features/sms` | `test_sms.py`, `sms.e2e.ts` (5) | Complete in simulation |
| FR-E-001, 002, 003 | `modules/sms/webhooks.py`, `webhook_router.py` | `/webhooks/{provider}/inbound`, `/status` | `features/sms` | `test_sms*.py`, `security.e2e.ts` | Complete in simulation. Live unverified |
| FR-F-001 to 006 | `modules/ai`, `integrations/ai` | `/ai/*` | `AiAssistantPanel.tsx` | `test_ai*.py`, `ai-assistant.test.tsx`, `ai.e2e.ts` (3) | Simulated |
| FR-G-001, 003 | `modules/notifications` | `/notifications*` | `features/notifications` | Backend, `notifications.e2e.ts` (2) | Complete |
| FR-G-002 | In-page Notification API | `/notifications/preferences` | `features/notifications` | Component tests | Partially complete (no Web Push) |
| FR-H-001, 002, 003 | `modules/credits` | `/credits`, `/credits/transactions` | `features/credits` | Backend ledger tests, SQL `03_credits_ledger` | Complete (simulated ledger) |
| FR-H-004 | None | None | None | None | Not implemented |
| FR-I-001 | `modules/profiles` | `/profile/privacy` | `features/profile` | Backend, SQL RLS | Complete |
| FR-I-002 | None | None | None | None | Not implemented |
| FR-I-003 | `modules/sms/optout.py` | `/sms/consents`, webhook | `features/sms` | `test_sms.py` | Complete |
| FR-I-004 | Table and RLS only | None | None | SQL RLS only | Partially complete |
| FR-J-001 to 005 | `modules/admin`, `sms/admin_*` | `/admin/*`, `/admin/sms/*` | `features/admin` | `test_admin_access.py`, `admin.e2e.ts` (2) | Complete |
| FR-K-001, 002, 003 | Frontend only | None | `ClassicMessenger.tsx`, `AppLayout.tsx` | `modes.e2e.ts` (3), component tests | Complete |

## 5. Code quality

Strengths:

- Layering follows the architecture rules: router, service, repository, with provider interfaces in `integrations/`. Provider selection is in one factory (`integrations/sms/factory.py`).
- No `any`, no `eslint-disable` in the frontend. mypy strict and Ruff are clean. Only 30 `type: ignore` or `noqa` markers in `backend/app`.
- Errors use one envelope. Bedrock errors are mapped to coarse codes and never logged with content.

Weaknesses:

- Large service files: `contacts/service.py` (819 lines), `sms/service.py` (757), `sms/engine.py` (691), `chat/service.py` (686). They are cohesive but near the point where they should be split.
- `services/` and `repositories/` at `app/` level hold only the health check, next to the per-module layout. This is minor duplication of structure.
- Several frontend features have one test file each (`admin`, `ai`, `credits`, `notifications`, `profile`, `contacts`), so component-level coverage depends on a few broad files.
- Raw SQL via `text()` is used throughout the repositories. I saw bound parameters, but I did not audit every query.
- I did not review the uncommitted change to `integrations/ai/base.py`.

## 6. Database

- 30 tables, 17 migrations. All 30 have `enable row level security`. Six tables have no policies (`audit_logs`, `message_delivery_events`, `provider_webhooks`, `rate_limit_counters`, `sms_opt_outs`, `system_settings`), which means deny-all to clients. This matches the rule that server-only tables allow no client access.
- Constraints include a Philippines check (`ck_sms_cap_ph_registration`), idempotency and one-ledger-entry-per-message unique indexes, and an avatar path guard.
- The SQL tests cover constraints, messaging, credits, RLS isolation, and attachment RLS. They ran on in-process PGlite with a Supabase stub, not on hosted Supabase. Storage bucket policies were never exercised against real Supabase Storage.
- Migration `20261113000002` and `20261120000001` have not been applied to any hosted database.
- `system_settings` and `messaging_credits` have no secondary indexes. This is acceptable for single-row or primary-key access, and I did not check query plans.
- The `public_profiles` view and client write grants remain exposed through the Supabase Data API unless the project disables it (security audit, open finding).

## 7. SMS

- Abstraction: complete. `SmsProvider` implemented by `MockSmsProvider` and `TwilioSmsProvider`. Live mode raises `LiveSmsConfigurationError` and never falls back to the mock.
- Status semantics: `accepted` is never shown as delivered. Statuses `queued, retrying, accepted, sent, delivered, undelivered, failed` are documented and tested.
- Webhooks: signature validated on raw bytes before parsing, with deduplication, tested including invalid signatures.
- Credits: reservation, deduction on acceptance, refund on permanent failure, release on early failure. No charge in live mode from this ledger (live ledger not built).
- Consent and opt-out: enforced in the send pipeline (`blocked` reasons returned by `/sms/quote`). STOP-style keywords opt a number out for every user.
- Country capabilities: configured per country with versioning. The Philippines requires registered sender status.
- **Unverified:** real Twilio behaviour, delivery receipts per route, Philippine sender registration, and webhook signature validation against Twilio's actual URL handling behind a proxy.

## 8. AI

- Abstraction: `AiProvider` with `MockAiProvider` and `BedrockAiProvider`. Bedrock calls the Converse API over HTTPS with a backend-only API key.
- Prompts: system prompts are constants. Message content is passed as JSON data, and the prompt tells the model to treat it as data. One JSON-shaped answer is required.
- Human approval: all AI routes return drafts and say nothing is sent. The frontend panel has accept, edit and dismiss actions, covered by `ai-assistant.test.tsx`.
- Privacy: only a hash of prompts and drafts is stored. Per-user opt-in, off by default.
- SMS optimisation recomputes segment counts on the server (`modules/ai/service.py`) and rejects a rewrite that saves no segment.
- **Unverified:** real Bedrock output quality, latency and translation accuracy. Only canned mock output has been run end to end.

## 9. Documentation

| Item | Finding |
|---|---|
| README "Getting Started" status paragraph | **Stale.** It says built so far is Modules A, B and C, while the code includes SMS, AI, credits, notifications, admin and Classic Mode |
| `docs/quality/test-report.md` counts | **Stale.** It reports 681 backend and 329 frontend cases. I counted 719 and 334 |
| `docs/product/frs/module-a-auth.md` | States live mobile delivery is unavailable "until Phase 2". This contradicts the built SMS gateway and needs a status update |
| Environment variables | Documented in `docs/deployment/environment-configuration.md`. `.env.example` exists. No real secrets are tracked in git |
| Installation | `scripts/setup.ps1` and per-app READMEs exist. I did not run a clean-machine install |
| Known limitations | Documented well in `test-report.md` and `security-audit-report.md`, but not collected in one place. Section 11 below does this |
| API docs versus routes | `docs/api/*.md` exist for each module. I did not diff them route by route |
| Schema docs versus migrations | `supabase/tools` can regenerate the schema reference. I did not run it |
| Architecture diagrams | Not checked against code |

## 10. Outstanding defects

| ID | Severity | Defect |
|---|---|---|
| D-01 | High | FR-I-002 (MUST) data export is not implemented. Neither endpoint nor UI exists |
| D-02 | High | FR-I-004 (MUST) message reporting is half-built. Reports can never be created, yet the admin view counts them |
| D-03 | Low | Running `playwright test` directly fails when a dev server holds port 5173 (`reuseExistingServer: false`). `scripts/e2e-browser.ps1` frees the ports first and avoids this |
| D-11 | High (for submission) | No `LICENSE` file in the repository |
| D-04 | Medium | Migrations `20261113000002` and `20261120000001` are unapplied to hosted Supabase (needs human approval) |
| D-05 | Medium | Supabase Data API exposure of `public_profiles` and client grants (security audit finding, hosted settings) |
| D-06 | Medium | `modules/sms/webhooks.py` at 77% is below the 85% business-logic floor |
| D-07 | Low | README and test report are stale (section 9) |
| D-08 | Low | Phone-number enumeration through the verification flow (security audit finding) |
| D-09 | Low | `npm audit` reports 16 issues in build and lint tooling. Fixes are breaking (`vite@6`) |
| D-10 | Low | Starlette deprecation warning for `httpx` with its test client (2 warnings in pytest) |

## 11. Known limitations

- SMS is simulated end to end. Live Twilio has never run against a real account.
- AI is simulated end to end. Bedrock has never been called.
- Auth is tested against a fake Supabase Auth, not real GoTrue.
- The WebSocket hub and presence registry are in memory, so only one backend instance is supported.
- Notifications reach only open tabs. No Web Push.
- No message deletion or editing, no SMS contacts in the buddy list, no contact mute or import, no social login, no top-up or billing.
- No load, soak or latency testing. No automated accessibility scan. Chromium is the only browser tested.
- Account deletion erases personal fields immediately, with no reactivation grace.

## 12. Technical debt register

| ID | Item | Cost of leaving it |
|---|---|---|
| T-01 | Single-process realtime hub and presence | Blocks horizontal scaling |
| T-02 | Large service modules (contacts, sms, chat, engine) | Slower review and change |
| T-03 | `app/services` and `app/repositories` beside module layout | Confusing structure |
| T-04 | Live ledger and billing absent | Live SMS cannot be charged |
| T-05 | Docs drift (README, test report, FRS status) | Misleading for reviewers |
| T-06 | Hosted-environment checks never done (RLS, Storage, GoTrue) | Unknown behaviour at deployment |
| T-07 | No performance test automation | Capacity unknown |
| T-08 | Test timing relies on a 1 s worker poll and 45 s allowances | Flaky on slow machines |
| T-09 | Vite config imports without a file extension (warning with native config loader) | Breaks when Vite changes its default |

## 13. Deployment readiness

| Target | Assessment |
|---|---|
| Local demo, simulation mode | Ready |
| Staging with simulated SMS and AI | Ready after applying migrations to a staging Supabase project and verifying RLS and Storage there |
| Staging with live SMS | Blocked: Twilio account, public webhook URL, `SMS_LIVE_CONFIRMED`, operator confirmation, and a Philippine sender registration |
| Production | Not ready. Needs items 1 to 7 in section 14, plus human approval for production migrations |

## 14. Recommended improvements, in priority order

1. Build data export (D-01) and the message-report endpoint and UI (D-02), or formally downgrade both MUSTs in `frs.md` with a decision-log entry.
2. Apply all migrations to a hosted staging Supabase project and run the RLS, Storage and GoTrue checks there. Disable or restrict the Data API (D-04, D-05).
3. Run the Twilio sandbox test with test credentials, then one operator-approved live send to a number you control.
4. Run one real Bedrock session per AI feature and review output quality, segment re-checking and failure fallback.
5. Document `scripts/e2e-browser.ps1` as the way to run the browser suite (D-03).
6. Raise `webhooks.py` coverage to 85% (D-06).
7. Update README, `test-report.md` and the module A status notes (D-07, T-05).
8. Add Web Push, or state clearly in the UI that notifications need an open tab.
9. Move presence and the WebSocket hub to shared infrastructure before running more than one backend instance.
10. Add an axe scan to Playwright and a basic load test for send and webhook paths.

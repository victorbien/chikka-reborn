# Testing Strategy

> **SUPERSEDED (November 2026).** Retained for history. The canonical version is in docs/quality/testing-strategy.md and quality/test-plan.md. Requirement IDs here use the older scheme (e.g. FR-A-001); see the 'Was:' fields in docs/product/functional-requirements.md for the mapping.

**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Date:** November 2026  

---

## 1. Testing Philosophy

Testing is not an afterthought. Tests are written alongside feature implementation, not after. The goal is to give the team confidence to change the codebase quickly without introducing regressions.

Core principles:
- **Test behaviour, not implementation.** Tests verify what the system does, not how it does it internally.
- **Determinism first.** Every test must produce the same result every time it runs, regardless of order, time, or external state.
- **Isolate external dependencies.** No test should call real SMS providers, real AI models, or production databases.
- **Fast feedback.** Unit and integration tests must complete in under 2 minutes in CI.
- **Honest coverage.** Coverage metrics are a guide, not a target to game. Untested critical paths are the risk — not a low percentage number.

---

## 2. Testing Layers

The strategy uses four testing layers, each with a distinct purpose.

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: End-to-End Tests (Playwright)                     │
│  Simulates a real user in a real browser                    │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: API Integration Tests (Pytest + TestClient)       │
│  Tests full request/response cycle with mocked providers    │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Service / Unit Tests (Pytest)                     │
│  Tests business logic in isolation                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Component Tests (React Testing Library)           │
│  Tests UI components in isolation                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Testing (Python / Pytest)

### 3.1 Tools

| Tool | Purpose |
|---|---|
| `pytest` | Test runner and assertion framework |
| `pytest-asyncio` | Async test support for FastAPI handlers |
| `httpx` + FastAPI `TestClient` | HTTP-level integration tests |
| `pytest-cov` | Coverage measurement |
| `factory-boy` | Test data factories (model instances) |
| `unittest.mock` / `pytest-mock` | Mocking external dependencies |
| `faker` | Realistic fake data generation |

### 3.2 Test Directory Structure

```
backend/
└── tests/
    ├── conftest.py              # Shared fixtures: app, db session, auth tokens
    ├── factories/               # factory-boy model factories
    │   ├── user_factory.py
    │   ├── conversation_factory.py
    │   └── sms_factory.py
    ├── unit/                    # Pure business logic tests (no HTTP, no DB)
    │   ├── test_sms_segments.py
    │   ├── test_phone_validation.py
    │   ├── test_credit_calculations.py
    │   └── test_idempotency.py
    ├── services/                # Service layer tests (DB mocked or in-memory)
    │   ├── test_auth_service.py
    │   ├── test_message_service.py
    │   ├── test_sms_service.py
    │   ├── test_ai_service.py
    │   └── test_credit_service.py
    ├── api/                     # API integration tests (full request → response)
    │   ├── test_auth_routes.py
    │   ├── test_message_routes.py
    │   ├── test_sms_routes.py
    │   ├── test_webhook_routes.py
    │   ├── test_ai_routes.py
    │   ├── test_credit_routes.py
    │   └── test_admin_routes.py
    └── providers/               # Provider adapter tests (mock external APIs)
        ├── test_mock_sms_provider.py
        ├── test_twilio_provider.py    # Uses mocked Twilio HTTP responses
        └── test_bedrock_provider.py   # Uses mocked Bedrock responses
```

### 3.3 Test Fixtures

**Database:** Tests use an in-memory SQLite database (via SQLAlchemy async) or a dedicated Supabase test project. Each test function gets a fresh, isolated DB transaction that is rolled back at teardown.

**Authentication:** A `conftest.py` fixture creates signed test JWTs for different user roles (regular user, admin) without calling Supabase Auth.

**SMS Provider:** All tests use `MockSmsProvider` by default. Twilio provider tests mock the HTTP layer using `pytest-httpx` or `respx`.

**AI Provider:** All tests mock the Bedrock HTTP layer. No real AWS calls are made in tests.

### 3.4 Coverage Targets

| Area | Target |
|---|---|
| Business logic (services, utils) | ≥ 80% line coverage |
| Auth flow (login, register, OTP) | 100% branch coverage |
| SMS send flow (send, retry, refund) | 100% branch coverage |
| Credit deduction and refund | 100% branch coverage |
| Webhook signature validation | 100% branch coverage |
| AI feature endpoints | ≥ 80% line coverage |
| Admin endpoints | ≥ 70% line coverage |

### 3.5 Key Test Cases by Area

#### Authentication
- Register with valid credentials → 201
- Register with duplicate email → 422
- Register with weak password → 422
- Login with correct credentials → 200 + tokens
- Login with wrong password → 401 (generic message)
- 5 failed logins → 429 rate limit
- Expired JWT → 401
- Password reset link expires → 400

#### SMS Send Flow
- Send SMS with sufficient credits → 202, status `accepted`
- Send SMS with insufficient credits → 422 `INSUFFICIENT_CREDITS`
- Send SMS to unsupported country → 422 `SMS_COUNTRY_UNSUPPORTED`
- Send SMS to opted-out number → 422 `PHONE_OPTED_OUT`
- Send SMS in simulation mode → `is_simulated: true` in response
- Duplicate idempotency key → returns original response, no double send
- Provider transient error → retry scheduled
- Provider permanent failure → credits refunded, message `permanently_failed`

#### Webhook Processing
- Valid Twilio signature → webhook processed
- Invalid signature → 403, no processing
- Delivery status `delivered` → OutboundSms status updated
- Delivery status `failed` → OutboundSms status updated, credits refunded
- Inbound SMS matched to conversation → message stored
- Inbound SMS unmatched → logged, admin flagged

#### Credit Ledger
- Send SMS → credit reserved, then confirmed on acceptance
- Provider rejection → reserved credits released
- Permanent failure → full refund transaction created
- Credit balance never goes below 0

#### AI Features
- Smart reply request → 3 suggestions returned
- AI provider timeout → 502 with graceful error, message: does not block messaging
- AI response contains no message content in application logs

---

## 4. Frontend Testing (React Testing Library)

### 4.1 Tools

| Tool | Purpose |
|---|---|
| `vitest` | Fast test runner (Vite-native) |
| `@testing-library/react` | Component rendering and interaction |
| `@testing-library/user-event` | Realistic user interaction simulation |
| `msw` (Mock Service Worker) | API mocking at the network layer |
| `@testing-library/jest-dom` | Custom DOM matchers |

### 4.2 Test Structure

```
frontend/
└── src/
    └── features/
        └── {feature}/
            └── __tests__/
                ├── components/     # UI component tests
                └── hooks/          # Custom hook tests
```

### 4.3 What to Test

**Components:**
- Renders correctly with all states: loading, empty, success, error.
- Form validation shows correct errors on invalid input.
- Accessible: interactive elements have correct ARIA labels.
- User interactions trigger correct callbacks or state changes.

**Hooks:**
- Custom hooks return correct data shapes.
- Mutations call the correct API endpoints (mocked via MSW).

### 4.4 Key Frontend Test Cases

#### Auth
- Login form: empty submit shows field errors.
- Login form: invalid email shows format error.
- Login form: correct submission calls `/auth/login`.
- Registration form: password mismatch shows error.

#### SMS Compose
- Segment counter updates as user types.
- Credit cost updates with segment count.
- Send button disabled when credits insufficient.
- "SIMULATED" badge visible when `is_simulated: true`.
- Send button disabled until `idempotency_key` is set.

#### AI Assistant Panel
- Suggestions panel shows loading state during AI call.
- Accepting a suggestion populates compose field, does not send.
- Dismissing suggestions leaves compose field unchanged.
- AI failure shows error, compose field remains functional.

#### Conversation View
- Loading state shown while messages fetch.
- Empty state shown for new conversation.
- Incoming message appears without page refresh.
- Read receipt updates in real time.

### 4.5 What Not to Unit Test

- Third-party library internals (Supabase JS client, TanStack Query internals).
- Pure CSS/styling (covered by visual review and E2E).
- Trivial one-liner presentational components with no logic.

---

## 5. End-to-End Tests (Playwright)

### 5.1 Tools

| Tool | Purpose |
|---|---|
| `playwright` | Browser automation (Chromium, Firefox, WebKit) |
| Playwright fixtures | Shared setup: create test users, seed data |

### 5.2 Scope

E2E tests cover **critical user journeys** only. They are not exhaustive — that is the role of unit and integration tests. E2E tests are slow and flaky; keep them focused.

### 5.3 E2E Test Suites

#### Authentication Journey
1. New user: land on homepage → click Sign Up → fill form → submit → see verification prompt.
2. Returning user: navigate to /login → enter credentials → land on /app/messages.
3. Forgot password: click Forgot Password → enter email → submit → see confirmation.
4. Logout: click logout → redirected to /login → protected routes inaccessible.

#### Chikka-to-Chikka Messaging Journey
1. User A logs in, opens conversation with User B.
2. User A types a message and sends it.
3. User B's session shows the message delivered in real time.
4. User B replies.
5. User A sees the reply and read receipt.

#### Internet-to-SMS Journey (Simulation Mode)
1. User navigates to /app/sms/new.
2. Enters a valid phone number.
3. System shows capability info and credit cost.
4. User types message — segment counter updates.
5. User sends — response shows "SIMULATED" badge.
6. Delivery status progresses through simulated callbacks.

#### AI Assistant Journey
1. User opens a conversation with existing messages.
2. User clicks "Suggest Replies" — loading spinner shown.
3. Suggestions appear in panel.
4. User clicks a suggestion — it populates the compose field.
5. User edits the suggestion.
6. User explicitly sends — message appears in conversation.
7. AI badge is visible before send, not visible to recipient.

#### Credit Flow Journey
1. User views credit balance.
2. User attempts to send SMS with insufficient credits — send blocked.
3. (Phase 4) User completes top-up — balance updated.

### 5.4 E2E Environment

- Playwright tests run against a **staging environment** with a seeded test database.
- SMS is always in **simulation mode** in E2E tests.
- AI calls are intercepted using Playwright route mocking.
- Test users are created via a Playwright fixture that calls the test seed API.

---

## 6. CI/CD Integration

### Pull Request Pipeline

```
1. Lint and type check (ESLint, Ruff/mypy)
2. Backend unit tests (pytest)
3. Backend service tests (pytest)
4. Backend API integration tests (pytest)
5. Frontend component tests (vitest)
6. All must pass before merge is allowed
```

### Merge to Main Pipeline

```
1. All PR pipeline steps
2. Build frontend (Vite)
3. Build backend (Docker)
4. Deploy to staging
5. Run E2E tests (Playwright)
6. All must pass before production deployment is triggered
```

### Test Reporting

- Test results are reported in CI with pass/fail counts and duration.
- Coverage reports are generated by `pytest-cov` and uploaded to the CI artefacts.
- Playwright E2E failures include screenshots and video recordings.
- Flaky test detection: a test that fails in fewer than 2 of 5 retries is marked flaky and reported separately.

---

## 7. Security Testing

Beyond automated tests, the following security checks are performed:

| Check | When | Method |
|---|---|---|
| Dependency vulnerability scan | Every PR | `pip-audit` (backend), `npm audit` (frontend) |
| OWASP Top 10 review | Before each production deploy | Manual checklist |
| Webhook signature bypass test | API integration tests | Test with invalid signature → expect 403 |
| SQL injection (via ORM) | Unit tests | Parameterised queries are enforced by SQLAlchemy |
| XSS prevention | E2E tests | Playwright script injection tests |
| Rate limit enforcement | API integration tests | Exceed limit → expect 429 |
| JWT expiry enforcement | API integration tests | Expired token → expect 401 |

---

## 8. Test Data Management

- Test data is created fresh per test using factories (factory-boy for Python, Playwright fixtures for E2E).
- No shared mutable state between tests.
- Staging database is reset to a known seed state before each E2E run.
- Production data is never used in tests.
- Realistic-looking fake data (Faker library) is used instead of generic strings like `"test"` or `"foo"`.

---

## 9. What Is Explicitly Not Tested by Automation

| Area | Reason | Alternative |
|---|---|---|
| Real SMS delivery | Costs money; external dependency | MockSmsProvider in all automated tests |
| Real AI model quality | Model output is non-deterministic | Manual review of AI suggestions per release |
| Visual regressions | Not in scope Phase 1 | Manual UI review; consider Chromatic in Phase 3+ |
| Accessibility (full WCAG audit) | Requires assistive technology | Automated axe checks + manual review |
| Load and performance | Dedicated load test phase | Phase 6: k6 or Locust load tests |

---

## 10. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

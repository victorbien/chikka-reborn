---
inclusion: always
---

# Testing

Detailed docs: `docs/testing-strategy.md`, `docs/quality/test-plan.md`, `acceptance-criteria.md`, `security-test-plan.md`, `performance-test-plan.md`.

Write tests alongside each feature, not afterwards. Tests must be deterministic.

## Required Test Types

- Unit: services, utilities, validators, segmentation, state transitions (Pytest; Vitest/React Testing Library for components and hooks).
- Integration: API endpoints with a real test database, repositories, RLS policies, webhook handling with signature checks, background jobs.
- End-to-end: critical flows in Playwright (sign-up/login, chat, send SMS in simulation mode, receive simulated inbound SMS, delivery status display).

## Coverage Expectations

- Business logic (services, credits, status transitions, retry): at least 85% line coverage.
- Overall backend: at least 80%. Frontend features: at least 70%.
- Coverage is a floor, not a goal. Every acceptance criterion needs a test.
- Must-have cases: unauthorised access denied, invalid webhook signature rejected, duplicate idempotency key ignored, accepted is not shown as delivered, no credit charge for simulation, refund on permanent failure.

## Regression Testing

- Every fixed bug gets a test that fails without the fix.
- The full unit and integration suite runs on every pull request; E2E runs on main flows before release.

## Test Data and Mocking

- Use factories/fixtures with fake data only. Never real phone numbers or personal data.
- Never call real SMS, AI, or other external services in tests. Use `MockSmsProvider` and a fake `AiProvider`.
- Mock at the integration interface, not inside business logic.
- Tests are isolated: each sets up and cleans its own data. Freeze time and seed randomness (including retry jitter).
- Run commands: `pytest`, `playwright test`, and frontend `vitest --run` (never watch mode in automation).

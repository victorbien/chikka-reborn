---
inclusion: always
---

# Security

Detailed docs: `docs/architecture/security-architecture.md`, `docs/database/row-level-security.md`, `docs/quality/security-test-plan.md`.

## Authentication

- Supabase Auth issues sessions; the backend verifies the JWT on every protected request.
- Require email verification; support password reset and session revocation.
- Rate limit login, signup, reset, and verification endpoints.

## Authorisation

- Deny by default. Check ownership/role in the service layer for every resource access.
- Roles (user, admin) are enforced server-side. Never trust client-supplied user IDs or roles.
- Admin endpoints require the admin role and are audit-logged.
- Do not remove or weaken auth controls without explicit human approval.

## Row Level Security

- Every table has RLS enabled and policies defined in the same migration that creates it.
- Policies follow least privilege. Service-role keys are backend-only.
- Every table needs tests proving cross-user access is denied.

## Secrets Management

- All secrets (Supabase, Twilio, Bedrock, signing secrets) come from environment variables or a secret manager.
- Never commit secrets or `.env` files; provide `.env.example` with placeholders.
- Never place provider credentials in frontend code or logs. Rotate on suspected exposure.

## Webhook Verification

- Verify the provider signature on raw request bytes before any processing. Reject failures with 401/403 and log them.
- Never bypass verification, even in development. Simulation mode uses a mock signer.
- Validate payload schemas and deduplicate by provider event ID.

## Rate Limiting

- Apply per-user and per-IP limits on auth, SMS sending, AI endpoints, and webhooks. Return 429 with `Retry-After`.

## Audit Logging

- Log: auth events, SMS sends/inbound/status callbacks, credit changes, admin actions, consent and opt-out changes, data exports/deletions.
- Mask phone numbers (`+63****1234`). Never log message bodies, tokens, or secrets.
- Retain SMS audit logs at least 90 days.

## Data Retention and Deletion

- Define retention per data type in `docs/`. Collect only what is needed.
- Support account deletion and data export. Use soft delete (`deleted_at`) where audit needs it, then purge on schedule.
- Honour opt-outs permanently. Sanitise user content before storing or rendering. Use HTTPS everywhere.

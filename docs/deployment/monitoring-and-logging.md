# Monitoring and Logging

**Document:** CHKR-DEPLOY-004  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Defines the logging standards, monitoring strategy, alerting rules, and observability approach for Chikka Reborn.

## Scope

All environments. Monitoring infrastructure is introduced from Phase 2 (staging) and Phase 6 (full production monitoring).

---

## 1. Structured Logging (Backend)

All backend logs are emitted as **JSON** to stdout. The hosting platform captures and aggregates stdout.

### Log Format

```json
{
  "timestamp": "2026-11-09T12:00:00.123Z",
  "level": "INFO",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "a1b2c3d4-...",
  "service": "sms_service",
  "message": "Outbound SMS accepted by provider",
  "provider": "mock",
  "sms_id": "uuid",
  "duration_ms": 45
}
```

### Log Fields

| Field | Always Present | Description |
|---|---|---|
| `timestamp` | Yes | ISO 8601 UTC |
| `level` | Yes | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `request_id` | Yes | UUID from `X-Request-ID` header |
| `service` | Yes | Service name (e.g. `sms_service`, `auth_service`) |
| `message` | Yes | Human-readable event description |
| `user_id` | When authenticated | Masked if sensitive context |
| `duration_ms` | On completion | Request or operation duration |
| `error_code` | On errors | Structured error code (e.g. `INSUFFICIENT_CREDITS`) |

### PII Rules in Logs

| Data | Log Behaviour |
|---|---|
| Phone numbers | Masked: `+63****1234` (country code + last 4 digits) |
| Email addresses | Never logged |
| Message body | Never logged (AI or SMS content) |
| User display name | Not logged by default |
| IP addresses | Logged for rate limiting; not tied to user ID |

### Log Levels

| Level | Usage |
|---|---|
| `DEBUG` | Development only. Verbose trace of execution flow. |
| `INFO` | Normal operations: requests, SMS sent, user actions. |
| `WARNING` | Unexpected but recoverable: invalid webhook signature, retry triggered. |
| `ERROR` | Recoverable failures: provider timeout, DB constraint violation. |
| `CRITICAL` | System-level failures requiring immediate attention. |

Production runs at `INFO` level.

---

## 2. Request Logging

Every HTTP request is logged by the logging middleware:

```json
{
  "event": "request_completed",
  "method": "POST",
  "path": "/api/v1/sms/send",
  "status_code": 202,
  "duration_ms": 145,
  "request_id": "...",
  "user_id": "..."
}
```

Webhook endpoints log at WARNING level when signature validation fails:

```json
{
  "event": "webhook_signature_invalid",
  "level": "WARNING",
  "path": "/api/v1/webhooks/sms/status",
  "remote_ip": "54.172.xx.xx",
  "request_id": "..."
}
```

---

## 3. Application Events to Log

| Event | Level | Key Fields |
|---|---|---|
| User registered | INFO | user_id, timestamp |
| Login success | INFO | user_id |
| Login failure | WARNING | masked_email, attempt_count, ip |
| SMS sent (accepted) | INFO | sms_id, provider, is_simulated, segments |
| SMS delivery status update | INFO | sms_id, status, provider_status |
| SMS permanently failed | WARNING | sms_id, retry_count, credits_refunded |
| Inbound SMS received | INFO | matched (bool), from_phone (masked) |
| Webhook signature invalid | WARNING | path, remote_ip |
| AI request | INFO | feature, model_id, input_tokens, output_tokens, latency_ms, success |
| Credit deduction | INFO | user_id, amount, balance_after, reference_type |
| Credit refund | INFO | user_id, amount, balance_after, reason |
| Admin mode change | WARNING | admin_id, previous_mode, new_mode |
| Provider error | ERROR | provider, error_code, sms_id (if SMS) |

---

## 4. Health Checks

### Backend Health Endpoint

`GET /health` — no auth required. Checked every 30 seconds by the hosting platform.

```json
{
  "status": "healthy",
  "database": "connected",
  "sms_provider": "mock",
  "sms_provider_status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 86400,
  "timestamp": "2026-11-09T12:00:00Z"
}
```

If any critical dependency is unreachable, returns:
```json
{ "status": "unhealthy", "database": "error", ... }
```
with HTTP 503.

### Supabase Health

Supabase provides its own status page and uptime monitoring. Subscribe to status updates at `status.supabase.com`.

---

## 5. Alerting Rules (Phase 2+)

| Alert | Condition | Severity | Action |
|---|---|---|---|
| Backend unhealthy | `/health` returns non-200 for > 2 consecutive checks | Critical | Page on-call engineer |
| High 5xx rate | Error rate > 1% over 5 minutes | High | Notify engineering channel |
| SMS failure rate high | SMS permanent failure rate > 10% over 10 minutes | High | Notify engineering + operations |
| Credit anomaly | Single user deduction > 50 credits in 1 minute | High | Auto-flag for review |
| AI cost spike | AI token usage > 2× daily average | Medium | Notify engineering |
| Database connection exhaustion | Pool usage > 90% | High | Notify engineering |
| Staging E2E failure | Playwright E2E fails on merge to main | Critical | Block deployment |

Alerting tool: hosting platform native alerts (Render/Railway/Fly.io) or Better Uptime. Specific tool TBD.

---

## 6. Log Retention

| Environment | Retention |
|---|---|
| Development | Not aggregated; stdout only |
| Staging | 7 days |
| Production | 30 days (application logs) |
| SMS audit logs (DB) | 90 days minimum (per `docs/architecture/sms-gateway-architecture.md`) |
| AI usage logs (DB) | 90 days minimum |
| Credit transaction logs (DB) | Indefinite (financial ledger) |

---

## 7. Distributed Tracing (Phase 3+)

Once multi-service complexity increases, consider adding OpenTelemetry for distributed tracing:

- Every request gets a trace ID.
- Spans created for: HTTP handler, service calls, DB queries, provider calls.
- Traces exportable to Jaeger, Tempo, or a managed service.

This is deferred to Phase 3+ (ADL-pending). The `request_id` in current structured logs serves as a lightweight tracing mechanism for Phase 1–2.

---

## 8. Frontend Monitoring

### Vercel Analytics (Phase 1+)

Vercel provides Core Web Vitals tracking:
- LCP (Largest Contentful Paint)
- FID (First Input Delay)
- CLS (Cumulative Layout Shift)

Accessible from Vercel dashboard → Analytics.

### Error Monitoring (Phase 2+)

Consider Sentry for frontend error tracking:
- Captures unhandled React errors with component stack.
- Groups duplicate errors.
- Alerts on new error types or error rate spikes.

No user message content should be captured by Sentry. Configure `beforeSend` to strip message body fields from error payloads.

---

## 9. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

# Test Plan

**Document:** CHKR-QA-002  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Defines specific test cases for each product module. Covers happy paths, error paths, and boundary conditions. Aligned with functional requirements in `docs/product/functional-requirements.md`.

## Scope

Phase 1–3 test cases. Phase 4–6 cases to be added when those phases are planned.

---

## Module AUTH — Authentication

### Unit Tests

| ID | Test | Expected |
|---|---|---|
| UT-AUTH-001 | Register with valid email and strong password | User created, verification email queued |
| UT-AUTH-002 | Register with duplicate email | 409 CONFLICT (generic message) |
| UT-AUTH-003 | Register with weak password (< 8 chars) | 422 VALIDATION_ERROR |
| UT-AUTH-004 | Register with invalid email format | 422 VALIDATION_ERROR |
| UT-AUTH-005 | Login with correct credentials | 200 with access + refresh tokens |
| UT-AUTH-006 | Login with wrong password | 401 UNAUTHORIZED (generic) |
| UT-AUTH-007 | Login after 5 failed attempts | 429 RATE_LIMITED |
| UT-AUTH-008 | Use expired access token | 401 UNAUTHORIZED |
| UT-AUTH-009 | Use expired refresh token | 401 UNAUTHORIZED |
| UT-AUTH-010 | Password reset with registered email | 200 (always, no enumeration) |
| UT-AUTH-011 | Password reset with unregistered email | 200 (always, no enumeration) |
| UT-AUTH-012 | Confirm password reset with expired token | 400 |
| UT-AUTH-013 | Phone OTP — valid OTP | phone_verified: true |
| UT-AUTH-014 | Phone OTP — wrong OTP | 422 |
| UT-AUTH-015 | Phone OTP — expired OTP (> 10 min) | 400 |
| UT-AUTH-016 | Phone OTP — 4th attempt within 30 min | 429 |
| UT-AUTH-017 | Delete account with correct password | 202, sessions invalidated |
| UT-AUTH-018 | Delete account with wrong password | 401, account not deleted |

---

## Module CONTACTS

| ID | Test | Expected |
|---|---|---|
| UT-CONT-001 | Add Chikka user as contact | 201 contact created |
| UT-CONT-002 | Add self as contact | 422 |
| UT-CONT-003 | Add duplicate Chikka contact | 409 |
| UT-CONT-004 | Add SMS contact with valid E.164 | 201 |
| UT-CONT-005 | Add SMS contact with invalid format | 422 VALIDATION_ERROR |
| UT-CONT-006 | Add SMS contact for unsupported country | 422 SMS_COUNTRY_UNSUPPORTED |
| UT-CONT-007 | Block a contact | Status → blocked |
| UT-CONT-008 | Unblock a contact | Status → active |
| UT-CONT-009 | Search for user by username | Returns matching profiles |
| UT-CONT-010 | Search for private profile | Returns 0 results |
| UT-CONT-011 | Remove a contact | 204, contact deleted |

---

## Module MSG — Real-Time Messaging

| ID | Test | Expected |
|---|---|---|
| UT-MSG-001 | Send message in existing conversation | 201, status: sent |
| UT-MSG-002 | Send empty message body | 422 |
| UT-MSG-003 | Send message exceeding 2000 chars | 422 |
| UT-MSG-004 | Send message to blocked contact | 403 |
| UT-MSG-005 | Load message history — pagination | 50 messages, has_more: true |
| UT-MSG-006 | Load message history — cursor navigation | Correct page from cursor |
| UT-MSG-007 | Mark message as delivered | Status updated |
| UT-MSG-008 | Mark message as read | Status updated + timestamp |
| UT-MSG-009 | Delete own message (scope: me) | deleted_at set, body null, only for sender |
| UT-MSG-010 | Delete own message (scope: everyone, within 5 min) | deleted_at set for both parties |
| UT-MSG-011 | Delete own message (scope: everyone, after 5 min) | 422 |
| UT-MSG-012 | Delete another user's message | 403 |
| UT-MSG-013 | Deleted message appears as placeholder | body: null, deleted_at: set |
| UT-MSG-014 | Start conversation with non-existent user | 404 |
| UT-MSG-015 | Start conversation with user who blocked you | 403 |
| UT-MSG-016 | Start duplicate conversation | 200 (returns existing) |
| UT-MSG-017 | Non-participant reads messages | 0 results (RLS) |

---

## Module SMS — Internet-to-SMS

| ID | Test | Expected |
|---|---|---|
| UT-SMS-001 | Send SMS in simulation mode | 202, is_simulated: true |
| UT-SMS-002 | Simulation mode — SIMULATED badge in response | is_simulated: true, provider: mock |
| UT-SMS-003 | Send SMS with insufficient credits | 422 INSUFFICIENT_CREDITS |
| UT-SMS-004 | Send SMS to opted-out number | 422 PHONE_OPTED_OUT |
| UT-SMS-005 | Send SMS to unsupported country | 422 SMS_COUNTRY_UNSUPPORTED |
| UT-SMS-006 | Send SMS without phone_verified | 422 PHONE_NOT_VERIFIED |
| UT-SMS-007 | Send SMS with invalid E.164 number | 422 VALIDATION_ERROR |
| UT-SMS-008 | Submit duplicate idempotency key | 409, original response returned |
| UT-SMS-009 | Segment count — GSM-7, 160 chars exactly | 1 segment |
| UT-SMS-010 | Segment count — GSM-7, 161 chars | 2 segments |
| UT-SMS-011 | Segment count — Unicode, 70 chars | 1 segment |
| UT-SMS-012 | Segment count — Unicode, 71 chars | 2 segments |
| UT-SMS-013 | Credit deduction — reserved on send | balance - credit_cost = reserved |
| UT-SMS-014 | Credit confirmation — accepted by provider | reserved released, balance deducted |
| UT-SMS-015 | Credit refund — permanent failure | balance restored |
| UT-SMS-016 | Retry — transient failure | retry_count incremented, rescheduled |
| UT-SMS-017 | Retry — max retries exceeded | status: permanently_failed, credits refunded |
| UT-SMS-018 | Capability check — Philippines | outbound: true, inbound: false (requires verification) |

---

## Module SMSRECV — Inbound SMS

| ID | Test | Expected |
|---|---|---|
| UT-RECV-001 | Valid Twilio webhook signature | 200, processed |
| UT-RECV-002 | Invalid webhook signature | 403, not processed |
| UT-RECV-003 | Inbound SMS matched to conversation | Message inserted, is_matched: true |
| UT-RECV-004 | Inbound SMS unmatched | is_matched: false, admin notified |
| UT-RECV-005 | Duplicate inbound webhook (same provider_message_id) | Idempotent — not double-processed |
| UT-RECV-006 | Inbound SMS origin label | origin: sms on inserted message |

---

## Module AI — AI Assistant (Phase 3)

| ID | Test | Expected |
|---|---|---|
| UT-AI-001 | Smart reply — valid request | 200 with 3 suggestions |
| UT-AI-002 | Smart reply — non-participant conversation | 404 |
| UT-AI-003 | Translation — valid language pair | 200 with translated_text |
| UT-AI-004 | Translation — unsupported language | 422 |
| UT-AI-005 | SMS optimise — fits in 1 segment | meaning_preserved: true, 1 segment |
| UT-AI-006 | SMS optimise — cannot fit in 1 segment | meaning_preserved: false, message explaining |
| UT-AI-007 | AI provider timeout (mocked) | 502 PROVIDER_ERROR — compose field still accessible |
| UT-AI-008 | AI rate limit exceeded | 429 |
| UT-AI-009 | AI call — no message content in logs | ai_usage_logs has no body field |
| UT-AI-010 | AI suggestion — does not auto-send | Response contains suggestion only, no message record created |

---

## Module CREDIT

| ID | Test | Expected |
|---|---|---|
| UT-CRED-001 | Get credit balance | Correct balance/reserved/available |
| UT-CRED-002 | Concurrent sends — race condition | Balance never goes negative (SELECT FOR UPDATE) |
| UT-CRED-003 | Simulation mode SMS | Credits not deducted |
| UT-CRED-004 | Credit transaction created on deduction | Ledger entry with correct amount + balance_after |
| UT-CRED-005 | Credit refund transaction | Ledger entry with positive amount |

---

## Module RLS — Row Level Security

| ID | Test | Expected |
|---|---|---|
| UT-RLS-001 | User A reads User B's profile via API | Returns only public fields; private profiles return nothing |
| UT-RLS-002 | User A reads User B's contacts | 0 results |
| UT-RLS-003 | User A reads messages in conversation they're not part of | 0 results |
| UT-RLS-004 | User A reads User B's outbound SMS | 0 results |
| UT-RLS-005 | User A reads User B's credit transactions | 0 results |
| UT-RLS-006 | User A reads sms_delivery_events directly | 0 results (admin only) |
| UT-RLS-007 | User A reads ai_usage_logs directly | 0 results (admin only) |
| UT-RLS-008 | Admin reads any user's profile | Returns profile |
| UT-RLS-009 | Admin reads any user's outbound SMS | Returns records |
| UT-RLS-010 | Unauthenticated request to profiles | 0 results or 401 |

---

## E2E Journey Tests (Playwright)

| ID | Journey | Covered By |
|---|---|---|
| E2E-001 | Registration → Email verify → First login | Journey 1 |
| E2E-002 | Add Chikka contact → Open conversation → Send message → Receive real-time | Journey 2 |
| E2E-003 | SMS compose → Simulation send → SIMULATED badge → Delivery status | Journey 3 |
| E2E-004 | Admin → Switch to live mode (3 friction steps) → Mode changes | Journey 6 |
| E2E-005 | AI translation → Review panel → Accept → Send | Journey 5 |
| E2E-006 | Account deletion → Sessions invalidated → Redirect to login | Journey 7 |
| E2E-007 | Insufficient credits → Send blocked → Low balance warning visible | Implicit in Journey 3 |
| E2E-008 | Blocked contact cannot send message | FR-CONTACTS-004 |

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

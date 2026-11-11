# Authentication API

**Document:** CHKR-API-002  
**Project:** Chikka Reborn  
**Version:** 2.0  
**Status:** Implemented (Implementation 02)  
**Last Revised:** November 2026  

---

## Purpose

Authentication and user management endpoints. Supabase Auth owns credentials; the backend mediates every auth call (ADL-011, ADL-019) to add rate limits, neutral responses, profile checks, consent records and audit events. The interactive reference is at `/docs` (disabled in production).

## Base Paths

| Path | Area |
|---|---|
| `/api/v1/auth` | Sign-up, sign-in, tokens, email verification, password reset, sessions |
| `/api/v1/users/me` | Profile, onboarding, photo, presence, mobile number, account deletion |

All responses use the envelope in [api-overview.md](api-overview.md): `{ "data": ..., "request_id": "..." }` or `{ "error": { "code", "message", "details" }, "request_id" }`.

## Tokens and Cookies

| Item | Where it lives | Notes |
|---|---|---|
| Access token (Supabase JWT, 1 hour) | Response body; SPA memory only | `Authorization: Bearer <token>` on protected routes |
| Refresh token | `chikka_refresh` cookie | `HttpOnly`, `SameSite=Lax`, `Path=/api/v1/auth`, `Secure` outside development, 7-day sliding expiry |

The backend verifies the JWT signature, expiry and audience on every protected request, then checks in the database that the Supabase session (`session_id` claim) still exists and that the profile is not suspended or deleted. Logout and session revocation therefore take effect on the next request, not at token expiry. Roles come from `profiles.role`, never from token metadata.

`POST /auth/refresh` reads the cookie and requires the header `X-Chikka-CSRF: 1`. Browsers only send that header after a CORS preflight that the API's explicit origin list approves.

## Access Levels

| Level | Meaning |
|---|---|
| Public | No token |
| Signed in | Valid token, live session, account not suspended or deleted |
| Verified | Signed in and email confirmed (`status = active`) |

## Rate Limits

Counters are stored in `rate_limit_counters` (keyed hashes, shared across instances). Exceeding a limit returns `429 rate_limited` with `Retry-After` and `details.retry_after_seconds`.

| Action | Limit |
|---|---|
| Register | 10 / hour / IP |
| Login | 5 consecutive failures per email, then 15-minute lockout; 20 failures / 15 min / IP |
| Re-authentication (deletion, phone change) | 5 failures per user, then 15-minute lockout |
| Password reset request | 3 / hour / IP and 3 / hour / email |
| Password reset confirm | 10 / hour / IP |
| Resend verification | 3 / hour / IP and 3 / hour / email |
| Verify email | 20 / hour / IP |
| Refresh | 120 / hour / IP |
| Mobile code send | 3 / 30 min / user (plus a 60-second resend cooldown per number) |
| Mobile code check | 20 / 30 min / user; 5 wrong codes invalidate the code |
| Profile writes | 60 / hour / user |

---

## Authentication (`/api/v1/auth`)

### POST /auth/register

Public. FR-AUTH-001.

```json
{ "email": "user@example.com", "password": "Example-Pass-1", "display_name": "Example User", "accept_terms": true }
```

**202:** `{ "data": { "message": "Check your inbox. If the address can be used, we sent a link to confirm it." } }`

The response is identical for a new and an already registered address (AC3). Terms and Privacy consent are recorded with notice version and a coarse IP prefix. Password policy: at least 8 characters (72 bytes max) with an uppercase letter, a lowercase letter and a digit. Unknown fields are rejected.

**Errors:** `422 validation_error` (field problems in `details.problems`), `422 weak_password`, `429`, `503 auth_unavailable`.

### POST /auth/login

Public. FR-AUTH-004, FR-AUTH-006.

```json
{ "email": "user@example.com", "password": "Example-Pass-1" }
```

**200:** `{ "data": { "access_token": "...", "token_type": "bearer", "expires_in": 3600 } }` plus the refresh cookie and `Cache-Control: no-store`.

| Status | Code | When |
|---|---|---|
| 401 | `invalid_credentials` | Wrong email or password (identical for both) |
| 403 | `email_not_verified` | Correct password, email not yet confirmed |
| 403 | `account_unavailable` | Suspended or deleted |
| 429 | `rate_limited` | Lockout; message does not confirm the account exists |
| 503 | `auth_unavailable` | Supabase Auth unreachable |

### POST /auth/refresh

Cookie + `X-Chikka-CSRF: 1`. Returns a new access token and rotates the cookie. `401` when the cookie is missing or revoked (the cookie is then cleared); `403 csrf_required` without the header.

### POST /auth/logout

Signed in. Body optional: `{ "scope": "local" | "global" }` (default `local`). **204.** Clears the cookie. If Supabase is unreachable the backend deletes the session rows itself, so sign-out always completes.

### POST /auth/verify-email

Public. FR-AUTH-002. The confirmation email links to the SPA at `/auth/verify-email?token_hash=...`; the SPA posts the hash:

```json
{ "token_hash": "..." }
```

**200:** tokens (as login). The profile becomes `active` and the user is signed in. Links are single use and expire after 24 hours; a resend invalidates earlier links. **400 `invalid_or_expired_link`.**

### POST /auth/resend-verification

Public. `{ "email": "..." }`. **200** with the same neutral message whether or not the address exists or needs confirming.

### POST /auth/reset-password

Public. FR-AUTH-005. `{ "email": "..." }`. **200:** `"If an account exists for that address, we sent a password reset link."` for every address.

### POST /auth/reset-password/confirm

Public. The reset email links to `/auth/reset-password?token_hash=...`.

```json
{ "token_hash": "...", "new_password": "New-Example-Pass-2", "confirm_password": "New-Example-Pass-2" }
```

**200.** Every session is ended, including the one the link created; the user signs in again. The password policy is checked before the single-use link is spent. **400 `invalid_or_expired_link`**, **422** mismatch or weak (`weak_password` also covers reusing the current password).

### GET /auth/sessions

Signed in. FR-AUTH-014. Up to 50 active sessions:

```json
{ "data": [ { "id": "uuid", "created_at": "...", "last_active_at": "...", "device": "Chrome on Windows", "ip_prefix": "203.0.113.0/24", "current": true } ] }
```

The raw user agent and full IP address are never returned.

### DELETE /auth/sessions/{session_id}

Signed in. **204.** `400 current_session` for the session in use (use logout); `404` if it does not exist or belongs to someone else.

### POST /auth/sessions/revoke-others

Signed in. **200** `{ "data": { "message": "Signed out 2 other sessions." } }`.

---

## Profile (`/api/v1/users/me`)

Every endpoint acts on the caller's own row, identified only by the verified token. There is no endpoint that takes a user id.

### GET /users/me

Signed in. FR-AUTH-007.

```json
{
  "data": {
    "id": "uuid", "username": "example_user", "display_name": "Example User",
    "email": "user@example.com", "email_verified": true,
    "avatar_url": "https://<project>.supabase.co/storage/v1/object/sign/avatars/...",
    "bio": null, "country_code": "PH", "language": "en", "time_zone": "Asia/Manila",
    "theme": "system", "ui_mode": "modern", "presence_preference": "online",
    "role": "user", "status": "active", "onboarding_completed": true,
    "phone": { "masked": "+63****1234", "verification_mode": "simulated", "verified_at": "..." },
    "created_at": "...", "updated_at": "..."
  }
}
```

`email` comes from the token; profile data and credentials are stored separately. `avatar_url` is a signed URL valid for one hour (`null` if storage is unavailable).

### PATCH /users/me

Verified. Any subset of `display_name` (2–50), `bio` (≤160, `null` or empty clears), `country_code` (ISO 3166-1 alpha-2), `language` (one of `en fil ceb ilo hil es ar zh ja ko id ms vi th`), `time_zone` (IANA), `theme` (`system|light|dark`), `ui_mode` (`modern|classic`). HTML tags and control characters are stripped. Unknown fields, including `id`, `role`, `status` and `username`, are rejected with 422. **200:** updated profile.

### POST /users/me/onboarding

Verified. FR-AUTH-015. Sets the username once.

```json
{ "username": "example_user", "display_name": "Example User", "country_code": "PH", "language": "en", "time_zone": "Asia/Manila", "ui_mode": "modern" }
```

Username: 3–20 letters, digits or underscores, unique case-insensitively, not reserved. **409 `username_taken`** with `details.suggestions`; **409 `already_onboarded`**.

### POST /users/me/avatar

Verified. FR-AUTH-011. `multipart/form-data`, field `avatar`. JPEG, PNG or WebP up to **2 MB** (the FRS limit; the earlier 5 MB draft is superseded). The server identifies the format from the bytes, rejects decompression bombs, re-encodes to WebP at most 512 px, and so strips EXIF including location. Stored in the private `avatars` bucket under `<user_id>/`. **200** `{ "data": { "avatar_url": "..." } }`; **422 `invalid_image`**; **503 `storage_unavailable`** (old photo kept).

### DELETE /users/me/avatar

Verified. **204.**

### PUT /users/me/presence

Verified. FR-AUTH-013. `{ "preference": "online" | "away" | "busy" | "invisible" }`.

### POST /users/me/presence/heartbeat

Verified. `{ "idle": false }`, every 30 seconds; `idle: true` after 5 minutes without input. **200** `{ "data": { "status": "online", "preference": "online", "last_seen_at": "..." } }`. No heartbeat for 60 seconds means offline. Others will see `invisible` as `offline`.

### DELETE /users/me

Signed in. FR-AUTH-009. Re-authentication required.

```json
{ "password": "Example-Pass-1", "confirmation": "DELETE" }
```

**202** `{ "data": { "message": "...", "deleted_at": "..." } }`. Erases username, display name (becomes "Deleted user"), bio, photo, country and mobile numbers; ends every session; disables sign-in and replaces the auth email with a non-identifying address. Keeps the profile row (status `deleted`), consent history, credit ledger and audit rows. **403 `reauthentication_failed`** (nothing changed), **422** wrong phrase, **503 `deletion_unavailable`** (nothing changed).

---

## Mobile Number (`/api/v1/users/me/phone`)

FR-AUTH-008, FR-AUTH-012. Separate from email verification and not delegated to Supabase phone auth (which would need an SMS provider configured in Supabase). Codes are 6 digits, valid 10 minutes, stored as a keyed hash and never logged.

| Mode (`SMS_PROVIDER_MODE`) | Delivery |
|---|---|
| `mock` (simulation) | Nothing is sent. The code appears in the simulated inbox, labelled SIMULATED. Verification is recorded as `simulated`. |
| `live` | Needs the Phase 2 `SmsProvider`. Until then sending answers `503 otp_delivery_unavailable`; it never falls back to simulation. |

| Method and path | Access | Purpose |
|---|---|---|
| `GET /users/me/phone` | Verified | `{ verified, masked, verification_mode, verified_at, delivery_mode }` |
| `POST /users/me/phone` | Verified | Send a code. `{ "phone_number": "+63...", "password": "..." }`; `password` is required only when replacing a verified number |
| `POST /users/me/phone/verify` | Verified | `{ "phone_number": "+63...", "code": "123456" }` |
| `DELETE /users/me/phone` | Verified | `{ "password": "..." }` removes the verified number |
| `GET /users/me/phone/simulated-inbox` | Verified | Simulation outside production only; otherwise 404 |

Errors: `422` invalid E.164 number; `409 phone_unavailable` (neutral: the number is verified on another account); `409 already_verified`; `403 reauthentication_required`; `400 resend_cooldown`, `otp_not_requested`, `otp_expired`, `otp_locked`; `422 otp_invalid` with `details.attempts_remaining`. The previous number is released only after the new one is verified.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
| 2.0 | November 2026 | Kiro | Rewritten to match Implementation 02: cookie refresh, token-hash email links, sessions, presence, onboarding, phone endpoints under `/users/me/phone`, 2 MB photos, deletion with typed confirmation |

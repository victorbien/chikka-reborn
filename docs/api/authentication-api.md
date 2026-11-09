# Authentication API

**Document:** CHKR-API-002  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Documents all authentication and user management endpoints. Auth is backed by Supabase Auth; the FastAPI layer provides additional user profile and phone verification endpoints.

## Base Path

`/api/v1/auth` — Authentication  
`/api/v1/users` — User profile management

---

## POST /auth/register

Register a new user with email and password.  
**Auth:** None required  
**Rate limit:** 10 requests / hour / IP  
**FR:** FR-AUTH-001, FR-AUTH-002

**Request:**
```json
{
  "email": "marites@example.com",
  "password": "SecurePass1",
  "display_name": "Marites Santos"
}
```

**Response 201:**
```json
{
  "data": {
    "user_id": "a1b2c3d4-...",
    "email": "marites@example.com",
    "display_name": "Marites Santos",
    "email_verified": false
  },
  "request_id": "..."
}
```

**Errors:**
- `422 VALIDATION_ERROR` — invalid email format or weak password
- `409 CONFLICT` — email already registered (generic message; does not confirm existence)

---

## POST /auth/login

Authenticate with email and password.  
**Auth:** None required  
**Rate limit:** 5 attempts / 15 min / IP (FR-AUTH-006)  
**FR:** FR-AUTH-004

**Request:**
```json
{
  "email": "marites@example.com",
  "password": "SecurePass1"
}
```

**Response 200:**
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "v1.MRjq...",
    "token_type": "bearer",
    "expires_in": 3600
  },
  "request_id": "..."
}
```

**Errors:**
- `401 UNAUTHORIZED` — invalid credentials (generic; does not reveal which field is wrong)
- `429 RATE_LIMITED` — too many failed attempts

---

## POST /auth/logout

Invalidate the current session.  
**Auth:** Required  
**FR:** FR-AUTH-004

**Response 204:** No content.

---

## POST /auth/refresh

Exchange a refresh token for a new access token.  
**Auth:** None (uses refresh token)

**Request:**
```json
{ "refresh_token": "v1.MRjq..." }
```

**Response 200:** Same structure as `/auth/login` response.  
**Errors:** `401 UNAUTHORIZED` — expired or invalid refresh token

---

## POST /auth/reset-password

Request a password reset email.  
**Auth:** None  
**Rate limit:** 3 requests / 1 hour / IP  
**FR:** FR-AUTH-005

**Request:**
```json
{ "email": "marites@example.com" }
```

**Response 200:** Always returns success (prevents email enumeration):
```json
{
  "data": { "message": "If an account exists, a reset link has been sent." },
  "request_id": "..."
}
```

---

## POST /auth/reset-password/confirm

Set a new password using the reset token from email.  
**Auth:** Reset token (from email link, passed as query param `?token=...`)

**Request:**
```json
{
  "new_password": "NewSecurePass1",
  "confirm_password": "NewSecurePass1"
}
```

**Response 200:** Success confirmation.  
**Errors:** `400` — expired or invalid token; `422` — passwords don't match or weak

---

## POST /auth/resend-verification

Resend the email verification link.  
**Auth:** Required (unverified account)

**Response 200:** Always returns success.  
**Rate limit:** 3 requests / hour / account

---

## POST /auth/verify-phone

Send an OTP to associate a phone number with the account.  
**Auth:** Required  
**Rate limit:** 3 OTP sends / 30 min / account  
**FR:** FR-AUTH-008

**Request:**
```json
{ "phone_number": "+639171234567" }
```

**Response 200:**
```json
{
  "data": { "expires_in": 600 },
  "request_id": "..."
}
```

**Errors:** `422 VALIDATION_ERROR` — invalid E.164 format; `409` — number already verified on another account

---

## POST /auth/verify-phone/confirm

Confirm the OTP and complete phone verification.  
**Auth:** Required  
**FR:** FR-AUTH-008

**Request:**
```json
{ "otp": "123456" }
```

**Response 200:**
```json
{
  "data": { "phone_verified": true },
  "request_id": "..."
}
```

**Errors:** `422` — invalid OTP; `400` — expired OTP

---

## GET /users/me

Get the authenticated user's full profile.  
**Auth:** Required  
**FR:** FR-AUTH-007

**Response 200:**
```json
{
  "data": {
    "id": "a1b2c3d4-...",
    "username": "marites_santos",
    "display_name": "Marites Santos",
    "bio": "OFW in Dubai",
    "avatar_url": "https://storage.supabase.co/avatars/a1b2c3d4.jpg",
    "country_code": "PH",
    "phone_number": "+639171234567",
    "phone_verified": true,
    "role": "user",
    "ui_mode": "modern",
    "email_verified": true,
    "created_at": "2026-11-09T00:00:00Z"
  },
  "request_id": "..."
}
```

---

## PATCH /users/me

Update the authenticated user's profile.  
**Auth:** Required  
**FR:** FR-AUTH-007

**Request** (any subset of updatable fields):
```json
{
  "display_name": "Marites C. Santos",
  "bio": "OFW in Dubai. Mom of 2.",
  "country_code": "AE",
  "ui_mode": "classic"
}
```

**Response 200:** Updated profile object (same shape as GET /users/me).  
**Errors:** `422` — invalid display_name length; invalid country_code; invalid ui_mode

---

## POST /users/me/avatar

Upload a new profile avatar.  
**Auth:** Required  
**Content-Type:** `multipart/form-data`  
**FR:** FR-AUTH-007

**Request:** Form field `avatar` containing an image file (JPEG, PNG, WebP; max 5MB).

**Response 200:**
```json
{
  "data": { "avatar_url": "https://storage.supabase.co/avatars/a1b2c3d4.jpg" },
  "request_id": "..."
}
```

---

## DELETE /users/me

Delete the authenticated user's account.  
**Auth:** Required + re-authentication  
**FR:** FR-AUTH-009

**Request:**
```json
{ "confirm_password": "SecurePass1" }
```

**Response 202:** Deletion scheduled.
```json
{
  "data": {
    "message": "Account deletion scheduled. Personal data will be erased within 30 days.",
    "scheduled_at": "2026-11-09T12:00:00Z"
  },
  "request_id": "..."
}
```

**Errors:** `401` — re-authentication failed

---

## GET /users/search

Search for registered Chikka users.  
**Auth:** Required  
**FR:** FR-CONTACTS-001

**Query params:**
- `q` (required, min 2 chars) — search term (username or email prefix)
- `page`, `page_size`

**Response 200:** Paginated list of public profiles (excludes private profiles, blocked users).

```json
{
  "data": [
    {
      "id": "uuid",
      "username": "jericho_r",
      "display_name": "Jericho Reyes",
      "avatar_url": "...",
      "is_online": true
    }
  ],
  "pagination": { "total": 3, "page": 1, "page_size": 20, "has_next": false, "has_prev": false },
  "request_id": "..."
}
```

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

# Module A — Authentication and User Management (`AUTH`)

Part of the [Functional Requirements Specification](../functional-requirements.md). Conventions, roles, modes and cross-cutting rules (`CC-xx`) are defined there.

---

### FR-AUTH-001 — Email Registration

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | Visitor |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | A visitor can create an account with email and password. |
| Preconditions | Visitor is not signed in. Registration is enabled. |
| Trigger | Visitor submits the registration form. |
| Main workflow | 1) Visitor enters email, display name, password, and accepts Terms and Privacy Notice. 2) Client validates with Zod. 3) Backend re-validates and creates the Supabase Auth user. 4) A profile row is created with status `pending_verification`. 5) Verification email is sent (FR-AUTH-002). 6) UI shows a "check your email" screen. |
| Alternative workflows | A) Email already registered: return the same neutral confirmation, send an "account already exists" email to that address. B) Visitor chooses social sign-up (FR-AUTH-003). |
| Expected result | Unverified account and profile exist; verification email queued. |
| Error scenarios | Invalid email or weak password: 422 with field errors. Rate limit exceeded: 429 with `Retry-After`. Email send failure: account is kept, UI offers "resend". Auth service down: 503, nothing created. |
| Dependencies | Supabase Auth, email delivery, CC-02, CC-05. |
| Acceptance criteria | AC1 Email passes RFC 5322 validation. AC2 Password has at least 8 characters with one uppercase, one lowercase and one digit. AC3 A duplicate email produces a response indistinguishable from a new registration. AC4 Terms acceptance is stored with timestamp and version (FR-PRIVACY-007). AC5 No session with full access is issued before verification. |

### FR-AUTH-002 — Email Verification

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | Registered user (unverified) |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | An account must verify its email before gaining full access. |
| Preconditions | Account exists with status `pending_verification`. |
| Trigger | User opens the verification link, or requests a new one. |
| Main workflow | 1) User opens link. 2) Backend confirms the token. 3) Account status becomes `active`. 4) User is redirected to profile onboarding (FR-AUTH-015). |
| Alternative workflows | A) Link expired: show "expired" page with resend button. B) Already verified: redirect to login. C) User requests resend: new email sent, previous link invalidated. |
| Expected result | Account is `active` and may use messaging features. |
| Error scenarios | Invalid or tampered token: generic failure page. Resend limit exceeded (3 per hour): 429. |
| Dependencies | FR-AUTH-001, email delivery. |
| Acceptance criteria | AC1 Link expires after 24 hours. AC2 Unverified users can sign in but only see the verification-required screen. AC3 Unverified accounts cannot send SMS or add contacts. AC4 Resend invalidates earlier links. |

### FR-AUTH-003 — Social Login (Google, GitHub)

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | Visitor |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users can register or sign in with Google or GitHub. |
| Preconditions | OAuth apps are configured in Supabase (secrets in environment only). |
| Trigger | User selects a social provider button. |
| Main workflow | 1) Redirect to provider. 2) User consents. 3) Callback creates or links the Supabase user. 4) First-time users complete profile onboarding (FR-AUTH-015). 5) Session issued. |
| Alternative workflows | A) Email matches an existing password account: require the user to sign in with the existing method, then link. B) User cancels at provider: return to login with neutral message. |
| Expected result | Signed-in session; profile exists. |
| Error scenarios | Provider error or denied scope: return to login with a readable message. Provider email unverified: treat as unverified and require FR-AUTH-002. |
| Dependencies | Supabase Auth OAuth providers. |
| Acceptance criteria | AC1 Flow completes without exposing provider tokens to frontend code beyond Supabase's client library. AC2 First-time social users are prompted for display name. AC3 Linking never silently merges two different accounts. |

### FR-AUTH-004 — Login

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | Registered user |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users sign in with email and password. |
| Preconditions | Account exists and is not suspended or deleted. |
| Trigger | User submits the login form. |
| Main workflow | 1) User enters credentials. 2) Supabase validates. 3) JWT session issued. 4) Presence set to online (FR-AUTH-013). 5) User lands on last visited page or the conversation list. |
| Alternative workflows | A) Social login (FR-AUTH-003). B) Unverified account: show verification-required screen. C) Suspended account: show suspension notice with support contact. |
| Expected result | Authenticated session; backend accepts the JWT on protected routes. |
| Error scenarios | Wrong credentials: generic "email or password incorrect" (no enumeration). Locked out: FR-AUTH-006 message. Network failure: retryable error. |
| Dependencies | Supabase Auth, FR-AUTH-006. |
| Acceptance criteria | AC1 Correct credentials return a valid session. AC2 Wrong email and wrong password give identical responses and timing class. AC3 Sessions expire after 7 days of inactivity. AC4 Suspended users cannot obtain access to protected APIs. |

### FR-AUTH-005 — Password Reset

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | Registered user |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users can reset a forgotten password by email. |
| Preconditions | None (visitor-accessible). |
| Trigger | User submits "Forgot password" with an email. |
| Main workflow | 1) User enters email. 2) UI always shows "if the address is registered, a link was sent". 3) User opens link, sets new password. 4) All other sessions are revoked. 5) User signs in. |
| Alternative workflows | A) Social-only account: email explains the sign-in method. B) Link reused: rejected. |
| Expected result | Password changed; old sessions invalid. |
| Error scenarios | Expired link: restart flow. Weak password: 422. Rate limit: 429. |
| Dependencies | Supabase Auth, email delivery. |
| Acceptance criteria | AC1 Link is valid for 1 hour and single use. AC2 Response never reveals whether the email exists. AC3 Existing sessions are invalidated after reset. AC4 A password-changed email is sent. |

### FR-AUTH-006 — Login Rate Limiting and Lockout

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | System |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Failed logins are rate limited to resist brute force. |
| Preconditions | Login endpoint reachable. |
| Trigger | Failed login attempt. |
| Main workflow | 1) Failures are counted per account and per IP. 2) At 5 consecutive failures a 15-minute lockout starts. 3) UI shows remaining lockout time. 4) Successful login after lockout resets the counter. |
| Alternative workflows | A) Admin clears a lockout (FR-ADMIN-002). |
| Expected result | Repeated guessing is blocked. |
| Error scenarios | Counter store unavailable: fail closed for login (503), log the error. |
| Dependencies | CC-02. |
| Acceptance criteria | AC1 Five consecutive failures trigger the lockout. AC2 Lockout message does not confirm the account exists. AC3 Lockout events are audit logged (CC-03). |

### FR-AUTH-007 — Profile Editing

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users can edit their profile after creation. |
| Preconditions | Signed in and verified. |
| Trigger | User saves the profile form. |
| Main workflow | 1) User edits display name, bio, country, preferred language, time zone. 2) Zod validation. 3) Backend updates profile. 4) Changes appear immediately across the UI and to permitted contacts. |
| Alternative workflows | A) Cancel discards changes. B) Display name rejected by content filter: ask for another. |
| Expected result | Profile updated and `updated_at` set. |
| Error scenarios | Invalid fields: 422. Concurrent edit: last write wins, UI refreshes. Unsafe content: sanitised or rejected. |
| Dependencies | FR-AUTH-015, FR-PRIVACY-001. |
| Acceptance criteria | AC1 Display name is 2 to 50 characters. AC2 Bio maximum 160 characters, HTML stripped. AC3 Updates are visible without a page reload. AC4 Edits to others' profiles are rejected (CC-04). |

### FR-AUTH-008 — Mobile Number Verification (OTP)

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both (behaviour differs)** |
| Description | Users can verify ownership of a mobile number using a one-time code. |
| Preconditions | Email verified. Number is in a country with outbound SMS supported (FR-SMS-007). Number is not verified on another account. |
| Trigger | User enters a number and requests a code. |
| Main workflow | 1) User enters number; it is normalised to E.164. 2) Backend checks capability and send limits. 3) A 6-digit code is generated, stored hashed with expiry. 4) **Live:** code is sent as a real SMS. **Simulation:** code is delivered to the in-app "Simulated SMS inbox" panel labelled SIMULATED, shown only when the environment is not production. 5) User enters the code. 6) Number is marked verified, with `verification_mode` = `live` or `simulated`. |
| Alternative workflows | A) Resend after cooldown. B) User cancels; number stays unverified. C) After switching to live mode, numbers verified in simulation must be re-verified before features requiring a live-verified number. |
| Expected result | Number attached to the account and flagged with its verification mode. |
| Error scenarios | Wrong code: attempts counted, 5 failures invalidate the code. Expired code: request a new one. Unsupported country: explain and block. Number already used: neutral failure. Provider error (live): readable message, no charge, retry allowed. |
| Dependencies | `SmsProvider`, FR-SMS-007, FR-PRIVACY-007, CC-02. |
| Acceptance criteria | AC1 Code is 6 digits and valid for 10 minutes. AC2 Maximum 3 send attempts per 30 minutes. AC3 One verified number per account and one account per verified number. AC4 In simulation no real SMS is sent and the UI shows SIMULATED. AC5 Codes are never logged in plain text. AC6 Verification records its mode. |

### FR-AUTH-009 — Account Deletion

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users can delete their account and personal data. |
| Preconditions | Signed in. |
| Trigger | User confirms deletion in Settings. |
| Main workflow | 1) User chooses "Delete account" and reads what is removed and kept. 2) Re-authentication. 3) User types a confirmation phrase. 4) Account is soft-deleted (`deleted_at`) and all sessions revoked. 5) Personal data is scheduled for erasure within 30 days. 6) Confirmation email sent. |
| Alternative workflows | A) User cancels. B) Reactivation by signing in within a 7-day grace period (OPEN-04). C) Admin-initiated deletion (FR-ADMIN-002). |
| Expected result | Account inaccessible; data erased on schedule; messages in other users' histories show "Deleted user". |
| Error scenarios | Re-auth failure: no change. Pending erasure job fails: retried and alerted to admin. |
| Dependencies | FR-PRIVACY-009, FR-CREDIT-007, CC-03. |
| Acceptance criteria | AC1 Re-authentication is required. AC2 All sessions are invalid immediately. AC3 Conversation content is anonymised, not deleted, for other participants. AC4 Credit ledger and audit records are retained in anonymised form. AC5 Erasure completes within 30 days. |

### FR-AUTH-010 — Logout

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users can sign out of the current device, or all devices. |
| Preconditions | Signed in. |
| Trigger | User selects "Log out" or "Log out everywhere". |
| Main workflow | 1) Client calls sign-out. 2) Session (or all sessions) revoked. 3) Realtime subscriptions closed, presence set to offline. 4) TanStack Query cache cleared. 5) Redirect to login. |
| Alternative workflows | A) Offline: local session is cleared and server revocation retried on reconnect. |
| Expected result | No cached private data remains in the client. |
| Error scenarios | Server unreachable: local sign-out still completes, user is informed. |
| Dependencies | FR-AUTH-013, FR-AUTH-014. |
| Acceptance criteria | AC1 After logout protected routes redirect to login. AC2 Revoked tokens are rejected by the backend. AC3 Presence shows offline to contacts within 60 seconds. AC4 Browser back button does not reveal private data. |

### FR-AUTH-011 — Profile Photo

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users can upload, replace and remove a profile photo. |
| Preconditions | Signed in and verified. |
| Trigger | User selects an image in profile settings. |
| Main workflow | 1) User picks a file. 2) Client checks type and size, offers a crop. 3) Backend validates content type by inspection and re-encodes. 4) Stored in Supabase Storage under the user's path. 5) Profile avatar URL updated. |
| Alternative workflows | A) Remove photo: default avatar with initials. B) Upload cancelled. |
| Expected result | New avatar shown wherever the profile is visible. |
| Error scenarios | Unsupported or oversized file: 422. Corrupt image: rejected. Storage unavailable: 503, old photo retained. |
| Dependencies | Supabase Storage with RLS, FR-PRIVACY-001. |
| Acceptance criteria | AC1 Allowed types JPEG, PNG, WebP up to 2 MB. AC2 EXIF metadata is stripped. AC3 Only the owner can write to their path. AC4 Every avatar has alt text of the display name. AC5 Visibility follows profile privacy. |

### FR-AUTH-012 — Mobile Number Management

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both (behaviour differs)** |
| Description | Users can change or remove their verified mobile number and control its visibility. |
| Preconditions | Signed in. |
| Trigger | User opens Settings, Mobile number. |
| Main workflow | 1) User views masked number and verification mode. 2) To change: re-authenticate, then run FR-AUTH-008 for the new number. 3) Old number is released only after the new one is verified. 4) To remove: re-authentication, then number is detached. |
| Alternative workflows | A) Number discoverability setting (who may find me by number) lives in FR-PRIVACY-005. |
| Expected result | The account holds at most one verified number. |
| Error scenarios | New number fails verification: old number retained. Number belongs to another account: neutral failure. |
| Dependencies | FR-AUTH-008, FR-PRIVACY-005, CC-03. |
| Acceptance criteria | AC1 Changes require re-authentication. AC2 Numbers are masked in UI except to the owner during edit. AC3 Change and removal are audit logged. AC4 Removing the number disables features that require one. |

### FR-AUTH-013 — User Presence

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | User, System |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | The platform tracks and shares presence (online, away, busy, invisible, offline). |
| Preconditions | Signed in. |
| Trigger | Session start, activity, inactivity, status change, or sign-out. |
| Main workflow | 1) Client joins a Supabase Realtime presence channel. 2) Heartbeat every 30 seconds. 3) No activity for 5 minutes sets `away`. 4) No heartbeat for 60 seconds sets `offline`. 5) User may set `busy` or `invisible`; invisible is shown to others as offline. 6) Permitted contacts see changes in real time. |
| Alternative workflows | A) User disables presence sharing (FR-PRIVACY-005): contacts see "status hidden". B) Multiple tabs: the most active state wins. |
| Expected result | Contacts see accurate, privacy-respecting presence. |
| Error scenarios | Realtime unreachable: presence shown as unknown, not online. |
| Dependencies | Supabase Realtime, FR-CONTACTS-014, FR-PRIVACY-005. |
| Acceptance criteria | AC1 Presence changes reach contacts within 5 seconds. AC2 Blocked users never receive presence. AC3 Presence is not persisted beyond last-seen timestamp. AC4 Invisible users cannot be distinguished from offline by others. |

### FR-AUTH-014 — Session Management

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users can see and revoke their active sessions. |
| Preconditions | Signed in. |
| Trigger | User opens Settings, Security, Sessions. |
| Main workflow | 1) List sessions with device, browser, approximate location and last active. 2) Current session is marked. 3) User revokes one or all other sessions. 4) Revoked sessions are rejected on next request. |
| Alternative workflows | A) Suspicious login notification email on a new device (SHOULD). |
| Expected result | User controls where they are signed in. |
| Error scenarios | Revocation fails: error shown and list refreshed. |
| Dependencies | Supabase Auth, session metadata table. |
| Acceptance criteria | AC1 Revocation takes effect within 1 minute. AC2 IP addresses are shown coarsely. AC3 Revocation is audit logged. |

### FR-AUTH-015 — Profile Creation (Onboarding)

| Field | Detail |
|---|---|
| Module | A — Authentication |
| User role | User (new) |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | New users complete a short onboarding that creates a usable profile. |
| Preconditions | Email verified (or social sign-in completed). |
| Trigger | First sign-in with no completed profile. |
| Main workflow | 1) Choose unique username. 2) Confirm display name. 3) Choose country and language. 4) Optional photo (FR-AUTH-011). 5) Choose interface mode (FR-CLASSIC-001). 6) Review privacy defaults (FR-PRIVACY-001). 7) Profile marked complete. |
| Alternative workflows | A) Skip optional steps. B) Username taken: suggestions offered. |
| Expected result | Profile exists with username and defaults; user can be found per privacy settings. |
| Error scenarios | Reserved or offensive username: rejected. Save failure: progress retained. |
| Dependencies | FR-AUTH-002, FR-PRIVACY-001. |
| Acceptance criteria | AC1 Username is 3 to 20 characters of letters, digits and underscore, unique case-insensitively. AC2 Users cannot use messaging until username exists. AC3 Default visibility is "contacts only". AC4 Onboarding is keyboard accessible. |

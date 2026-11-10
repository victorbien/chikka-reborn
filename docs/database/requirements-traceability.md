# Requirements Traceability (Database)

**Document:** CHKR-DB-008  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Proposed  
**Last Revised:** November 2026  

---

## Purpose

Verifies the database schema against every functional requirement in `docs/product/frs/` (130 requirements across 11 modules). For each one it states what in the schema supports it, or why the schema is not involved.

Legend:

| Mark | Meaning |
|---|---|
| ✔ | Covered by the schema (tables, constraints, triggers or policies) |
| ○ | No schema needed (UI, provider adapter, Supabase-managed, or ephemeral). Noted where the backend does the work |
| ◐ | Partly covered. The gap is stated |
| ⏳ | Deferred. A table or migration is still needed, with the reason |

Checks were made against the requirement titles and the data details extracted from each requirement. Where an acceptance criterion depends on backend behaviour, the entry says "backend".

## 1. Result

| Mark | Count |
|---|---|
| ✔ Covered | 105 |
| ○ No schema needed | 15 |
| ◐ Partly covered | 6 |
| ⏳ Deferred | 4 |
| **Total** | **130** |

No requirement was found that the schema contradicts. The 10 not fully covered (6 partial, 4 deferred) are listed in section 3 with the action for each. One real gap was found and fixed during this review: FR-ADMIN-009 (resolving a failed message with a note) had no storage, so resolution columns were added to `messages`.

## 2. Matrix

### Module A: Authentication and users

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-AUTH-001 | Email registration | ✔ | `auth.users` + `profiles` (status `pending_verification`, trigger-created); terms/privacy acceptance in `user_consents` with notice version |
| FR-AUTH-002 | Email verification | ○ | Supabase Auth (24 h link, resend). Backend sets `profiles.status = 'active'`. Resend limit via `rate_limit_counters` |
| FR-AUTH-003 | Social login | ○ | Supabase `auth.identities`. Explicit linking is backend behaviour |
| FR-AUTH-004 | Login | ○ | Supabase sessions (7-day inactivity is configuration). Suspended accounts blocked via `profiles.status` |
| FR-AUTH-005 | Password reset | ○ | Supabase Auth (1 h, single-use) |
| FR-AUTH-006 | Lockout | ✔ | `rate_limit_counters` (`login:account`, `login:ip`, `attempts`, `locked_until`); lockout events to `audit_logs` |
| FR-AUTH-007 | Profile editing | ✔ | `profiles`: display name 2 to 50, bio at most 160, country, language, time zone; `updated_at` |
| FR-AUTH-008 | Mobile OTP | ✔ | `phone_numbers`: hashed code, 10 min expiry, attempts at most 5, sends counter and window, `verification_mode`, per-mode uniqueness. Resend cooldown length is not specified in the FRS |
| FR-AUTH-009 | Account deletion | ✔ | `deletion_requested_at`, `deleted_at`, status `deleted`; profile is tombstoned so messages, ledger and audit rows stay valid. Erasure job is backend. The 7-day reactivation window is unconfirmed (OPEN-04) |
| FR-AUTH-010 | Logout | ○ | Supabase; presence falls back via `last_seen_at` |
| FR-AUTH-011 | Profile photo | ◐ | `profiles.avatar_path`. The Storage bucket and its access policies are not yet in a migration |
| FR-AUTH-012 | Mobile number management | ✔ | `phone_numbers.status` (`released`, `released_at`); one verified number per account per mode; changes to `audit_logs` |
| FR-AUTH-013 | User presence | ✔ | `presence_preference`, `share_presence`, `show_last_seen`, `last_seen_at`. Live state is ephemeral |
| FR-AUTH-014 | Session management | ⏳ | Needs a `user_sessions` metadata table (device, browser, approximate location, last active, revoke). Supabase holds the sessions themselves |
| FR-AUTH-015 | Onboarding | ✔ | `username` nullable until onboarding; `onboarding_completed_at`; default visibility `contacts`; reserved and offensive names are backend checks |

### Module B: Contacts

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-CONTACTS-001 | Send request | ✔ | `contact_requests`: note at most 140, 30-day expiry, one pending request per pair (either direction), no self-add. 30 per day via `idx_contact_requests_sent` and `rate_limit_counters`. Silent success for blocked senders is backend |
| FR-CONTACTS-002 | SMS contact | ✔ | `contacts.contact_type = 'sms'`, E.164, unique per owner. "SMS not available" and "opted out" flags are derived from capabilities and `sms_opt_outs`. No consent recorded on add (by design) |
| FR-CONTACTS-003 | List display | ✔ | `contacts.is_favourite`, groups, indexes for owner ordering; pagination is a query concern |
| FR-CONTACTS-004 | Block | ✔ | `user_blocks` for accounts or numbers; blocked inbound SMS stored with `messages.suppressed_at` |
| FR-CONTACTS-005 | Groups | ✔ | `contact_groups` (name 1 to 30, colour, position, max 20, unique per owner), `contact_group_members` |
| FR-CONTACTS-006 | Mute | ✔ | `contacts.muted_until` / `muted_indefinitely` and the same on `conversation_members`. Scope question in FRS resolved by supporting both |
| FR-CONTACTS-007 | Search | ✔ | Case-insensitive unique `username` index; exact email via `auth.users` (backend only); number search only when `discoverable_by_phone`; 20 per minute via `rate_limit_counters` |
| FR-CONTACTS-008 | Import | ✔ | Consent in `user_consents` (`contact_import`); raw files never stored |
| FR-CONTACTS-009 | Pending list | ✔ | `contact_requests.status` (incl. `cancelled`, `expired`), `expires_at`, partial index |
| FR-CONTACTS-010 | Accept / reject | ✔ | `private.accept_contact_request()` creates both contact rows atomically; `responded_at` supports the 7-day re-request rule; decisions to `audit_logs` |
| FR-CONTACTS-011 | Favourites | ✔ | `contacts.is_favourite` |
| FR-CONTACTS-012 | Unblock | ✔ | Delete from `user_blocks` (backend), audit logged |
| FR-CONTACTS-013 | Recent | ✔ | `conversations.last_message_at`; `contacts.recent_cleared_at` hides without deleting |
| FR-CONTACTS-014 | Online status display | ✔ | Presence settings on `profiles`; state is ephemeral |

### Module C: Chikka messaging

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-MSG-001 | Send message | ✔ | `messages`: body at most 2000 characters, `idempotency_key`, DB-assigned `seq`, stored before broadcast. Blocked messages accepted but suppressed. 60 per minute is a backend rate limit |
| FR-MSG-002 | Status indicators | ✔ | Chikka `message_deliveries` rows (`sent`, `delivered`, `read`, `failed`) with timestamps and forward-only rule; SMS statuses never use `read` |
| FR-MSG-003 | Typing indicator | ○ | Ephemeral, never persisted. `profiles.send_typing_indicators` stores the setting |
| FR-MSG-004 | History | ✔ | `seq` order with unique `(conversation_id, seq)` supports cursor pagination of 50 |
| FR-MSG-005 | Deletion | ✔ | `message_hides` (delete for me), `deleted_for_everyone_at` with body cleared; 5-minute window enforced by backend from `created_at`; reported content survives in `abuse_reports.snapshot` |
| FR-MSG-006 | Emoji | ✔ | UTF-8 text; limits count characters (code points) |
| FR-MSG-007 | Real-time updates | ○ | Backend WebSocket gateway. `seq`, `status_version` and event dedupe keys make the protocol possible |
| FR-MSG-008 | Read receipts | ✔ | `profiles.send_read_receipts` (default off), delivery `read_at`, `conversation_members.last_read_seq` |
| FR-MSG-009 | Search | ✔ | `messages.search_vector` (generated, GIN). Participant scoping by policy; deleted messages have null bodies. Uses the `simple` configuration, so no stemming |
| FR-MSG-010 | Attachments | ⏳ | Needs `message_attachments` and a private Storage bucket |
| FR-MSG-011 | Editing | ◐ | `edited_at` exists and SMS edits are refused by constraint. Version history needs `message_versions` |
| FR-MSG-012 | Conversation management | ✔ | `conversation_members`: pinned (max 5 by trigger), archived, muted, marked unread, `cleared_before_seq`; unread derived from `last_read_seq` |
| FR-MSG-013 | Start / open | ✔ | `conversations.direct_key` unique; `get_or_create_chikka_conversation()` is atomic and idempotent |

### Module D: Internet-to-SMS

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-SMS-001 | Compose and send | ✔ | `messages` (sms) + `message_deliveries`; mode stored via `is_simulated` and provider configuration; `is_ai_assisted`; 30 per hour via `idx_messages_sms_send_rate` and `system_settings.sms_user_limit_per_hour` |
| FR-SMS-002 | Segments and cost | ✔ | `encoding`, `char_count`, `segment_count` (1 to 10), `credit_cost_units`, `capability_id` (rate used) |
| FR-SMS-003 | Simulation labelling | ✔ | `is_simulated` on message and delivery, `NOT NULL`, checked against provider mode |
| FR-SMS-004 | Delivery tracking | ✔ | `message_delivery_events` (unique callbacks, applied/ignored), orphans in `provider_webhooks`, `idx_deliveries_reconcile` for the 30-minute poll |
| FR-SMS-005 | Insufficient credit prevention | ✔ | Ledger trigger refuses overdraw; backend maps to 402 |
| FR-SMS-006 | Recipient validation | ◐ | `e164` domain. The mobile/landline/unknown type is a validation-time result and is not persisted |
| FR-SMS-007 | Country capability check | ✔ | `sms_country_capabilities`, tri-state support, unknown country means unsupported (no row) |
| FR-SMS-008 | Confirm before sending | ○ | UI |
| FR-SMS-009 | Provider response | ✔ | `provider_status`, `provider_message_id`, `failure_code`, redacted `failure_reason`, `http_status`, provider configuration; `SIM-` prefix. Raw send responses are deliberately not stored (redaction); raw callbacks are in `provider_webhooks` |
| FR-SMS-010 | Failures | ✔ | `failure_class`, `is_permanent`; one refund per message by unique ledger key; resend creates a new message |
| FR-SMS-011 | Retry | ✔ | Attempt rows, `next_attempt_at`, `locked_until` lease; defaults (3 attempts, 5 s base, 300 s cap) in `provider_configurations`. Backoff and Retry-After handling are backend |
| FR-SMS-012 | Idempotent send | ✔ | Unique `(sender_user_id, idempotency_key)`, `request_hash` for the 409 case; rows outlive the 24 h minimum |
| FR-SMS-013 | Simulated scenarios | ○ | Mock provider behaviour; `is_simulated` and `SIM-` IDs distinguish results |

### Module E: SMS-to-Internet

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-SMSRECV-001 | End to end | ✔ | `sms_routes` + `provider_webhooks` + inbound `messages` in the user's `sms` conversation |
| FR-SMSRECV-002 | Signature validation | ○ | Backend. The schema stores only verified events (`signature_verified_at NOT NULL`); rejections go to `audit_logs` |
| FR-SMSRECV-003 | Origin labelling | ✔ | `messages.channel`, `direction`, `sender_phone` |
| FR-SMSRECV-004 | Receive webhook | ✔ | `provider_webhooks`: 64 KB cap, server-only, `purge_after` default 90 days |
| FR-SMSRECV-005 | Resolve account | ✔ | `sms_routes` exclusivity; suspended or deleted recipients stored with `suppressed_reason = 'recipient_unavailable'` |
| FR-SMSRECV-006 | Resolve conversation | ✔ | `conversations.direct_key` for `(user, remote)`; `get_or_create_sms_conversation()` |
| FR-SMSRECV-007 | Create inbound message | ✔ | `direction = 'inbound'`, 1600 characters with `body_truncated`, status `received`, `is_simulated`, no ledger entry |
| FR-SMSRECV-008 | Notify | ✔ | `notifications.notification_type = 'sms_inbound'` |
| FR-SMSRECV-009 | Duplicate prevention | ✔ | Unique `(provider, kind, dedupe_key)` and unique provider message ID per configuration |
| FR-SMSRECV-010 | Unknown sender | ✔ | `routing_result = 'unrouted'` with partial index; purge at 90 days. The 10 per hour abuse flag is a backend query |
| FR-SMSRECV-011 | Unsupported destination | ✔ | Capability row governs; unrouted or blocked result recorded |
| FR-SMSRECV-012 | Opt-out messages | ✔ | `sms_opt_outs` (keyword, scope, source webhook); consent history untouched |
| FR-SMSRECV-013 | Simulate inbound | ✔ | `is_simulated` on webhook and message |

### Module F: AI assistant

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-AI-001 | Smart replies | ✔ | `ai_assistance_logs.feature = 'suggest_replies'` |
| FR-AI-002 | Translation | ✔ | Feature `translate`, `language` |
| FR-AI-003 | Rewriting | ✔ | Feature `rewrite` |
| FR-AI-004 | SMS length optimisation | ✔ | Feature `optimise_sms`, `meaning_preserved` |
| FR-AI-005 | Summary | ✔ | Feature `summarise`; per-conversation exclusion `conversation_members.ai_enabled` |
| FR-AI-006 | Mandatory approval | ○ | Structural, in the backend design (no send path from the AI module). `user_decision` and `accepted_message_id` record the outcome |
| FR-AI-007 | AI-assisted badge | ✔ | `messages.is_ai_assisted`; column is not granted to clients, so recipients never see it |
| FR-AI-008 | Tone adjustment | ✔ | Feature `tone_adjust` |
| FR-AI-009 | Composition | ✔ | Feature `compose`. The 300-character prompt limit is validated at the API |
| FR-AI-010 | Language selection | ✔ | `ai_assistance_logs.language`, `profiles.language` |
| FR-AI-011 | Request history | ✔ | Metadata always; content optional, requires `content_expires_at` (30 days); owner may delete; administrators have no access |
| FR-AI-012 | Failures and rate limits | ✔ | `outcome` values; 30 per hour via `idx_ai_logs_user` and `system_settings`; kill switch `system_settings.ai_enabled` |
| FR-AI-013 | Privacy controls | ✔ | `profiles.ai_enabled` (default off), `ai_use` consent, per-conversation switch. Redaction is backend |

### Module G: Notifications

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-NOTIF-001 | In-app alerts | ✔ | `notifications` (unread persists); do-not-disturb follows `presence_preference = 'busy'` |
| FR-NOTIF-002 | Browser push | ⏳ | Needs `push_subscriptions`; blocked on OD-004 |
| FR-NOTIF-003 | SMS delivery alerts | ✔ | Types `sms_delivered`, `sms_failed`; `group_key` groups several failures; failed-SMS alerts cannot be disabled (constraint) |
| FR-NOTIF-004 | Low balance | ✔ | `low_balance_threshold_units` (1 to 100 credits), `messaging_credits.low_balance_alerted` re-arms |
| FR-NOTIF-005 | Preferences | ✔ | `notification_preferences.overrides` (type x channel), quiet hours, previews; security/system in-app notices cannot be disabled |
| FR-NOTIF-006 | History | ✔ | `read_at`, `dismissed_at`, `expires_at` (90 days), feed indexes |
| FR-NOTIF-007 | Contact request alerts | ✔ | Types `contact_request`, `contact_accepted`; none for rejection or block (backend) |
| FR-NOTIF-008 | Email | ✔ | `email_hard_bounce_count`, `email_disabled_at`, per-category switches in `overrides`. Digest timing and the 10 per hour cap are backend |

### Module H: Credits

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-CREDIT-001 | Balance display | ✔ | `messaging_credits` balance and reserved per ledger (live, demo); balance equals sum of ledger (tested) |
| FR-CREDIT-002 | Per-country pricing | ✔ | `credit_multiplier` on versioned capabilities with `effective_from`; rate version stored on each message and ledger row; zero or negative rejected |
| FR-CREDIT-003 | Deduct and refund | ✔ | `credit_transactions` with user, message, provider, country, segments, amount, time; atomic trigger; single adjustment per message for segment differences |
| FR-CREDIT-004 | Top-up | ◐ | Entry type `top_up` with unique `external_reference` makes payment events idempotent. A `payments` table waits on OD-001 |
| FR-CREDIT-005 | Estimated cost | ✔ | Computed from the capability multiplier; quote kept in `credit_cost_units` |
| FR-CREDIT-006 | Simulated credits | ✔ | Separate `demo` ledger, one-time grant from `system_settings.demo_grant_units`; cannot be bought or converted; mismatch with message mode refused |
| FR-CREDIT-007 | Transaction history | ✔ | Ledger with `balance_after`, `reserved_after`, entry types; CSV export is backend |
| FR-CREDIT-008 | Low-credit warning | ✔ | As FR-NOTIF-004 |
| FR-CREDIT-009 | Insufficient credit | ✔ | Trigger raises `INSUFFICIENT_CREDITS` with available and required units |
| FR-CREDIT-010 | Admin adjustments | ✔ | `adjustment` entries require reason and actor; negative result refused; second-admin approval is marked FUTURE in the FRS |

### Module I: Privacy

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-PRIVACY-001 | Profile visibility | ✔ | `profile_visibility` enforced by `public_profiles` |
| FR-PRIVACY-002 | Data export | ⏳ | Needs `data_exports` (state, link expiry, file expiry, one in flight) |
| FR-PRIVACY-003 | SMS recipient opt-out | ✔ | `sms_opt_outs`, platform-wide |
| FR-PRIVACY-004 | Reporting | ✔ | `abuse_reports`: reasons, evidence `snapshot`, one report per reporter per message, daily limit via index |
| FR-PRIVACY-005 | Presence and activity settings | ✔ | Columns on `profiles` |
| FR-PRIVACY-006 | Blocking enforcement | ✔ | `user_blocks`, `suppressed_at`, invisible to the blocked party, `public_profiles` filter |
| FR-PRIVACY-007 | Consent records | ✔ | Append-only `user_consents`, per-recipient attestation |
| FR-PRIVACY-008 | Opt-out management | ✔ | `sms_opt_outs` lift fields; admin lift needs reason and actor |
| FR-PRIVACY-009 | Retention and deletion | ◐ | Dates and indexes exist for each window; **message-body retention is undefined (OD-006)**. Purge jobs are backend |
| FR-PRIVACY-010 | Access controls | ✔ | RLS everywhere; six server-only tables with no client access; admin roles limited |

### Module J: Administration

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-ADMIN-001 | Platform statistics | ○ | Aggregates over existing tables |
| FR-ADMIN-002 | User management | ✔ | `profiles.status`, `suspended_at`; actions and reasons to `audit_logs`. "Not the last admin" is a backend rule |
| FR-ADMIN-003 | SMS mode control | ✔ | `provider_configurations.is_active` with confirmation fields. Note: the SMS design proposed mode as startup configuration; the FRS wants an admin action. Both can read this table |
| FR-ADMIN-004 | SMS audit log | ✔ | `audit_logs` (category `sms`, 90 days) plus message and delivery rows; read-only |
| FR-ADMIN-005 | Capability management | ✔ | Versioned `sms_country_capabilities`; Philippines needs a registration status |
| FR-ADMIN-006 | AI usage monitoring | ✔ | Aggregates over `ai_assistance_logs` through the backend; no content access |
| FR-ADMIN-007 | SMS activity monitoring | ✔ | Deliveries, unrouted webhooks index; thresholds can live in `system_settings` |
| FR-ADMIN-008 | Delivery monitoring | ✔ | `message_deliveries` status, versions, timestamps |
| FR-ADMIN-009 | Failed message monitoring | ✔ | Stuck-message indexes; **resolution note and resolver columns added to `messages`** (found missing during this review) |
| FR-ADMIN-010 | Credit management | ✔ | `system_settings.demo_grant_units`; resets and top-ups as ledger adjustments |
| FR-ADMIN-011 | Report management | ✔ | `abuse_reports.status`, mandatory resolution note, resolver; 48 h indicator derived from `created_at` |
| FR-ADMIN-012 | Audit logs | ✔ | Immutable `audit_logs`; categories for admin, auth, SMS, credit, consent, privacy, security, moderation |
| FR-ADMIN-013 | Health and switches | ◐ | Switches in `system_settings`. The 24 h health-check history is not stored |
| FR-ADMIN-014 | Provider configuration | ✔ | `provider_configurations`: sender pool in `settings`, registration status, webhook path, retry settings; secrets never stored |

### Module K: Classic and Modern modes

| ID | Requirement | | Schema support |
|---|---|---|---|
| FR-CLASSIC-001 | Mode toggle | ✔ | `profiles.ui_mode` |
| FR-CLASSIC-002 | Classic mode | ○ | Frontend |
| FR-CLASSIC-003 | Modern mode (default) | ✔ | Default `modern` |
| FR-CLASSIC-004 | Theme | ✔ | `profiles.theme` (`system` default) |
| FR-CLASSIC-005 | Responsive layouts | ○ | Frontend |
| FR-CLASSIC-006 | Preference persistence | ✔ | `ui_mode`, `theme`, `language`, `display_options`; invalid values cannot be stored, so reads never need a fallback |
| FR-CLASSIC-007 | Accessibility parity | ○ | Frontend |

## 3. Items Not Fully Covered

| ID | Mark | Gap | Action |
|---|---|---|---|
| FR-AUTH-014 | ⏳ | No `user_sessions` table | Add a migration with the session backend work (Phase 1) |
| FR-MSG-010 | ⏳ | No `message_attachments` table | Add with the attachments feature and Storage bucket design |
| FR-NOTIF-002 | ⏳ | No `push_subscriptions` table | After OD-004 |
| FR-PRIVACY-002 | ⏳ | No `data_exports` table | Add with the export feature |
| FR-AUTH-011 | ◐ | Storage bucket and access policies for avatars are not in a migration | Add a Storage migration once the bucket layout is decided (private path per user) |
| FR-MSG-011 | ◐ | No `message_versions` table | Add with message editing |
| FR-SMS-006 | ◐ | Number type (mobile, landline, unknown) is not persisted | Acceptable; reconsider if audits need it |
| FR-CREDIT-004 | ◐ | No `payments` table | After OD-001 |
| FR-PRIVACY-009 | ◐ | Message-body retention is undefined | Decide OD-006 |
| FR-ADMIN-013 | ◐ | 24 h health-check history is not stored | Use the monitoring system, or add a table if that is rejected |

## 4. Inconsistencies Found in the Requirements

These affect the schema and are recorded so they can be settled.

| Item | Observation | Schema choice |
|---|---|---|
| Mute scope | FR-CONTACTS-006 mutes a contact; FR-MSG-012 mutes a conversation "per FR-CONTACTS-006" | Stored on both |
| Chikka `sending` status | Listed in FR-MSG-001/002 but is client-side | Not persisted |
| Philippines capability | AC-2-019 expects outbound `true`; the seed and DB rules forbid `supported` without evidence | Seeded `requires_verification`; acceptance test should expect that |
| AC-2-010 | Simulated progress lists Queued, Sent, Delivered and omits `accepted` | Schema keeps `accepted` (steering requires it) |
| Opt-out scope | "Scoped to the platform sender" (FR-SMSRECV-012) vs "platform-wide" (FR-PRIVACY-003) | Platform-wide by default; optional per-sender-number rows |
| Simulation credits (OD-009) | Decision log says open; FRS already specifies a demo ledger | Demo ledger implemented |
| Read receipts | AC-1-012 shows them in the default flow; FR-MSG-008 says default off | Default off |
| Message retention | No period defined anywhere | Open (OD-006) |

## 5. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial verification against 130 requirements |

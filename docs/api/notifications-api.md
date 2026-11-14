# Notifications API

**Document:** CHKR-API-007  
**Project:** Chikka Reborn  
**Version:** 2.0  
**Status:** Implemented (Module G)  
**Last Revised:** November 2026  

---

## Purpose

The in-app notification feed, per-user preferences, browser notifications and email. Design: ADL-022 in [architecture-decisions.md](../architecture/architecture-decisions.md).

Base path `/api/v1/notifications`. Standard envelope; lists are paginated.

## Types

| Type | Raised when |
|---|---|
| `new_message` | A contact messages you (not when the chat is muted). Unread messages from one chat fold into one notification (`occurrence_count`) |
| `sms_inbound` | A reply to your SMS arrives. Folded per conversation while unread |
| `sms_delivered` | The provider confirmed delivery |
| `sms_failed` | An SMS failed or was undelivered |
| `contact_request` | Someone sent you a request. Silent for blocked or private paths, so nothing is revealed |
| `contact_accepted` | Your request was accepted |
| `low_balance` | Available demo credits reached your threshold |
| `system` | Administrator notices, credit adjustments, SMS opt-outs |
| `security` | Other devices signed out, password reset, mobile number verified or removed |

SMS text is never copied into a notification. A message notification carries a preview only when the user turned previews on.

## Duplicates

- Each event carries a `dedupe_key` (for example `sms_status:<message>:delivered`, `chat_message:<message>`). The database holds one notification per user and key, so repeated callbacks, retries and replays cannot notify twice.
- Grouped types (`new_message`, `sms_inbound`) update the open unread notification instead of adding rows. Once it is read, the next event starts a new one.

## Preference rules

For each type and channel (`in_app`, `push` = browser notification, `email`) the defaults are: in-app on for all; browser on except `sms_delivered` and `contact_accepted`; email on only for `system` and `security`.

- `sms_failed`, `system` and `security` cannot be switched off in the app (`422 notification_mandatory`).
- A type off on every channel creates nothing. In-app off with another channel on creates a hidden row that still drives that channel.
- Quiet hours (the user's profile time zone, may wrap midnight) suppress browser notifications and email, never the feed.
- Previews are off by default.

## GET /notifications

Query: `page`, `page_size` (1-100), `unread_only` (bool), `type`. Newest first. Dismissed and expired (90 days) rows are not listed.

```json
{ "data": [ { "id": "uuid", "type": "new_message", "title": "New message from Bob Cruz",
  "body": null, "reference_type": "conversation", "reference_id": "uuid",
  "occurrence_count": 3, "is_read": false, "created_at": "2026-11-14T08:00:00Z" } ],
  "pagination": { "total": 1, "page": 1, "page_size": 30, "has_next": false, "has_prev": false } }
```

## GET /notifications/unread-count

`{ "data": { "unread_count": 2 } }`

## POST /notifications/{id}/read

Marks one as read (idempotent) and returns it. `404` for another user's or an unknown id.

## POST /notifications/read-all

Optional query `type`. Returns `{ "updated": 2, "unread_count": 0 }`.

## POST /notifications/{id}/dismiss

Removes it from the list and the count. Returns `{ "unread_count": n }`.

## GET /notifications/preferences, PUT /notifications/preferences

```json
{ "data": { "types": [ { "type": "new_message", "in_app": true, "push": true, "email": false,
    "in_app_locked": false } ],
  "quiet_hours_start": "22:00", "quiet_hours_end": "07:00", "show_previews": false,
  "low_balance_threshold_units": 500, "low_balance_threshold_credits": 5.0,
  "email_disabled": false, "email_simulated": true } }
```

`PUT` takes any subset: `types` (`{ "<type>": { "in_app"?, "push"?, "email"? } }`), `quiet_hours_start` and `quiet_hours_end` (`HH:MM`, both or neither; send both as `null` to turn off), `show_previews`, `low_balance_threshold_units` (100-10000, so 1-100 credits). Only deviations from the defaults are stored. `email_disabled` is true after three permanent email failures; `email_simulated` is true when the mock email provider is configured.

## Real-time delivery

After a notification commits, the dispatcher sends `notification.created` to the user's open sessions:

```json
{ "type": "notification.created", "data": { "notification": { ... }, "browser": true, "unread_count": 3 } }
```

`browser` is decided on the server (preference and quiet hours). The frontend shows a system notification only when `browser` is true, the user granted permission, and the tab is in the background. Permission is requested only when the user presses a button. There is no service-worker push: a closed browser gets email, not a browser notification.

## Email

The dispatcher sends emails through the configured `EmailProvider` (`EMAIL_PROVIDER_MODE=mock` or `smtp`; see [environment configuration](../deployment/environment-configuration.md)). Emails carry the title, the body only when previews are on, and a link; never SMS text. Attempts are counted before sending; a failed email is retried after 60 s x attempts, up to three attempts. An address the provider rejects is not retried, and after three rejections email is switched off for the account (`email_disabled`).

## Administration

### POST /admin/notifications

Administrator only. Header `Idempotency-Key` (UUID). Body `{ "title", "body"?, "user_id"? }`. Without `user_id` the notice goes to every active user (at most 10,000). Repeating a key creates nothing new. Audited (`notification.announced`). Returns `{ "recipients": n, "created": n }`.

## Errors

| Status | Code | When |
|---|---|---|
| 401 | `not_authenticated` | Not signed in |
| 403 | `forbidden` | Admin endpoint without the admin role |
| 404 | `not_found` | Unknown or someone else's notification; unknown target user |
| 422 | `notification_mandatory`, `validation_error` | Switching off a mandatory in-app notice; invalid input |

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
| 2.0 | November 2026 | Kiro | Implemented: dedupe and grouping, preferences, quiet hours, security type, delivery outbox, email provider, admin notices |

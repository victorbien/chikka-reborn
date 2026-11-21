# Contacts API

**Document:** CHKR-API-003
**Project:** Chikka Reborn
**Version:** 2.0
**Status:** Implemented (Chikka contacts); SMS contacts planned for Phase 2
**Last Revised:** November 2026

---

## Purpose

Contact management for Module B: buddy list, discovery, requests, groups, blocks and recent activity. Version 2.0 replaces the v1.0 draft, which described direct adds and a `status` field. The implemented model follows the schema in [`database-design.md`](../database-design.md) and the requirements in [`module-b-contacts.md`](../product/frs/module-b-contacts.md).

All routes are under `/api/v1/contacts`, require a verified, signed-in user, and use the standard success envelope `{ "data": ..., "request_id": ... }` and error envelope `{ "error": { "code", "message", "details" }, "request_id" }`. List endpoints return `{ "data": [...], "pagination": { "total", "page", "page_size", "has_next", "has_prev" }, "request_id" }`. `page_size` is 1 to 100 (default 50).

## Ownership rule

Every identifier in a path or body is looked up inside the caller's own records. An id that belongs to someone else behaves exactly like an id that does not exist (`404`). Row Level Security repeats the rule in the database.

## Buddy list

### GET /contacts

| Query | Meaning |
|---|---|
| `filter` | `all` (default), `online`, `offline`, `favourites`, `group` |
| `group_id` | Required with `filter=group` |
| `page`, `page_size` | Pagination |

Favourites come first, then alphabetical. Blocked contacts and inactive accounts are omitted. SMS-only contacts appear under `all`, `favourites` and `group`, never under `online` or `offline`.

Each entry:

| Field | Notes |
|---|---|
| `id` | Contact record id (the caller's own row) |
| `contact_type` | `chikka` or `sms` |
| `user_id`, `username` | `null` for SMS contacts |
| `display_name`, `nickname` | `nickname` is private to the caller and overrides the display name |
| `avatar_url` | Short-lived signed URL |
| `status_message` | Hidden when the contact's profile visibility is `private` |
| `presence` | `online`, `away`, `busy`, `offline` or `unknown` |
| `last_seen_at` | Only when the contact enabled "show last seen" |
| `is_favourite`, `group_ids` | Private to the caller |
| `masked_phone` | SMS contacts only, for example `+63****4567` |

`presence` is `unknown` when the contact shares presence with nobody. It is never reported as `offline`. A contact who chose "invisible" appears `offline`.

### GET /contacts/{contact_id}

Contact profile. Adds `bio` (hidden for private profiles), `country_code` and `added_at`. Email addresses and phone numbers are never returned.

### PATCH /contacts/{contact_id}

Body: `is_favourite` (boolean, not null) and/or `nickname` (string up to 100 characters, `null` clears it; SMS contacts cannot clear it). Unknown fields are rejected.

### DELETE /contacts/{contact_id}

Removes the contact. For a Chikka contact the relationship ends for both people (both rows are deleted in one transaction) and group memberships go with it. Either person can send a new request afterwards. Audit event `contact.removed`.

## Discovery

### GET /contacts/search?q=

Searches the caller's own contacts by name or username (substring, case-insensitive), and resolves one exact term to a person.

Response: `{ "contacts": [ContactSummary], "people": [SearchPerson] }`. `people` has at most one entry.

The exact term is interpreted as:

| Term | Match | Requires |
|---|---|---|
| Contains `@` | Exact email (case-insensitive) | Target enabled `discoverable_by_email` |
| Starts with `+` | Exact number, normalised to E.164 | Target has a verified number and enabled `discoverable_by_phone` |
| Otherwise | Exact username (case-insensitive) | Target is not `private` |

A person never appears if they are the caller, are `private`, have not finished onboarding, are inactive, or are blocked in either direction. All of these reasons, and "does not exist", produce the same empty `people` list, so the endpoint cannot be used to learn whether an address, number or username is registered. Phone numbers are never echoed.

`SearchPerson` has `user_id`, `username`, `display_name`, `avatar_url` and `relationship` (`none`, `contact`, `request_sent`, `request_received`) with `contact_id` / `request_id` where relevant.

Errors: `422 query_too_short` (under 2 characters), `429` (20 searches per minute per user).

## Contact requests

### POST /contacts/requests

Body: `user_id`, optional `note` (up to 140 characters, sanitised). Response: `{ "status": "sent" | "contacts" }`.

`sent` is returned whether the request was created or was silently not created. Silent cases: the target is unknown, inactive, `private`, has blocked the sender, a request is already pending, or the sender was rejected less than 7 days ago. `contacts` is returned when the two are already contacts or when the target had a pending request to the sender (both become contacts at once).

Errors: `422` (self-request, invalid note), `409 user_blocked` (the sender blocked the target and must unblock first), `429` (30 requests per day per user).

### GET /contacts/requests?direction=incoming|outgoing

Pending, unexpired requests (expire after 30 days). Items: `id`, `direction`, `person` (`user_id`, `username`, `display_name`, `avatar_url`), `note`, `created_at`, `expires_at`. Requests from users the caller blocked are hidden. Rejected requests never appear for the sender.

### POST /contacts/requests/{id}/accept

Optional body `{ "group_id": uuid }`. Only the recipient may accept; anyone else gets `404`. Creates both contact rows atomically (`private.accept_contact_request`). Idempotent for an already accepted request. Returns the new contact's detail. `409 request_unavailable` if the request expired, was cancelled or a block exists.

### POST /contacts/requests/{id}/reject

Optional body `{ "block": boolean }`. `204`. The sender is not notified and sees no change. `409 request_unavailable` if already resolved.

### DELETE /contacts/requests/{id}

Sender cancels a pending request. `204`. Anyone else gets `404`.

## Groups

Groups are private labels, not group chats.

| Route | Notes |
|---|---|
| `GET /contacts/groups` | `id`, `name`, `color`, `position`, `member_count` |
| `POST /contacts/groups` | Body `name` (1 to 30 characters, sanitised), optional `color` (`#RRGGBB`). `201`. `409 group_name_taken` (case-insensitive per owner), `422 group_limit_reached` (20 groups) |
| `PATCH /contacts/groups/{id}` | `name`, `color`, `position` |
| `DELETE /contacts/groups/{id}` | `204`. Contacts are kept |
| `POST /contacts/groups/{id}/members` | Body `contact_ids` (1 to 100). Every id must be the caller's own contact, otherwise `404` and nothing is added. Duplicates are ignored |
| `DELETE /contacts/groups/{id}/members/{contact_id}` | `204` |

## Blocks

| Route | Notes |
|---|---|
| `GET /contacts/blocks` | People the caller blocked. Never visible to the blocked person |
| `POST /contacts/blocks` | Body `user_id`. `201`. Idempotent. Withdraws pending requests between the two. `404` for an unknown user, `422` for self |
| `DELETE /contacts/blocks/{user_id}` | `204`. Does not re-add a removed contact and does not deliver anything retroactively |

A block hides the contact from the blocker's list and hides the blocker from the blocked person's list, requests, search and presence. Blocking keeps the contact row, so unblocking restores a surviving relationship. Audit events `contact.blocked` and `contact.unblocked`.

## Recent activity

| Route | Notes |
|---|---|
| `GET /contacts/recent` | Up to 20 contacts by latest conversation activity. Excludes blocked contacts. Items: `contact`, `conversation_id`, `last_message_at`. No message text |
| `DELETE /contacts/recent` | `204`. Hides the list; conversations and messages are untouched |
| `GET /contacts/recent-conversations` | Up to 20 conversations (Chikka and SMS), including people who are not contacts. SMS entries show a masked number |

## Privacy settings (used by discovery)

`GET` / `PATCH /api/v1/users/me/privacy`

| Field | Values | Default |
|---|---|---|
| `profile_visibility` | `everyone`, `contacts`, `private` | `contacts` |
| `share_presence` | `everyone`, `contacts`, `nobody` | `contacts` |
| `show_last_seen` | boolean | `false` |
| `discoverable_by_email` | boolean | `false` |
| `discoverable_by_phone` | boolean | `false` |

`PATCH /api/v1/users/me` also accepts `status_message` (up to 80 characters).

## Audit

Decisions are recorded in the `privacy` category without personal data: `contact.request_sent`, `contact.request_accepted`, `contact.request_rejected`, `contact.request_cancelled`, `contact.removed`, `contact.blocked`, `contact.unblocked`, `privacy.settings_changed`.

## Not yet implemented

SMS contacts (FR-CONTACTS-002), import (FR-CONTACTS-008), mute (FR-CONTACTS-006), request notifications (FR-NOTIF-007, Module G) and real-time presence push. The buddy list refreshes by polling every 30 seconds. Presence is held in memory per backend process (see ADL-013).

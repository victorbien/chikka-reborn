# Messaging API

**Document:** CHKR-API-004
**Project:** Chikka Reborn
**Version:** 2.0
**Status:** Implemented (Implementation 04, Chikka-to-Chikka). SMS conversations come with Phase 2.
**Last Revised:** November 2026

---

## Purpose

REST endpoints for Chikka-to-Chikka conversations and messages (Module C). Version 2.0 replaces the v1.0 draft: messages are ordered and paged by `seq` instead of timestamps, sends carry a client message ID, and status changes come from the server (acknowledgements and reads), not from a client `PATCH`. Real-time events are in [realtime-api.md](realtime-api.md).

All routes require a verified, onboarded user and use the standard envelopes (`{ "data", "request_id" }`, errors `{ "error": { "code", "message", "details" }, "request_id" }`). Lists add `pagination`.

## Rules that apply everywhere

- **Membership.** A conversation you are not in returns `404`, exactly like one that does not exist.
- **Contacts.** You can open and write to conversations with Chikka contacts only.
- **Blocks.** If you blocked someone, you cannot write to them (`403 user_blocked`) and their conversation leaves your list. If they blocked you, your message is stored and shown to you as "sent", and never reaches them. Nothing tells you that you were blocked.
- **Text.** Up to 2000 characters, counted in Unicode code points (one emoji is one). Stored as typed, without invisible control characters, and always rendered as text, never HTML.

## Message lifecycle

| Status | Where | Meaning |
|---|---|---|
| `pending` | Sender's device only | Not stored yet. Shown as "Sending". |
| `failed` | Sender's device only | Could not be stored (network, rate limit, server error). Retried with the same `client_message_id`. |
| `sent` | Server | Stored. Nothing more is known. |
| `delivered` | Server | The recipient's app received it: a WebSocket `ack`, or the recipient loading the conversation. Not "read". |
| `read` | Server | The recipient viewed it, recorded only when **both** people enable read receipts (off by default). |

Status only moves forward and carries `status_version`. Opening a conversation clears your unread count whether or not read receipts are on.

---

## Conversations

### GET /conversations

| Query | Default | Notes |
|---|---|---|
| `archived` | `false` | Inbox or archive |
| `q` | | 2 to 100 characters. Matches the other person's name or username, or words in messages you can see. Searches archived conversations too. 30 searches per minute. |
| `page`, `page_size` | 1, 30 | `page_size` up to 100 |

Sorted pinned first, then by latest activity. Conversations without messages are not listed (open them by id). Each item:

| Field | Notes |
|---|---|
| `id`, `conversation_type` | Always `chikka` here |
| `participant` | `user_id`, `username`, `display_name`, `avatar_url` (signed, short-lived), `presence` (`unknown` when not shared), `is_contact` |
| `last_message` | `id`, `seq`, `is_mine`, `preview` (up to 120 characters), `has_attachments`, `created_at`, `status` (yours only), or `null` |
| `last_message_at`, `unread_count`, `is_archived`, `is_muted` | Unread excludes your own messages |
| `can_send`, `cannot_send_reason` | Reason is user-readable: you blocked them, you are no longer contacts, or they cannot receive messages |

### POST /conversations

Body `{ "user_id": "…" }`. Returns the single conversation with that contact, creating it on first use (idempotent, one per pair). `403 not_a_contact` for strangers, unknown users and people you blocked (same response for all). `422` for yourself.

### GET /conversations/unread

`{ "unread_messages", "unread_conversations" }`. Muted conversations and people you blocked are not counted.

### GET /conversations/{id}

One conversation summary.

### PATCH /conversations/{id}

Body `{ "is_archived": true | false }`. Yours only; the other person is unaffected. A new message brings an archived conversation back to the inbox unless it is muted.

---

## Messages

### GET /conversations/{id}/messages

| Query | Notes |
|---|---|
| (none) | The latest page |
| `before_seq` | Older messages (scrolling up) |
| `after_seq` | Newer messages (catching up after a reconnect) |
| `limit` | 1 to 100, default 50 |

`before_seq` and `after_seq` together: `422`. Messages come oldest first within the page.

Response: `{ "messages": [...], "has_more_before", "last_read_seq", "peer_read_seq" }`. `peer_read_seq` is the other person's read position, only when both have read receipts on, otherwise `null`.

Message fields: `id`, `conversation_id`, `seq`, `sender_user_id`, `is_mine`, `body` (null for attachment-only or deleted), `attachments` (`id`, `file_name`, `content_type`, `size_bytes`, `url`), `created_at`, `edited_at`. On your own messages only: `client_message_id`, `status`, `status_version`, `delivered_at`, `read_at`.

Loading messages as the recipient marks them `delivered`, and the sender is told over the socket.

### POST /conversations/{id}/messages

```json
{ "client_message_id": "uuid generated by the client", "body": "Hello", "attachment_ids": [] }
```

`body`, `attachment_ids` (up to 5, from the upload endpoint), or both. `201` with the stored message. Repeating the same `client_message_id` with the same content returns the original with `200`: no second copy, no second push, and it does not count against the rate limit. The same id with different content: `409 idempotency_conflict`.

| Error | Code |
|---|---|
| Empty, whitespace only, or over 2000 characters | `422` |
| Attachment not yours, already sent, or from another conversation | `422 attachment_unavailable` |
| You blocked them / not contacts / they cannot receive | `403 user_blocked`, `403 cannot_send` |
| More than 60 messages per minute | `429` with `Retry-After` |

### POST /conversations/{id}/read

Body `{ "up_to_seq": n }`. Moves your read position forward (never back, never past the last message) and returns `{ "conversation_id", "last_read_seq", "unread_count" }`. Marks the other person's messages `read` if both of you allow read receipts, otherwise `delivered`.

### POST /conversations/{id}/attachments

Multipart field `file`. JPEG, PNG, WebP, GIF or PDF, up to 10 MB, 60 uploads per hour. The type is detected from the file's content; the name and declared type are ignored. Images must decode; JPEG, PNG and static WebP are re-encoded so EXIF (including location) is removed. `201` with the attachment, then send it with `attachment_ids`. Files are private: downloads use signed URLs that expire after an hour (refetch the conversation for fresh ones).

Errors: `422 invalid_attachment` with a readable reason, `503 storage_unavailable`.

---

## Not yet implemented

Editing (FR-MSG-011), deleting (FR-MSG-005), pinning and muting from the UI (FR-MSG-012; the columns exist), notifications for offline recipients (Module G), and SMS conversations (Modules D and E).

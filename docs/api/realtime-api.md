# Real-Time API (WebSocket)

**Document:** CHKR-API-009
**Project:** Chikka Reborn
**Version:** 1.0
**Status:** Implemented (Implementation 04)
**Last Revised:** November 2026

The wire protocol for `GET /ws/v1`. The design and its reasons are in [realtime-design.md](../architecture/realtime-design.md) and ADL-013 / ADL-020 in [architecture-decisions.md](../architecture/architecture-decisions.md).

The socket is a speed-up. **REST is the source of truth**: writes go through the [messaging API](messaging-api.md), and after every connect or reconnect the client refetches what it shows. A frame that never arrives loses nothing.

---

## 1. Connecting

```text
GET ws(s)://<api host>/ws/v1      (no query string, no token in the URL)
```

| Step | Client | Server |
|---|---|---|
| 1 | Opens the socket. Browsers send `Origin`; it must be in `CORS_ORIGINS`. | Foreign origin: handshake refused. |
| 2 | Within 5 seconds sends `{"type": "auth", "token": "<access token>"}` | No frame in time: close `4408`. Anything else first, or a bad token: close `4401`. |
| 3 | | Checks the token, that the Supabase session still exists, and that the account is active and onboarded. Unusable account: close `4403`. |
| 4 | | `{"type": "ready", "connection_id": "…", "heartbeat_s": 25, "server_time": "…", "expires_at": "…"}` |

After `ready` the client resyncs from REST (conversation list, unread totals, any open conversation).

## 2. Client to server

Frames are JSON text, at most 8 KB, at most 10 per second (bursts of 20). Unknown types get an `error` frame.

| Frame | Purpose |
|---|---|
| `{"type": "ping"}` | Heartbeat, every `heartbeat_s` seconds. Answered with `{"type": "pong", "server_time": "…"}`. No frame for 60 seconds closes the socket (`1001`). |
| `{"type": "ack", "message_ids": ["…"]}` | The app received these messages (1 to 100). This is what makes the sender see **Delivered**. Only your own deliveries change; other ids are ignored. Never sent for "read". |
| `{"type": "typing", "conversation_id": "…"}` | You are typing. The server forwards at most one per 2 seconds per conversation, only between contacts, never when either has blocked the other, and only if you allow typing indicators. Not stored. |
| `{"type": "auth.refresh", "token": "<new token>"}` | Extends the connection before the token expires. Answer `{"type": "auth.ok", "expires_at": "…"}`. A token for a different user closes with `4401`. |

## 3. Server to client

Events share one envelope. `event_id` is unique, so clients can drop duplicates.

```json
{
  "type": "message.created",
  "event_id": "1f0c…",
  "conversation_id": "a2b9…",
  "data": { "message": { "id": "…", "seq": 41, "is_mine": false, "body": "Hello" } },
  "sent_at": "2026-11-12T09:00:00Z"
}
```

| Type | `data` | Sent to |
|---|---|---|
| `message.created` | `message`: exactly what `GET …/messages` returns to that user. Your own messages carry `client_message_id` and `status`; other people's do not. | Both members. A message from someone the recipient blocked goes to the sender only. |
| `message.status_changed` | `message_id`, `conversation_id`, `status` (`delivered` or `read`), `status_version`, `delivered_at`, `read_at` | The sender. Apply only if `status_version` is higher than what you hold. |
| `conversation.read` | `conversation_id`, `last_read_seq`, `unread_count` | The reader's other tabs and devices. |
| `conversation.updated` | `is_archived` | The user's other tabs and devices. |
| `typing` | `user_id` | The other member. Clear the indicator after 3 seconds without another. |
| `error` | `code`, `message` (top-level, not in `data`) | The connection that caused it. `forbidden` means you are not in that conversation; 5 of them close the socket with `4403`. |

### Ordering, duplicates and gaps

- Order messages by `seq` (per conversation, gap-free), never by time.
- A `message.created` whose `seq` is more than one past the highest you hold means something was missed: refetch `GET …/messages`.
- When the stored copy of your own optimistic message arrives (push or REST response, whichever is first), match it by `client_message_id` and replace the local copy.

## 4. Close codes

| Code | Meaning | Client should |
|---|---|---|
| `1000` | Normal close | Nothing |
| `1001` | Server restarting, or the client went quiet | Reconnect with backoff |
| `1009` | Frame too big or not text | Reconnect with backoff |
| `1013` | Temporarily unavailable (database or key server) | Reconnect with backoff |
| `4401` | Token invalid or expired (plus 30 s grace), or you signed out | Refresh the token once, then reconnect. If refreshing fails, sign out. |
| `4403` | Account unavailable, or repeated forbidden frames | Do not retry automatically |
| `4408` | No `auth` frame within 5 seconds | Reconnect |
| `4409` | Replaced: more than 5 connections for this user | Do not fight it; this tab is the oldest |
| `4413` | The client could not keep up (more than 256 queued events) | Reconnect and resync |
| `4429` | Too many frames | Reconnect with backoff |

## 5. Reconnection (client)

Exponential backoff with full jitter: delay = random(0, min(30 s, 1 s × 2^attempt)). The attempt counter resets once a connection has stayed up for 60 seconds. Coming back online (`online` event) or to the tab (`visibilitychange`) tries at once. While disconnected the UI says so in words, and sending still works over REST.

## 6. Limits of this version

- One backend instance. Fan-out is in process (ADL-020). A second instance needs the Postgres `NOTIFY` listener first.
- No presence push yet. Presence still comes from REST (heartbeats every 30 seconds).

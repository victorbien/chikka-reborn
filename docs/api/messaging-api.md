# Messaging API

**Document:** CHKR-API-004  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Documents all Chikka-to-Chikka real-time messaging endpoints — conversations and messages.

## Base Path

`/api/v1/conversations`  
`/api/v1/conversations/:id/messages`

---

## GET /conversations

Get all conversations for the authenticated user.  
**Auth:** Required  
**FR:** FR-MSG-004, FR-MSG-011

**Query params:** `page`, `page_size`

**Response 200:**
```json
{
  "data": [
    {
      "id": "uuid",
      "conversation_type": "chikka",
      "participants": [
        { "user_id": "uuid", "display_name": "Jericho Reyes", "avatar_url": "...", "is_online": true }
      ],
      "last_message": {
        "body": "Kumusta ka?",
        "created_at": "2026-11-09T12:00:00Z",
        "origin": "chikka"
      },
      "unread_count": 2,
      "last_message_at": "2026-11-09T12:00:00Z"
    }
  ],
  "pagination": { "total": 5, "page": 1, "page_size": 20, "has_next": false, "has_prev": false },
  "request_id": "..."
}
```

---

## POST /conversations

Start a new conversation or return an existing one.  
**Auth:** Required  
**FR:** FR-MSG-001

**Request:**
```json
{
  "participant_user_id": "uuid-of-other-user"
}
```

**Response 200** (existing conversation found):
```json
{
  "data": { "id": "uuid", "conversation_type": "chikka", ... },
  "request_id": "..."
}
```

**Response 201** (new conversation created): Same shape.

**Errors:**
- `404 NOT_FOUND` — participant user does not exist
- `422 VALIDATION_ERROR` — cannot start a conversation with yourself
- `403 FORBIDDEN` — target user has blocked the requester

---

## GET /conversations/:conversationId

Get conversation details.  
**Auth:** Required (must be a participant)

**Response 200:**
```json
{
  "data": {
    "id": "uuid",
    "conversation_type": "chikka",
    "participants": [ ... ],
    "created_at": "2026-11-01T00:00:00Z",
    "last_message_at": "2026-11-09T12:00:00Z"
  },
  "request_id": "..."
}
```

**Errors:** `403 FORBIDDEN` — not a participant; `404 NOT_FOUND`

---

## GET /conversations/:conversationId/messages

Get paginated message history.  
**Auth:** Required (must be a participant)  
**FR:** FR-MSG-004

**Query params:**
- `before` — ISO timestamp cursor (load messages before this time)
- `limit` — default 50, max 100

**Response 200:**
```json
{
  "data": [
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "sender_user_id": "uuid",
      "sender_display_name": "Jericho Reyes",
      "sender_avatar_url": "...",
      "sender_phone": null,
      "origin": "chikka",
      "body": "Kumusta ka?",
      "status": "read",
      "is_ai_assisted": false,
      "is_simulated": false,
      "deleted_at": null,
      "created_at": "2026-11-09T12:00:00Z"
    },
    {
      "id": "uuid",
      "origin": "sms",
      "sender_phone": "+639171234567",
      "sender_user_id": null,
      "body": "Maayos naman!",
      "status": "delivered",
      "is_simulated": true,
      "created_at": "2026-11-09T12:01:00Z"
    }
  ],
  "pagination": {
    "has_more": true,
    "next_cursor": "2026-11-09T11:00:00Z"
  },
  "request_id": "..."
}
```

Note: Deleted messages return with `body: null` and `deleted_at` set — not omitted from the list.

---

## POST /conversations/:conversationId/messages

Send a Chikka message in a conversation.  
**Auth:** Required (must be a participant)  
**FR:** FR-MSG-001, FR-MSG-007

**Request:**
```json
{
  "body": "Kamusta ka na?",
  "is_ai_assisted": false
}
```

**Response 201:**
```json
{
  "data": {
    "id": "uuid",
    "conversation_id": "uuid",
    "sender_user_id": "uuid",
    "origin": "chikka",
    "body": "Kamusta ka na?",
    "status": "sent",
    "is_ai_assisted": false,
    "is_simulated": false,
    "created_at": "2026-11-09T12:05:00Z"
  },
  "request_id": "..."
}
```

**Errors:**
- `422 VALIDATION_ERROR` — empty body; exceeds 2000 characters
- `403 FORBIDDEN` — not a participant; sender is blocked by recipient

---

## PATCH /conversations/:conversationId/messages/:messageId/status

Update message status (delivered, read).  
**Auth:** Required — called by the **recipient's** client automatically.  
**FR:** FR-MSG-002

**Request:**
```json
{ "status": "read" }
```

Valid values: `delivered`, `read`  
**Response 200:** Updated message object.

---

## DELETE /conversations/:conversationId/messages/:messageId

Delete a sent message.  
**Auth:** Required (sender only)  
**Phase:** 2  
**FR:** FR-MSG-005

**Query params:**
- `scope` — `me` (delete for self only) | `everyone` (delete for both, within 5 minutes of creation)

**Response 200:**
```json
{
  "data": {
    "id": "uuid",
    "deleted_at": "2026-11-09T12:10:00Z",
    "scope": "everyone"
  },
  "request_id": "..."
}
```

**Errors:**
- `403 FORBIDDEN` — not the sender
- `422 VALIDATION_ERROR` — `scope=everyone` attempted after 5-minute window

---

## POST /conversations/:conversationId/read

Mark all messages in a conversation as read up to a given timestamp.  
**Auth:** Required (must be a participant)

**Request:**
```json
{ "read_until": "2026-11-09T12:05:00Z" }
```

**Response 200:** `{ "data": { "updated_count": 3 } }`

---

## Typing Indicators

Typing indicators are **not** REST endpoints — they use Supabase Realtime broadcast channels:

```javascript
// Frontend: broadcast typing event
channel.send({
  type: 'broadcast',
  event: 'typing',
  payload: { user_id: currentUser.id, conversation_id: conversationId }
});

// Frontend: listen for typing events
channel.on('broadcast', { event: 'typing' }, (payload) => {
  // Show typing indicator for payload.user_id
  // Auto-clear after 3 seconds
});
```

Typing events are ephemeral — they are never persisted to the database.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

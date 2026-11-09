# Notifications API

**Document:** CHKR-API-007  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Documents all notification endpoints for in-app and push notification management.

## Base Path

`/api/v1/notifications`

---

## GET /notifications

Get the authenticated user's notifications.  
**Auth:** Required  
**FR:** FR-NOTIF-001, FR-NOTIF-006

**Query params:**
- `is_read` — `true` | `false` (omit for all)
- `type` — filter by notification type
- `page`, `page_size`

**Response 200:**
```json
{
  "data": [
    {
      "id": "uuid",
      "type": "new_message",
      "title": "New message from Jericho Reyes",
      "body": "Kumusta ka?",
      "is_read": false,
      "reference_type": "conversation",
      "reference_id": "uuid",
      "created_at": "2026-11-09T12:00:00Z"
    },
    {
      "id": "uuid",
      "type": "sms_delivered",
      "title": "Message delivered",
      "body": "Your SMS to +63****1234 was delivered.",
      "is_read": true,
      "reference_type": "outbound_sms",
      "reference_id": "uuid",
      "created_at": "2026-11-09T11:55:00Z"
    },
    {
      "id": "uuid",
      "type": "low_balance",
      "title": "Low credit balance",
      "body": "You have 0.10 credits remaining.",
      "is_read": false,
      "reference_type": null,
      "reference_id": null,
      "created_at": "2026-11-09T11:50:00Z"
    }
  ],
  "pagination": { "total": 15, "page": 1, "page_size": 20, "has_next": false, "has_prev": false },
  "request_id": "..."
}
```

**Notification Types:**

| Type | Triggered By |
|---|---|
| `new_message` | Incoming Chikka message or inbound SMS |
| `sms_delivered` | SMS delivery confirmed by provider |
| `sms_failed` | SMS permanently failed after all retries |
| `low_balance` | Credit balance falls below configured threshold |
| `system` | Platform-wide announcements |
| `contact_request` | (Future) Contact request received |

---

## GET /notifications/unread-count

Get the count of unread notifications.  
**Auth:** Required

**Response 200:**
```json
{
  "data": { "unread_count": 5 },
  "request_id": "..."
}
```

Used to populate the notification badge in the navigation bar without loading all notifications.

---

## PATCH /notifications/:notificationId

Mark a single notification as read.  
**Auth:** Required (must own the notification)

**Request:**
```json
{ "is_read": true }
```

**Response 200:** Updated notification object.  
**Errors:** `404 NOT_FOUND`, `403 FORBIDDEN`

---

## POST /notifications/mark-all-read

Mark all notifications as read.  
**Auth:** Required

**Response 200:**
```json
{
  "data": { "updated_count": 5 },
  "request_id": "..."
}
```

---

## DELETE /notifications/:notificationId

Dismiss (delete) a notification.  
**Auth:** Required (must own the notification)

**Response 204:** No content.

---

## GET /notifications/preferences

Get the user's notification preferences.  
**Auth:** Required  
**Phase:** 2  
**FR:** FR-NOTIF-005

**Response 200:**
```json
{
  "data": {
    "push_enabled": true,
    "new_message": true,
    "sms_delivered": true,
    "sms_failed": true,
    "low_balance": true,
    "system": true
  },
  "request_id": "..."
}
```

---

## PATCH /notifications/preferences

Update notification preferences.  
**Auth:** Required  
**Phase:** 2  
**FR:** FR-NOTIF-005

**Request:**
```json
{
  "push_enabled": false,
  "sms_delivered": false
}
```

**Response 200:** Updated preferences object.

---

## POST /notifications/push/subscribe

Register a browser push notification subscription.  
**Auth:** Required  
**Phase:** 2  
**FR:** FR-NOTIF-002

**Request:**
```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/...",
  "keys": {
    "p256dh": "...",
    "auth": "..."
  }
}
```

This is the Web Push API subscription object, forwarded directly from the browser's `PushManager.subscribe()` result.

**Response 201:**
```json
{
  "data": { "subscription_id": "uuid" },
  "request_id": "..."
}
```

> **Note:** The push notification service is an open decision (OD-004). The endpoint structure above assumes the Web Push API. This may be revised when OD-004 is resolved.

---

## DELETE /notifications/push/subscribe

Unregister push notification subscription.  
**Auth:** Required

**Response 204:** No content.

---

## Real-Time Notifications via Supabase Realtime

New notifications are delivered in real time via Supabase Realtime (no polling needed):

```javascript
// Frontend subscription
supabase
  .channel('user-notifications')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'notifications',
    filter: `user_id=eq.${currentUser.id}`,
  }, (payload) => {
    // Increment badge count; show toast
  })
  .subscribe();
```

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

# Contacts API

**Document:** CHKR-API-003  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Documents all contact management endpoints — adding, listing, updating, and removing contacts (both Chikka users and SMS-only contacts).

## Base Path

`/api/v1/contacts`

---

## GET /contacts

Get the authenticated user's contact list.  
**Auth:** Required  
**FR:** FR-CONTACTS-003

**Query params:**
- `type` — `chikka` | `sms` | `all` (default: `all`)
- `status` — `active` | `blocked` | `all` (default: `active`)
- `page`, `page_size`

**Response 200:**
```json
{
  "data": [
    {
      "id": "uuid",
      "contact_type": "chikka",
      "chikka_user": {
        "id": "uuid",
        "username": "jericho_r",
        "display_name": "Jericho Reyes",
        "avatar_url": "...",
        "is_online": true
      },
      "phone_number": null,
      "display_name": null,
      "status": "active",
      "created_at": "2026-11-01T10:00:00Z"
    },
    {
      "id": "uuid",
      "contact_type": "sms",
      "chikka_user": null,
      "phone_number": "+639171234567",
      "display_name": "Lolo Ben",
      "status": "active",
      "created_at": "2026-11-02T09:00:00Z"
    }
  ],
  "pagination": { "total": 2, "page": 1, "page_size": 20, "has_next": false, "has_prev": false },
  "request_id": "..."
}
```

---

## POST /contacts

Add a new contact.  
**Auth:** Required  
**FR:** FR-CONTACTS-001, FR-CONTACTS-002

### Add Chikka User Contact

**Request:**
```json
{
  "contact_type": "chikka",
  "chikka_user_id": "uuid-of-target-user"
}
```

**Response 201:**
```json
{
  "data": {
    "id": "uuid",
    "contact_type": "chikka",
    "chikka_user": { "id": "...", "display_name": "Jericho Reyes", ... },
    "status": "active"
  },
  "request_id": "..."
}
```

**Errors:**
- `404 NOT_FOUND` — target user does not exist or profile is private
- `409 CONFLICT` — contact already exists
- `422 VALIDATION_ERROR` — cannot add yourself as a contact

### Add SMS Contact

**Request:**
```json
{
  "contact_type": "sms",
  "phone_number": "+639171234567",
  "display_name": "Lolo Ben"
}
```

**Response 201:** Contact object with `contact_type: "sms"`.

**Errors:**
- `422 VALIDATION_ERROR` — invalid E.164 phone number format
- `422 SMS_COUNTRY_UNSUPPORTED` — outbound SMS not available for this country
- `409 CONFLICT` — SMS contact with this number already exists

---

## GET /contacts/:contactId

Get a single contact record.  
**Auth:** Required (must own the contact)

**Response 200:** Single contact object.  
**Errors:** `404 NOT_FOUND`, `403 FORBIDDEN`

---

## PATCH /contacts/:contactId

Update a contact's display name, group, or status.  
**Auth:** Required (must own the contact)  
**FR:** FR-CONTACTS-004, FR-CONTACTS-006

**Request:**
```json
{
  "display_name": "Ben Santos (Tatay)",
  "status": "muted"
}
```

Valid `status` values for PATCH: `active`, `muted`.  
Use `POST /contacts/:contactId/block` for blocking.

**Response 200:** Updated contact object.

---

## DELETE /contacts/:contactId

Remove a contact from the list.  
**Auth:** Required (must own the contact)  
**FR:** FR-CONTACTS-003

**Response 204:** No content.

---

## POST /contacts/:contactId/block

Block a contact.  
**Auth:** Required  
**FR:** FR-CONTACTS-004

**Response 200:**
```json
{
  "data": { "id": "uuid", "status": "blocked" },
  "request_id": "..."
}
```

When a contact is blocked:
- They cannot send messages to the blocker.
- They cannot see the blocker's online status.
- They move to the blocked contact list (not removed).

---

## DELETE /contacts/:contactId/block

Unblock a contact.  
**Auth:** Required  
**FR:** FR-CONTACTS-004

**Response 200:**
```json
{
  "data": { "id": "uuid", "status": "active" },
  "request_id": "..."
}
```

---

## GET /contacts/groups

List all contact groups for the authenticated user.  
**Auth:** Required  
**Phase:** 2  
**FR:** FR-CONTACTS-005

**Response 200:**
```json
{
  "data": [
    { "id": "uuid", "name": "Family", "contact_count": 5 },
    { "id": "uuid", "name": "Workmates", "contact_count": 3 }
  ],
  "request_id": "..."
}
```

---

## POST /contacts/groups

Create a new contact group.  
**Auth:** Required  
**Phase:** 2  
**FR:** FR-CONTACTS-005

**Request:**
```json
{ "name": "Family Philippines" }
```

**Response 201:** Group object.

---

## POST /contacts/groups/:groupId/members

Add contacts to a group.  
**Auth:** Required  
**Phase:** 2

**Request:**
```json
{ "contact_ids": ["uuid1", "uuid2"] }
```

**Response 200:** Updated group with member count.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

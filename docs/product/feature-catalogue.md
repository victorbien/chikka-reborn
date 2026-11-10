# Feature Catalogue

**Document:** CHKR-PROD-007  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document catalogues every feature in Chikka Reborn with its module, priority classification (MVP / POST-MVP / FUTURE), development phase, functional requirement cross-reference, and dependency on other features.

## Scope

All features across all modules and phases. This is the single authoritative list of what the platform does.

---

## How to Read This Catalogue

| Column | Meaning |
|---|---|
| Feature ID | Unique identifier (FEAT-XXX-NNN) |
| Feature Name | Short descriptive name |
| Module | Product module (AUTH, CONTACTS, MSG, SMS, SMSRECV, AI, NOTIF, CREDIT, PRIVACY, ADMIN, CLASSIC) |
| Priority | MVP / POST-MVP / FUTURE |
| Phase | Development phase when delivered |
| FR Reference | Functional requirement ID(s) |
| Depends On | Feature IDs that must be delivered first |

---

## Module AUTH — Authentication and User Management

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-AUTH-001 | Email + password registration | MVP | 1 | FR-AUTH-001 | — |
| FEAT-AUTH-002 | Email verification | MVP | 1 | FR-AUTH-002 | FEAT-AUTH-001 |
| FEAT-AUTH-003 | Google OAuth login | MVP | 1 | FR-AUTH-003 | — |
| FEAT-AUTH-004 | GitHub OAuth login | MVP | 1 | FR-AUTH-003 | — |
| FEAT-AUTH-005 | Authenticated session management | MVP | 1 | FR-AUTH-004 | FEAT-AUTH-001 |
| FEAT-AUTH-006 | Password reset via email | MVP | 1 | FR-AUTH-005 | FEAT-AUTH-001 |
| FEAT-AUTH-007 | Login rate limiting | MVP | 1 | FR-AUTH-006 | FEAT-AUTH-005 |
| FEAT-AUTH-008 | User profile create and edit | MVP | 1 | FR-AUTH-007 | FEAT-AUTH-001 |
| FEAT-AUTH-009 | Profile avatar upload | MVP | 1 | FR-AUTH-007 | FEAT-AUTH-008 |
| FEAT-AUTH-010 | Mobile phone number association | MVP | 2 | FR-AUTH-008 | FEAT-AUTH-001 |
| FEAT-AUTH-011 | Mobile OTP verification | MVP | 2 | FR-AUTH-008 | FEAT-AUTH-010 |
| FEAT-AUTH-012 | Account deletion with data erasure | MVP | 1 | FR-AUTH-009 | FEAT-AUTH-001 |

---

## Module CONTACTS — Contacts and Buddy List

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-CONT-001 | Search for Chikka users | MVP | 1 | FR-CONTACTS-001 | FEAT-AUTH-001 |
| FEAT-CONT-002 | Add Chikka user as contact | MVP | 1 | FR-CONTACTS-001 | FEAT-CONT-001 |
| FEAT-CONT-003 | Add SMS contact by phone number | MVP | 2 | FR-CONTACTS-002 | FEAT-AUTH-010 |
| FEAT-CONT-004 | Contact list with alphabetical sort | MVP | 1 | FR-CONTACTS-003 | FEAT-CONT-002 |
| FEAT-CONT-005 | Online presence indicator | MVP | 1 | FR-CONTACTS-003 | FEAT-CONT-004 |
| FEAT-CONT-006 | SMS contact visual distinction | MVP | 2 | FR-CONTACTS-003 | FEAT-CONT-003 |
| FEAT-CONT-007 | Block contact | MVP | 1 | FR-CONTACTS-004 | FEAT-CONT-002 |
| FEAT-CONT-008 | Mute contact | MVP | 1 | FR-CONTACTS-006 | FEAT-CONT-002 |
| FEAT-CONT-009 | Remove contact | MVP | 1 | FR-CONTACTS-003 | FEAT-CONT-002 |
| FEAT-CONT-010 | Contact groups / labels | POST-MVP | 2 | FR-CONTACTS-005 | FEAT-CONT-002 |
| FEAT-CONT-011 | Contact list pagination | MVP | 1 | FR-CONTACTS-003 | FEAT-CONT-004 |

---

## Module MSG — Real-Time Chikka-to-Chikka Messaging

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-MSG-001 | Open conversation with Chikka contact | MVP | 1 | FR-MSG-001 | FEAT-CONT-002 |
| FEAT-MSG-002 | Send real-time text message | MVP | 1 | FR-MSG-001 | FEAT-MSG-001 |
| FEAT-MSG-003 | Message delivery status (Sent/Delivered/Read) | MVP | 1 | FR-MSG-002 | FEAT-MSG-002 |
| FEAT-MSG-004 | Typing indicator | MVP | 1 | FR-MSG-003 | FEAT-MSG-001 |
| FEAT-MSG-005 | Conversation history (paginated) | MVP | 1 | FR-MSG-004 | FEAT-MSG-001 |
| FEAT-MSG-006 | Date separators in conversation | MVP | 1 | FR-MSG-004 | FEAT-MSG-005 |
| FEAT-MSG-007 | Emoji support in messages | MVP | 1 | FR-MSG-006 | FEAT-MSG-002 |
| FEAT-MSG-008 | Offline message queuing | MVP | 1 | FR-MSG-001 | FEAT-MSG-002 |
| FEAT-MSG-009 | Delete message for self | POST-MVP | 2 | FR-MSG-005 | FEAT-MSG-002 |
| FEAT-MSG-010 | Delete message for everyone (5 min window) | POST-MVP | 2 | FR-MSG-005 | FEAT-MSG-002 |
| FEAT-MSG-011 | Conversation list with last message preview | MVP | 1 | FR-MSG-004 | FEAT-MSG-005 |

---

## Module SMS — Internet-to-SMS Messaging

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-SMS-001 | SMS compose screen | MVP | 2 | FR-SMS-001 | FEAT-AUTH-010 |
| FEAT-SMS-002 | E.164 phone number input and validation | MVP | 2 | FR-SMS-001 | FEAT-SMS-001 |
| FEAT-SMS-003 | Country capability check (pre-send) | MVP | 2 | FR-SMS-001 | FEAT-SMS-002 |
| FEAT-SMS-004 | Real-time segment counter | MVP | 2 | FR-SMS-002 | FEAT-SMS-001 |
| FEAT-SMS-005 | Credit cost preview | MVP | 2 | FR-SMS-002 | FEAT-SMS-004, FEAT-CRED-001 |
| FEAT-SMS-006 | Outbound SMS send (simulation mode) | MVP | 2 | FR-SMS-001, FR-SMS-003 | FEAT-SMS-005 |
| FEAT-SMS-007 | Outbound SMS send (live mode) | POST-MVP | 2 | FR-SMS-001 | FEAT-SMS-006 |
| FEAT-SMS-008 | Simulation mode "SIMULATED" badge | MVP | 2 | FR-SMS-003 | FEAT-SMS-006 |
| FEAT-SMS-009 | Delivery status tracking (Queued→Sent→Delivered) | MVP | 2 | FR-SMS-004 | FEAT-SMS-007 |
| FEAT-SMS-010 | Insufficient credit block on send | MVP | 2 | FR-SMS-005 | FEAT-CRED-001 |
| FEAT-SMS-011 | Idempotent send (duplicate prevention) | MVP | 2 | — | FEAT-SMS-006 |
| FEAT-SMS-012 | SMS retry with exponential backoff | MVP | 2 | — | FEAT-SMS-007 |
| FEAT-SMS-013 | Outbound SMS history | MVP | 2 | FR-SMS-001 | FEAT-SMS-006 |

---

## Module SMSRECV — SMS-to-Internet Messaging

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-RECV-001 | Inbound SMS webhook endpoint | MVP | 2 | FR-SMSRECV-001 | FEAT-SMS-007 |
| FEAT-RECV-002 | Webhook signature validation | MVP | 2 | FR-SMSRECV-002 | FEAT-RECV-001 |
| FEAT-RECV-003 | Match inbound SMS to conversation | MVP | 2 | FR-SMSRECV-001 | FEAT-RECV-001, FEAT-SMS-001 |
| FEAT-RECV-004 | Display inbound SMS in conversation thread | MVP | 2 | FR-SMSRECV-001 | FEAT-RECV-003 |
| FEAT-RECV-005 | SMS origin label on inbound messages | MVP | 2 | FR-SMSRECV-003 | FEAT-RECV-004 |
| FEAT-RECV-006 | Unmatched inbound SMS admin alert | POST-MVP | 2 | FR-SMSRECV-001 | FEAT-RECV-001, FEAT-ADMIN-001 |

---

## Module AI — AI-Powered Chikka Assistant

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-AI-001 | Amazon Bedrock provider integration | POST-MVP | 3 | FR-AI-001 | — |
| FEAT-AI-002 | AI provider abstraction layer | POST-MVP | 3 | — | FEAT-AI-001 |
| FEAT-AI-003 | Smart reply suggestions | POST-MVP | 3 | FR-AI-001 | FEAT-AI-002, FEAT-MSG-005 |
| FEAT-AI-004 | Message translation | POST-MVP | 3 | FR-AI-002 | FEAT-AI-002 |
| FEAT-AI-005 | Message rewriting | POST-MVP | 3 | FR-AI-003 | FEAT-AI-002 |
| FEAT-AI-006 | Tone adjustment | POST-MVP | 3 | FR-AI-003 | FEAT-AI-005 |
| FEAT-AI-007 | SMS length optimisation | POST-MVP | 3 | FR-AI-004 | FEAT-AI-002, FEAT-SMS-004 |
| FEAT-AI-008 | Conversation summary | POST-MVP | 3 | FR-AI-005 | FEAT-AI-002, FEAT-MSG-005 |
| FEAT-AI-009 | AI compose from prompt | POST-MVP | 3 | — | FEAT-AI-002 |
| FEAT-AI-010 | AI suggestion review panel | POST-MVP | 3 | FR-AI-006 | FEAT-AI-003 |
| FEAT-AI-011 | AI-assisted badge (pre-send) | POST-MVP | 3 | FR-AI-007 | FEAT-AI-010 |
| FEAT-AI-012 | AI graceful failure (non-blocking) | POST-MVP | 3 | FR-AI-006 | FEAT-AI-001 |
| FEAT-AI-013 | AI usage metadata logging | POST-MVP | 3 | — | FEAT-AI-001 |

---

## Module NOTIF — Notifications

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-NOTIF-001 | In-app message badge | MVP | 1 | FR-NOTIF-001 | FEAT-MSG-002 |
| FEAT-NOTIF-002 | Unread count in browser tab title | MVP | 1 | FR-NOTIF-001 | FEAT-NOTIF-001 |
| FEAT-NOTIF-003 | Browser push notifications | POST-MVP | 2 | FR-NOTIF-002 | FEAT-MSG-002 |
| FEAT-NOTIF-004 | SMS delivery notification | MVP | 2 | FR-NOTIF-003 | FEAT-SMS-009 |
| FEAT-NOTIF-005 | Notification preference settings | POST-MVP | 2 | FR-NOTIF-002 | FEAT-NOTIF-003 |
| FEAT-NOTIF-006 | Notification history view | POST-MVP | 2 | — | FEAT-NOTIF-001 |

---

## Module CREDIT — SMS Credits and Cost Management

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-CRED-001 | Credit balance display | MVP | 2 | FR-CREDIT-001 | FEAT-AUTH-001 |
| FEAT-CRED-002 | Per-country pricing configuration | MVP | 2 | FR-CREDIT-002 | FEAT-ADMIN-005 |
| FEAT-CRED-003 | Credit deduction on SMS acceptance | MVP | 2 | FR-CREDIT-003 | FEAT-SMS-007 |
| FEAT-CRED-004 | Credit refund on permanent failure | MVP | 2 | FR-CREDIT-003 | FEAT-SMS-012 |
| FEAT-CRED-005 | Credit reservation on send attempt | MVP | 2 | FR-CREDIT-003 | FEAT-CRED-003 |
| FEAT-CRED-006 | Low-balance warning | MVP | 2 | — | FEAT-CRED-001 |
| FEAT-CRED-007 | Credit transaction history | POST-MVP | 2 | — | FEAT-CRED-003 |
| FEAT-CRED-008 | Credit top-up via payment gateway | POST-MVP | 4 | FR-CREDIT-004 | FEAT-CRED-001 |

---

## Module PRIVACY — Privacy and Security

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-PRIV-001 | Profile visibility settings | MVP | 1 | FR-PRIVACY-001 | FEAT-AUTH-008 |
| FEAT-PRIV-002 | User data export | POST-MVP | 2 | FR-PRIVACY-002 | FEAT-AUTH-001 |
| FEAT-PRIV-003 | SMS opt-out handling | MVP | 2 | FR-PRIVACY-003 | FEAT-SMS-007 |
| FEAT-PRIV-004 | Message reporting | POST-MVP | 2 | FR-PRIVACY-004 | FEAT-MSG-002 |

---

## Module ADMIN — Administration Dashboard

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-ADMIN-001 | Platform statistics dashboard | POST-MVP | 2 | FR-ADMIN-001 | — |
| FEAT-ADMIN-002 | User list with search and filter | POST-MVP | 2 | FR-ADMIN-002 | FEAT-AUTH-001 |
| FEAT-ADMIN-003 | User suspension and reinstatement | POST-MVP | 2 | FR-ADMIN-002 | FEAT-ADMIN-002 |
| FEAT-ADMIN-004 | SMS provider mode toggle | POST-MVP | 2 | FR-ADMIN-003 | FEAT-SMS-006 |
| FEAT-ADMIN-005 | Country capability configuration | POST-MVP | 2 | FR-ADMIN-005 | — |
| FEAT-ADMIN-006 | SMS audit log view | POST-MVP | 2 | FR-ADMIN-004 | FEAT-SMS-006 |
| FEAT-ADMIN-007 | AI usage metrics | POST-MVP | 3 | FR-ADMIN-006 | FEAT-AI-013 |
| FEAT-ADMIN-008 | Credit transaction overview | POST-MVP | 4 | — | FEAT-CRED-007 |

---

## Module CLASSIC — Classic and Modern Mode

| Feature ID | Feature Name | Priority | Phase | FR Ref | Depends On |
|---|---|---|---|---|---|
| FEAT-MODE-001 | Modern Mode (default UI) | MVP | 1 | FR-CLASSIC-003 | FEAT-AUTH-001 |
| FEAT-MODE-002 | Classic Mode visual theme | POST-MVP | 5 | FR-CLASSIC-002 | FEAT-MODE-001 |
| FEAT-MODE-003 | Mode toggle in settings | POST-MVP | 5 | FR-CLASSIC-001 | FEAT-MODE-002 |
| FEAT-MODE-004 | Mode preference persisted to profile | POST-MVP | 5 | FR-CLASSIC-001 | FEAT-MODE-003, FEAT-AUTH-008 |

---

## Feature Count Summary

| Module | MVP Features | POST-MVP Features | FUTURE Features | Total |
|---|---|---|---|---|
| AUTH | 12 | 0 | 0 | 12 |
| CONTACTS | 10 | 1 | 0 | 11 |
| MSG | 9 | 2 | 0 | 11 |
| SMS | 12 | 1 | 0 | 13 |
| SMSRECV | 5 | 1 | 0 | 6 |
| AI | 0 | 13 | 0 | 13 |
| NOTIF | 3 | 3 | 0 | 6 |
| CREDIT | 6 | 2 | 0 | 8 |
| PRIVACY | 2 | 2 | 0 | 4 |
| ADMIN | 0 | 8 | 0 | 8 |
| CLASSIC | 1 | 3 | 0 | 4 |
| **Total** | **60** | **36** | **0** | **96** |

*Counts verified by script against the feature tables above.*

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

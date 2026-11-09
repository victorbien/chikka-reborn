# UI/UX Guidelines

**Document:** CHKR-DESIGN-001  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document defines the UI/UX design principles, interaction patterns, and standards that govern every screen in Chikka Reborn. These guidelines apply to both Modern Mode and Classic Chikka Mode unless explicitly differentiated.

## Scope

All user-facing screens across all phases. Designers, engineers, and reviewers use this document to evaluate new UI work.

---

## 1. Core Design Principles

### 1.1 Honesty in Every State

The interface never misrepresents the state of the world. Every status shown must be true:

- A message labelled "Delivered" has been confirmed delivered by the provider — not merely accepted.
- A simulated message carries a permanent **SIMULATED** badge that cannot be hidden.
- An AI-generated message carries an **AI-assisted** badge before the user sends it.
- Country capability is displayed accurately — if two-way SMS is unavailable, the UI says so.

### 1.2 All States Must Be Designed

Every data-dependent component must have a designed state for each condition:

| State | Requirement |
|---|---|
| **Loading** | Show a loading skeleton or spinner — never a blank screen |
| **Empty** | Show a friendly empty state with a clear call to action |
| **Success** | Show the data clearly |
| **Error** | Show a human-readable error with a recovery action |

No component is considered complete until all four states are designed and implemented.

### 1.3 Mobile-First, Desktop-Verified

All layouts are designed at 375px (mobile) first. Desktop (1280px) and tablet (768px) layouts are expanded from mobile. Every new screen must be verified at all three breakpoints before review.

### 1.4 Accessible by Default

Accessibility is not a phase 5 audit — it is built into every component from the start. See Section 5 for specific requirements.

### 1.5 Progressive Disclosure

Show users what they need, when they need it. Advanced settings, destructive actions, and infrequently used features are discoverable but not prominent. The compose screen should be simple; AI and segmentation tools appear contextually.

---

## 2. Layout Patterns

### 2.1 Modern Mode — Application Shell

```
┌─────────────────────────────────────────────────────────────┐
│  Top Navigation Bar (height: 56px)                          │
│  [Logo] [Search]               [Credits] [Notif] [Avatar]   │
├──────────────────────┬──────────────────────────────────────┤
│  Sidebar (280px)     │  Main Content Area                   │
│                      │                                       │
│  [Conversations]     │  Active Conversation                 │
│  [Contacts]          │  or                                  │
│  [SMS]               │  Compose Screen                      │
│  [Settings]          │  or                                  │
│  [Admin] (if admin)  │  Settings Panel                      │
│                      │                                       │
└──────────────────────┴──────────────────────────────────────┘
```

Mobile layout: sidebar collapses to a bottom navigation bar (4 icons). Sidebar opens as a drawer on tap.

### 2.2 Classic Mode — Buddy List Shell

```
┌─────────────────────────────────────────────────────────────┐
│  Chikka Reborn Header (nostalgic colour scheme)             │
├─────────────────────┬───────────────────────────────────────┤
│  Buddy List (240px) │  Message Window                       │
│                     │                                       │
│  [Online] ●         │  To: [recipient]                     │
│  - Jericho          │  ┌────────────────────────────────┐  │
│  - Rowena           │  │  Conversation history          │  │
│                     │  │                                │  │
│  [Offline]          │  └────────────────────────────────┘  │
│  - Maria            │  [Message input                  [Send]│
│  - Ben (SMS)        │                                       │
└─────────────────────┴───────────────────────────────────────┘
```

---

## 3. Typography

| Use | Font | Weight | Size |
|---|---|---|---|
| Headings (h1) | System sans-serif | 700 | 24px / 1.5rem |
| Headings (h2) | System sans-serif | 600 | 20px / 1.25rem |
| Body text | System sans-serif | 400 | 16px / 1rem |
| Small / label | System sans-serif | 400 | 14px / 0.875rem |
| Caption / meta | System sans-serif | 400 | 12px / 0.75rem |
| Monospace (IDs) | System monospace | 400 | 13px / 0.8125rem |

System font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`

Classic Mode uses a retro-feeling font (TBD — subject to OD-005) without reproducing licensed Chikka assets.

---

## 4. Colour System

### Modern Mode

| Token | Value | Usage |
|---|---|---|
| `--color-primary` | `#2563EB` (blue-600) | Primary actions, links |
| `--color-primary-hover` | `#1D4ED8` (blue-700) | Button hover |
| `--color-success` | `#16A34A` (green-600) | Delivered status, success states |
| `--color-warning` | `#D97706` (amber-600) | Simulation badge, low balance |
| `--color-error` | `#DC2626` (red-600) | Error states, failed messages |
| `--color-surface` | `#FFFFFF` | Card backgrounds |
| `--color-surface-alt` | `#F3F4F6` | Page background |
| `--color-border` | `#E5E7EB` | Borders, dividers |
| `--color-text-primary` | `#111827` | Primary text |
| `--color-text-secondary` | `#6B7280` | Secondary, meta text |

### SIMULATED Badge

Background: `#D97706` (amber). Text: `#FFFFFF`. Border-radius: 4px. Never removed or hidden.

### AI-Assisted Badge

Background: `#7C3AED` (violet-600). Text: `#FFFFFF`. Visible pre-send only.

### Classic Mode

Colour palette is TBD pending OD-005 (Classic Mode design direction). It should be warm, nostalgic, and clearly distinct from Modern Mode without reproducing licensed Chikka assets.

---

## 5. Accessibility Requirements

All UI must meet **WCAG 2.1 Level AA**:

| Requirement | Standard | Implementation |
|---|---|---|
| Colour contrast | 4.5:1 (normal text), 3:1 (large text) | Verify all colour combinations with a contrast checker |
| Keyboard navigation | All interactive elements reachable by Tab | Use semantic HTML; test with keyboard only |
| Focus indicators | Visible focus ring on all interactive elements | Never use `outline: none` without a replacement |
| Screen reader support | All UI conveys meaning without colour | Use semantic HTML, ARIA roles, labels |
| Form labels | All form fields have associated labels | Use `<label for>` or `aria-label` |
| Error association | Errors programmatically linked to fields | Use `aria-describedby` |
| Images | All images have alt text | Required; empty alt (`alt=""`) for decorative images |
| Motion | Respects `prefers-reduced-motion` | No animations on users who have opted out |

---

## 6. Interaction Patterns

### 6.1 Message Send Flow

1. User types in compose field → character/segment counter updates in real time.
2. Credit cost displayed below counter.
3. Send button enabled only when: message not empty + credits sufficient (for SMS) + recipient set.
4. On send: button shows loading state. Message appears in thread optimistically.
5. On failure: optimistic message shows error indicator. Retry action available.

### 6.2 AI Suggestion Flow

1. User clicks an AI feature button (e.g. "Suggest replies").
2. Button shows loading spinner. Compose field remains fully functional — never disabled.
3. Suggestions appear in a review panel (not in the compose field).
4. User can: accept (populates compose field), edit (populates compose field with suggestion), dismiss, or regenerate.
5. AI-assisted badge appears on the compose field when AI content is present.
6. User explicitly sends — badge disappears from conversation history view of recipient.

### 6.3 Destructive Actions

All destructive actions (delete message, delete account, block contact, switch to live SMS mode) require:
- A clear description of what will happen.
- A confirmation step (dialog with confirm + cancel).
- For high-impact actions (account deletion, live SMS mode toggle): re-authentication required.

### 6.4 Loading Skeletons

Use skeleton placeholders matching the expected content shape:
- Conversation list: skeleton rows with avatar circle + two lines.
- Message thread: skeleton bubbles alternating left/right.
- Contact list: skeleton rows.
- Never show a full-screen blank white page during loading.

---

## 7. Form Guidelines

- Use React Hook Form + Zod for all forms (see `docs/architecture/frontend-architecture.md`).
- Show inline validation errors below the relevant field on blur (not on keystroke).
- Submit button shows loading state during submission; disabled to prevent double-submit.
- Success and error states are communicated inline (not only via toast notifications).
- Phone number fields show format hint (`+63 XXX XXX XXXX`) and validate on blur.
- Password fields include a show/hide toggle.

---

## 8. Notification and Feedback Patterns

| Feedback Type | When | Component |
|---|---|---|
| Toast (success) | Non-critical success (message sent, contact added) | Bottom-right toast, auto-dismiss 3s |
| Toast (error) | Non-critical recoverable error | Bottom-right toast, persist until dismissed |
| Inline error | Form field validation failure | Below the relevant field |
| Full-page error | Critical failure (auth, page load) | Centred error card with retry action |
| Banner | System-level alerts (low credits, SMS mode) | Top of screen, dismissible |
| Badge | Unread message count | On contact/conversation in sidebar |

---

## 9. Responsive Behaviour Summary

| Element | Mobile (375px) | Tablet (768px) | Desktop (1280px) |
|---|---|---|---|
| Navigation | Bottom tab bar (4 icons) | Collapsible sidebar | Full sidebar (280px) |
| Conversation layout | Full-screen | Split 40/60 | Split 280px / remaining |
| AI panel | Bottom sheet | Side panel | Side panel |
| Admin dashboard | Single column | Two column | Three column |
| Credit balance | In bottom bar | In top nav | In top nav |

---

## 10. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

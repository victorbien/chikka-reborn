# Design System

**Document:** CHKR-DESIGN-002  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document defines the component library, design tokens, and composition patterns that make up the Chikka Reborn design system. It ensures visual and behavioural consistency across all screens and phases.

## Scope

All UI components across Modern Mode and Classic Mode. The design system is implemented in the `frontend/src/components/` directory using shadcn/ui as the base layer.

---

## 1. Foundation: shadcn/ui

The Chikka Reborn design system is built on **shadcn/ui** — a collection of accessible, customisable React components built on Radix UI primitives and Tailwind CSS.

### Key Properties
- Components are copied into the codebase (`frontend/src/components/ui/`), not imported from a package — they are owned and extensible.
- All components use Radix UI primitives for accessibility (ARIA, keyboard navigation, focus management).
- Styling is Tailwind CSS utility classes via `cn()` helper (class-variance-authority).
- No inline styles.

### Extending shadcn Components
- Do extend: add variants, sizes, or Chikka-specific compositions on top of shadcn components.
- Do not rebuild: never re-implement Dialog, Dropdown, Tooltip, Popover, or other complex primitives from scratch.

---

## 2. Core Component Inventory

### 2.1 Primitives (from shadcn/ui)

| Component | File | Usage |
|---|---|---|
| Button | `ui/button.tsx` | All clickable actions |
| Input | `ui/input.tsx` | Text inputs |
| Textarea | `ui/textarea.tsx` | Message compose area |
| Label | `ui/label.tsx` | Form field labels |
| Dialog | `ui/dialog.tsx` | Confirmations, AI panels, settings modals |
| Dropdown Menu | `ui/dropdown-menu.tsx` | Message actions, user menu |
| Avatar | `ui/avatar.tsx` | User and contact avatars |
| Badge | `ui/badge.tsx` | Status labels, SIMULATED, AI-assisted |
| Toast | `ui/toast.tsx` + `ui/toaster.tsx` | Feedback notifications |
| Skeleton | `ui/skeleton.tsx` | Loading states |
| Separator | `ui/separator.tsx` | Visual dividers |
| Scroll Area | `ui/scroll-area.tsx` | Conversation thread, contact list |
| Tooltip | `ui/tooltip.tsx` | Icon button labels |
| Sheet | `ui/sheet.tsx` | Mobile sidebar drawer, AI panel on mobile |
| Tabs | `ui/tabs.tsx` | Settings sections, admin dashboard |
| Select | `ui/select.tsx` | Country picker, language picker |
| Switch | `ui/switch.tsx` | Toggle settings |
| Progress | `ui/progress.tsx` | Credit top-up, export progress |

### 2.2 App-Specific Components (`components/common/`)

| Component | Props | Purpose |
|---|---|---|
| `SimulatedBadge` | — | Permanent amber badge for simulated SMS messages |
| `AiAssistedBadge` | `visible: boolean` | Violet badge shown pre-send on AI-composed messages |
| `MessageStatusIcon` | `status: MessageStatus` | Sent / Delivered / Read icons with tooltip |
| `SmsSegmentCounter` | `body: string`, `encoding: 'gsm7' \| 'unicode'` | Live segment + character count display |
| `CreditCostDisplay` | `segments: number`, `costPerSegment: number` | Credit cost preview before SMS send |
| `OnlinePresenceDot` | `isOnline: boolean` | Green/grey presence indicator on contact avatar |
| `EmptyState` | `icon`, `title`, `description`, `action?` | Standardised empty state component |
| `ErrorState` | `message`, `retry?` | Standardised error state with optional retry button |
| `LoadingSpinner` | `size?` | Accessible loading spinner |
| `PageLayout` | `title`, `children` | Standard page wrapper with heading |
| `ConfirmDialog` | `title`, `description`, `onConfirm`, `destructive?` | Reusable confirmation dialog |

---

## 3. Component Variants

### Button Variants

```typescript
// All button usage goes through this component
const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        default:     "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:     "border border-input hover:bg-accent",
        ghost:       "hover:bg-accent hover:text-accent-foreground",
        link:        "underline-offset-4 hover:underline text-primary",
        simulated:   "bg-amber-500 text-white hover:bg-amber-600", // SMS simulation context
      },
      size: {
        default: "h-10 py-2 px-4",
        sm:      "h-9 px-3",
        lg:      "h-11 px-8",
        icon:    "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);
```

### Badge Variants

```typescript
const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default:     "border-transparent bg-primary text-primary-foreground",
        secondary:   "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive text-destructive-foreground",
        outline:     "text-foreground",
        simulated:   "border-transparent bg-amber-500 text-white",   // SIMULATED label
        ai:          "border-transparent bg-violet-600 text-white",  // AI-assisted label
        sms_origin:  "border-transparent bg-blue-100 text-blue-800", // SMS-origin message
      },
    },
  }
);
```

---

## 4. Conversation Message Bubbles

### Modern Mode

```
Outgoing (right-aligned):
┌──────────────────────────────┐
│  Kumusta ka? Miss na kita!   │  ← bg-primary text-white rounded-lg
│                   12:34 ✓✓  │  ← timestamp + status icon
└──────────────────────────────┘

Incoming Chikka (left-aligned):
┌──────────────────────────────┐
│  Maayos naman! Ikaw?         │  ← bg-surface-alt text-primary rounded-lg
│  12:34                       │
└──────────────────────────────┘

Incoming SMS (left-aligned, with badge):
┌──────────────────────────────────┐
│  [SMS] Sige, text mo ko mamaya.  │  ← SMS badge + bg-blue-50
│  12:35                           │
└──────────────────────────────────┘

Simulated outgoing (right-aligned, with badge):
┌──────────────────────────────────┐
│  Hello lola!          [SIMULATED]│  ← amber SIMULATED badge always visible
│                   12:36 queued  │
└──────────────────────────────────┘
```

### Deleted Message Placeholder

```
┌──────────────────────────────────────────┐
│  🚫 This message was deleted             │  ← italic, secondary text colour
└──────────────────────────────────────────┘
```

---

## 5. AI Suggestion Review Panel

```
┌─────────────────────────────────────────────────────────────┐
│  ✨ AI Suggestions                              [×] Dismiss  │
├─────────────────────────────────────────────────────────────┤
│  ○  "Salamat! Ikaw din!"                        [Use]       │
│  ○  "Maayos naman, salamat. Ikaw?"              [Use]       │
│  ○  "Okay lang! Kumusta ka rin?"                [Use]       │
├─────────────────────────────────────────────────────────────┤
│  [Regenerate]                                               │
└─────────────────────────────────────────────────────────────┘
```

- Clicking **[Use]** populates the compose field. Does NOT send.
- The compose field is never disabled while the panel is open.
- The panel appears as a Sheet on mobile, a side panel on desktop.

---

## 6. SMS Compose Counter

```
┌─────────────────────────────────────────────────────────────┐
│  Message                                                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Hello Nanay! Kumusta kayo diyan? Nagpadala na ako    │  │
│  │  ng pera kahapon para sa groceries.                  │  │
│  └───────────────────────────────────────────────────────┘  │
│  123 / 160 chars  |  1 segment  |  0.05 credits           │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░  77%                   │
└─────────────────────────────────────────────────────────────┘
```

- Character count updates on every keystroke.
- Segment count recalculates when character count crosses 160 (GSM-7) or 70 (Unicode).
- Credit cost = segments × cost_per_segment.
- Progress bar fills red when approaching limit.

---

## 7. Notification Patterns

### Toast Notification (Modern Mode)

```
┌────────────────────────────────────────┐
│  ✓  Message delivered to +63****1234   │  ← bottom-right, auto-dismiss 3s
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│  ⚠  Low credit balance: 0.10 credits  │  ← amber, persists until dismissed
│     [Top up now]                       │
└────────────────────────────────────────┘
```

### Inline Error (Form)

```
Email address
┌────────────────────────────────────┐
│  invalid.email                     │
└────────────────────────────────────┘
⚠ Please enter a valid email address.
```

---

## 8. Classic Mode Design Direction

Classic Mode applies a separate CSS theme (`classic-theme.css`) via `data-mode="classic"` on the root element. Component logic is identical; only visual presentation changes.

Design direction (subject to completion of OD-005):
- Warm background tones (cream / off-white) evoking early-2000s web.
- Chunky bordered panels with slight drop shadows.
- Buddy list with "Online / Offline" group headers.
- Message window resembling a classic chat popup.
- No flat design; subtle gradients and borders acceptable.
- **No licensed Chikka assets.** Original designs only.

---

## 9. Iconography

Use **Lucide React** icon library (included with shadcn/ui).

| Icon | Usage |
|---|---|
| `MessageSquare` | Conversations nav item |
| `Users` | Contacts nav item |
| `Phone` | SMS features |
| `Sparkles` | AI assistant features |
| `Bell` | Notifications |
| `CreditCard` | Credits |
| `Settings` | Settings |
| `Shield` | Admin |
| `Check` | Sent status |
| `CheckCheck` | Delivered status |
| `Eye` | Read status |
| `Wifi` | Online presence |
| `WifiOff` | Offline presence |

---

## 10. Implemented Foundation (frontend/)

Tokens live in `frontend/src/index.css` as CSS variables, exposed to Tailwind through `@theme`. Classic and Modern share components; `data-mode` on `<html>` swaps tokens (radius, type scale, density, bevel). The mode is persisted in `localStorage` key `chikka.displayMode` by `DisplayModeProvider`.

| Token group | Modern | Classic |
|---|---|---|
| Canvas / surface | navy `#0b1220` / `#111a2c` | charcoal `#161b24` / `#1f2632` |
| Accent | cyan `#22d3ee` | cyan `#22d3ee` |
| Presence | online lime `#a3e635`, away amber, offline hollow grey | same |
| Radius | 8 / 12 / 16 px | 2 / 4 / 4 px |
| Type | system sans, 16 px | Tahoma/Verdana, 13 px |

Channel and mode labels: Internet (cyan outline), SMS out / SMS in (sky), SIMULATED (amber), LIVE (rose), AI-assisted (violet). Presence uses shape as well as colour. Animations are limited to a notification pulse and are disabled under `prefers-reduced-motion`.

Implemented in `components/shared/`: Avatar, PresenceIndicator, ChannelBadge (with SimulatedBadge, AiAssistedBadge), MessageStatusLabel, MessageBubble, MessageComposer, SmsCostEstimate, CreditBalance, ContactListItem, ConversationItem, NotificationItem, AiSuggestionPanel, EmptyState, ErrorState (error, offline, forbidden), ConfirmDialog, ModeSwitcher. Primitives in `components/ui/`: Button, Dialog.

Behaviour rules enforced and tested: "accepted" never renders as delivered; simulated SMS never shows a credit charge; AI suggestions only fill the composer; the composer sends only on an explicit action; attachments are shown disabled until supported.

---

## 11. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

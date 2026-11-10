---
inclusion: always
---

# Frontend Guidelines

Detailed docs: `docs/architecture/frontend-architecture.md`, `docs/design/design-system.md`, `ui-ux-guidelines.md`, `navigation-structure.md`, `screen-inventory.md`.

## Component Architecture

- Layers: `components/ui` (shadcn primitives) -> `components/shared` (app-wide) -> `features/<name>/components` -> route pages.
- Pages compose; components render. Put logic in hooks (`features/<name>/hooks`).
- Typed props, named exports, small components. No inline styles; use Tailwind utilities.
- Modern Mode and Classic Mode share logic and differ by theme/layout only.

## State Management

- Server state: TanStack Query only. Do not copy server data into component state.
- Local UI state: `useState`/`useReducer`. Form state: React Hook Form + Zod.
- Real-time events update the Query cache (`setQueryData`/invalidate), not parallel stores.
- Query keys are centralised per feature.

## API Integration

- One typed API client in `lib/api` handles base URL, auth header, error envelope parsing, and `request_id`.
- Feature hooks wrap the client (`useMessages`, `useSendSms`). Components never call `fetch` directly.
- Validate form input with Zod before submission. SMS send requests include an idempotency key.
- The frontend never holds provider credentials or calls SMS/AI vendors directly.
- Show segment count and credit cost before sending SMS. Show "SIMULATED" on simulated messages.

## Responsive Design

- Mobile-first, then verify on desktop. Use Tailwind breakpoints; no horizontal scroll at 320px.
- Touch targets at least 44px.

## Accessibility (WCAG 2.1 AA)

- Semantic HTML, labelled controls, visible focus, full keyboard navigation.
- Contrast at least 4.5:1 for text. `alt` text on images. Status is never conveyed by colour alone.
- Announce dynamic updates (new messages, errors) with ARIA live regions.
- Full conformance still needs manual testing with assistive technologies.

## Loading, Empty and Error States

Every data view handles all four: loading (skeleton or spinner), empty (explanatory message with next action), error (readable message, retry, request ID where useful), and success.

- AI loading never blocks the compose field.
- Display delivery status exactly: accepted/queued/sent/delivered/failed/undelivered. Never show "delivered" early.

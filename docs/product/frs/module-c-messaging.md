# Module C — Chikka-to-Chikka Messaging (`MSG`)

Part of the [Functional Requirements Specification](../functional-requirements.md). This module covers messages between two registered users on the platform. It involves no SMS provider and no credits. A conversation has a type: `chikka` (two registered users) or `sms` (a user and a mobile number, Modules D and E). The two types never merge, so a message's channel is always unambiguous. Group chat is out of scope (FUTURE).

"Delivered" in this module means the recipient's client acknowledged receipt. It is not SMS delivery and is never labelled as such.

---

### FR-MSG-001 — Send Chikka Message

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | A user sends a text message to a contact in real time. |
| Preconditions | Verified user. Mutual contact relationship. Neither party has blocked the other. |
| Trigger | User presses Send or Enter in the compose box. |
| Main workflow | 1) Client trims and validates the text. 2) The message appears instantly as `sending` (optimistic) with a client-generated ID. 3) Backend validates, authorises, sanitises and stores it. 4) Status becomes `sent`. 5) The message is pushed to the recipient via Realtime and the conversation list updates. |
| Alternative workflows | A) Recipient offline: message is stored and delivered on next connection. B) Offline sender: message stays `failed` with a retry action. C) Shift+Enter inserts a new line. |
| Expected result | Message stored once and visible to both parties. |
| Error scenarios | Empty or whitespace message: send disabled. Over 2000 characters: 422. Blocked: appears sent to the sender but is not delivered (FR-PRIVACY-006). Rate limit exceeded: 429 and message marked failed. Storage failure: 503 and retry. |
| Dependencies | FR-MSG-013, FR-MSG-007, CC-02, CC-05. |
| Acceptance criteria | AC1 Maximum 2000 characters. AC2 Client ID prevents duplicates on retry. AC3 Message is persisted before being broadcast. AC4 HTML is escaped on render. AC5 Maximum 60 messages per minute per user. |

### FR-MSG-002 — Message Status Indicators

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Senders see per-message status: Sending, Sent, Delivered, Read (when enabled), Failed. |
| Preconditions | A message has been created. |
| Trigger | Status events from the server or recipient client. |
| Main workflow | 1) `sent` is set when the server stores the message. 2) `delivered` is set when the recipient's client acknowledges it. 3) `read` is set per FR-MSG-008. 4) Updates arrive in real time and only move forward. |
| Alternative workflows | A) Recipient disabled read receipts: status stops at Delivered. |
| Expected result | Accurate status icons with accessible text. |
| Error scenarios | Out-of-order events: ignored. Missed realtime event: reconciled on reconnect. |
| Dependencies | FR-MSG-007, FR-MSG-008. |
| Acceptance criteria | AC1 Statuses never regress. AC2 Each status has a text label for screen readers. AC3 Status timestamps are available on hover or focus. AC4 Statuses are never shown for SMS messages using this scheme. |

### FR-MSG-003 — Typing Indicator

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users see when the other party is typing. |
| Preconditions | Both are in an open `chikka` conversation. |
| Trigger | Keystrokes in the compose box. |
| Main workflow | 1) Client sends an ephemeral typing event (throttled to one per 2 seconds). 2) Recipient shows "name is typing…". 3) Indicator clears after 3 seconds without events or on send. |
| Alternative workflows | A) User disabled typing indicators (FR-PRIVACY-005): no events are sent. |
| Expected result | Lightweight liveliness cue. |
| Error scenarios | Realtime failure: indicator silently absent. |
| Dependencies | Supabase Realtime broadcast. |
| Acceptance criteria | AC1 Appears within 500 ms. AC2 Disappears within 3 seconds of stopping. AC3 Never persisted. AC4 Announced politely to assistive tech without interrupting. |

### FR-MSG-004 — Message History and Timestamps

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users view conversation history with accurate timestamps. |
| Preconditions | User is a participant. |
| Trigger | User opens a conversation or scrolls up. |
| Main workflow | 1) The latest 50 messages load. 2) Scrolling up loads older pages using cursor pagination. 3) Each message shows local time; hovering shows the full date and time. 4) Date separators appear between days. 5) Scroll position is preserved on prepend. |
| Alternative workflows | A) New message while scrolled up: "New messages" chip instead of jumping. B) Empty conversation: prompt to say hello. |
| Expected result | Complete, ordered history. |
| Error scenarios | Page load failure: inline retry without losing loaded messages. |
| Dependencies | CC-04. |
| Acceptance criteria | AC1 Ordered by server timestamp, then ID. AC2 Timestamps display in the user's time zone. AC3 Only participants can read the conversation (RLS tested). AC4 Loading, empty, error and success states exist. |

### FR-MSG-005 — Message Deletion Policy

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users can delete their own messages under a defined policy. |
| Preconditions | The user sent the message. |
| Trigger | User selects Delete on a message. |
| Main workflow | 1) Choose "Delete for me" or "Delete for everyone". 2) For me: message is hidden only for the user. 3) For everyone: allowed within 5 minutes of sending; content is cleared and a placeholder "This message was deleted" shown to both. 4) Event is audit logged without content. |
| Alternative workflows | A) After 5 minutes only "Delete for me" is offered. B) Reported messages are retained for moderation despite deletion (FR-PRIVACY-004). |
| Expected result | Policy-consistent deletion on both sides. |
| Error scenarios | Window elapsed during confirmation: 409 with explanation. |
| Dependencies | FR-PRIVACY-004. |
| Acceptance criteria | AC1 Users cannot delete others' messages. AC2 The 5-minute limit is enforced server-side. AC3 Deleted content is removed from search and notifications. AC4 SMS messages cannot be recalled and offer only "Delete for me". |

### FR-MSG-006 — Emoji Support

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Messages support Unicode emoji, with an in-app picker. |
| Preconditions | None. |
| Trigger | User types or picks an emoji. |
| Main workflow | 1) Picker inserts at the cursor. 2) Emoji are stored as UTF-8. 3) Rendered consistently in both UI modes. |
| Alternative workflows | A) Classic Mode may offer classic text emoticons mapped to Unicode. |
| Expected result | Emoji round-trip correctly. |
| Error scenarios | Unsupported glyph: browser fallback glyph. |
| Dependencies | FR-CLASSIC-002. |
| Acceptance criteria | AC1 Stored text equals sent text. AC2 Picker is keyboard accessible. AC3 Emoji count as characters for the length limit by code point. AC4 Sending emoji over SMS switches the message to Unicode segmentation (FR-SMS-002). |

### FR-MSG-007 — Real-Time Message Updates

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User, System |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | New messages, status changes, edits and deletions arrive without refresh, and recover after disconnects. |
| Preconditions | Signed in. |
| Trigger | Database change or realtime event. |
| Main workflow | 1) Client subscribes to its conversations over Supabase Realtime. 2) Events update the TanStack Query cache. 3) On disconnect the client shows a "reconnecting" banner. 4) On reconnect it fetches messages since the last known ID and merges them. |
| Alternative workflows | A) Realtime unavailable: fall back to polling every 10 seconds. |
| Expected result | The UI converges to server truth. |
| Error scenarios | Duplicate events: de-duplicated by message ID. Auth token expiry: refreshed or user prompted to sign in. |
| Dependencies | Supabase Realtime, FR-NOTIF-001. |
| Acceptance criteria | AC1 Delivery to an online recipient within 2 seconds under normal conditions. AC2 No duplicates or gaps after reconnect. AC3 Users only receive events for their own conversations (RLS). AC4 Connection state is shown to the user. |

### FR-MSG-008 — Read Receipts

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | When both users enable them, senders see when messages were read. |
| Preconditions | Both participants have read receipts enabled (default off for new accounts). |
| Trigger | Recipient views unread messages in an open conversation. |
| Main workflow | 1) Visible messages are reported as read (batched). 2) Server records `read_at`. 3) Sender sees "Read" with time. |
| Alternative workflows | A) Either user disables receipts: no new receipts are sent or shown; existing ones remain. |
| Expected result | Receipts only where both parties agree. |
| Error scenarios | Report failure: retried quietly. |
| Dependencies | FR-PRIVACY-005, FR-MSG-002. |
| Acceptance criteria | AC1 Default is disabled. AC2 Unread counts clear when messages are viewed even without receipts. AC3 Turning receipts off stops new receipts immediately. |

### FR-MSG-009 — Message Search

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users search their own message history. |
| Preconditions | Signed in. |
| Trigger | User enters a query in conversation or global search. |
| Main workflow | 1) Query is validated (2 to 100 characters). 2) Backend runs a participant-scoped full-text search. 3) Results show snippet, contact, date and channel. 4) Selecting a result opens the conversation at that message. |
| Alternative workflows | A) Within-conversation search. B) No results: empty state. |
| Expected result | Relevant results across channels. |
| Error scenarios | Rate limit: 429. Search service error: readable message. |
| Dependencies | PostgreSQL full-text search, RLS. |
| Acceptance criteria | AC1 Results include only messages the user may see. AC2 Deleted messages are not returned. AC3 Queries are parameterised. AC4 Search content is not written to logs. |

### FR-MSG-010 — Attachments

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent (`chikka` conversations only; not supported over SMS) |
| Description | Users send images and documents in Chikka conversations. |
| Preconditions | Verified user in a `chikka` conversation. |
| Trigger | User picks or drops a file. |
| Main workflow | 1) Client checks type and size and shows a preview. 2) Upload goes to private Supabase Storage via a signed URL. 3) Backend validates MIME by content inspection, then links the file to a message. 4) Recipient sees a thumbnail or file chip and downloads through a short-lived signed URL. |
| Alternative workflows | A) Cancel upload. B) Attach multiple files, up to 5. |
| Expected result | Files are shared privately. |
| Error scenarios | Disallowed type or size: 422. Upload interrupted: retry. Malware or content check failure (if scanning enabled): file blocked. |
| Dependencies | Supabase Storage with RLS, FR-MSG-001. |
| Acceptance criteria | AC1 Allowed: JPEG, PNG, WebP, GIF, PDF; maximum 10 MB each. AC2 Files are private and access-controlled to participants. AC3 Images have alt text or file name labels. AC4 The attach control is absent in SMS conversations, with an explanation. |

### FR-MSG-011 — Message Editing Policy

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users can edit their own sent Chikka messages for a short period. |
| Preconditions | The user sent the message less than 15 minutes ago. Not deleted. |
| Trigger | User selects Edit. |
| Main workflow | 1) Message content loads into the editor. 2) User saves. 3) Server validates and stores the new content, retaining the previous version for moderation. 4) Both sides see the updated text with an "edited" marker. |
| Alternative workflows | A) Cancel. B) Window elapsed: edit not offered. |
| Expected result | Corrected message, transparent edit state. |
| Error scenarios | Window elapsed or message deleted: 409. Same content: no change. |
| Dependencies | FR-MSG-007. |
| Acceptance criteria | AC1 Edit window is 15 minutes, enforced server-side. AC2 Edited messages show an "edited" marker. AC3 Previous versions are available to admins on a report only. AC4 SMS messages cannot be edited. |

### FR-MSG-012 — Conversation Management

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users manage their conversation list: pin, archive, mute, mark unread, and delete for themselves. |
| Preconditions | A conversation exists. |
| Trigger | User opens the conversation menu or swipes on mobile. |
| Main workflow | 1) Pin keeps up to 5 conversations at the top. 2) Archive hides without deleting; a new message unarchives it unless muted. 3) Mute follows FR-CONTACTS-006. 4) Delete conversation clears the user's own view only. 5) Unread counts are shown on each row. |
| Alternative workflows | A) Bulk archive. B) Undo toast after archive or delete. |
| Expected result | An organised inbox. |
| Error scenarios | Action fails: UI reverts. |
| Dependencies | FR-CONTACTS-006, FR-NOTIF-001. |
| Acceptance criteria | AC1 Deleting a conversation does not delete it for the other party. AC2 Archive state persists across devices. AC3 Actions are keyboard accessible. AC4 Sorting is by latest activity with pinned first. |

### FR-MSG-013 — Start or Open Conversation

| Field | Detail |
|---|---|
| Module | C — Messaging |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Selecting a Chikka contact opens the single existing conversation or creates it. |
| Preconditions | Mutual contact relationship. |
| Trigger | User selects a contact or "New message". |
| Main workflow | 1) Backend looks up the conversation for the pair. 2) If absent, creates it atomically. 3) The client navigates to it with the compose box focused. |
| Alternative workflows | A) Concurrent creation by both users: unique constraint ensures one conversation. |
| Expected result | Exactly one `chikka` conversation per pair. |
| Error scenarios | Not a contact or blocked: 403 with neutral message. |
| Dependencies | FR-CONTACTS-010. |
| Acceptance criteria | AC1 A unique pair constraint prevents duplicates. AC2 Creation is idempotent. AC3 Focus moves to the compose box for keyboard users. |

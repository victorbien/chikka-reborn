# Module B — Contacts and Buddy List (`CONTACTS`)

Part of the [Functional Requirements Specification](../functional-requirements.md). Two contact types exist: **Chikka contacts** (registered users, mutual after acceptance) and **SMS contacts** (a mobile number the user may message by SMS; the person need not be registered).

---

### FR-CONTACTS-001 — Add Chikka Contact (Send Request)

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | A user adds a registered Chikka user by sending a contact request. Revised from v1.0 (follow model replaced by request and acceptance). |
| Preconditions | Verified user. Target is discoverable (FR-PRIVACY-001) and has not blocked the sender. |
| Trigger | User selects "Add" on a search result (FR-CONTACTS-007) or profile. |
| Main workflow | 1) User optionally adds a short note. 2) Backend creates a `pending` request. 3) Recipient is notified (FR-NOTIF-007). 4) UI shows "Request sent". |
| Alternative workflows | A) Reverse request already pending: both users become contacts at once. B) Already contacts: no-op with message. C) Target not found: neutral result. |
| Expected result | A pending request exists; no contact relationship until accepted. |
| Error scenarios | Blocked by target: neutral "request sent" shown, nothing created (no leak). Request limit exceeded: 429. Self-add: 422. Duplicate pending: idempotent success. |
| Dependencies | FR-CONTACTS-009, FR-CONTACTS-010, FR-PRIVACY-006, CC-02. |
| Acceptance criteria | AC1 Requests are limited to 30 per day per user. AC2 A blocked sender cannot discover they are blocked. AC3 Note is limited to 140 characters and sanitised. AC4 Duplicate requests do not create duplicate rows. |

### FR-CONTACTS-002 — Add SMS Contact

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** (number storage is identical; capability checks are configuration-driven) |
| Description | A user saves a mobile number as an SMS contact. |
| Preconditions | Verified user. |
| Trigger | User submits the "Add SMS contact" form. |
| Main workflow | 1) User enters name and number. 2) Number is normalised to E.164. 3) Country capability is looked up (FR-SMS-007). 4) Contact is saved with type `sms`. 5) If the number matches a registered, discoverable user, the UI suggests sending a Chikka request instead. |
| Alternative workflows | A) Unsupported country: contact is saved but flagged "SMS not available" with explanation. B) Duplicate number: offer to open the existing contact. |
| Expected result | SMS contact appears in the list with an SMS badge. Adding a contact does not record recipient consent (see FR-PRIVACY-007). |
| Error scenarios | Invalid number: 422. Number on the opt-out list: saved, but flagged "recipient opted out". |
| Dependencies | FR-SMS-006, FR-SMS-007, FR-PRIVACY-008. |
| Acceptance criteria | AC1 Numbers are stored in E.164. AC2 Duplicate numbers per user are rejected. AC3 Capability warnings are visible before the first send. AC4 Phone numbers are masked in logs. |

### FR-CONTACTS-003 — Contact List Display

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users see their contacts as a buddy list with presence. |
| Preconditions | Signed in. |
| Trigger | User opens the contacts panel. |
| Main workflow | 1) Backend returns a paginated list. 2) Favourites are pinned first, then groups, then alphabetical order. 3) Chikka contacts show a presence dot; SMS contacts show an SMS badge. 4) Selecting a contact opens or creates the conversation. |
| Alternative workflows | A) Empty list: onboarding prompt with "Find people" and "Add SMS contact". B) Group filter selected. |
| Expected result | Fast, scannable list reflecting live presence. |
| Error scenarios | Load failure: error state with retry. Presence unavailable: dots hidden, list still usable. |
| Dependencies | FR-CONTACTS-011, FR-CONTACTS-014, FR-CONTACTS-005. |
| Acceptance criteria | AC1 Paginated beyond 50 contacts. AC2 Presence dot has an accessible text label, not colour alone. AC3 All four states (loading, empty, error, success) are implemented. AC4 Blocked contacts do not appear in the main list. |

### FR-CONTACTS-004 — Block Contact

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | A user blocks a Chikka or SMS contact. |
| Preconditions | Contact or conversation exists, or user is blocking from a report flow. |
| Trigger | User selects "Block". |
| Main workflow | 1) Confirmation dialog explains effects. 2) Block record is created. 3) Conversation is hidden from the main list. 4) Enforcement per FR-PRIVACY-006 begins immediately. 5) Optional "also report". |
| Alternative workflows | A) Block an unknown inbound SMS sender (FR-SMSRECV-010). B) Block from a contact request. |
| Expected result | Blocked party cannot interact; they receive no notice. |
| Error scenarios | Block save fails: nothing changes, retry offered. |
| Dependencies | FR-PRIVACY-006, FR-PRIVACY-004. |
| Acceptance criteria | AC1 Blocked user cannot message, request, or see the blocker's presence. AC2 Blocked list is separate and reviewable. AC3 Blocking is reversible (FR-CONTACTS-012). AC4 Blocked inbound SMS is stored but not shown or notified. |

### FR-CONTACTS-005 — Contact Groups

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users organise contacts into named groups (labels). Groups are private organisation only, not group chats. |
| Preconditions | Signed in. |
| Trigger | User creates a group, or assigns a contact. |
| Main workflow | 1) Create group (name, optional colour). 2) Assign contacts (multi-select). 3) Group appears in the sidebar and filters the list. 4) Rename or delete group; contacts remain. |
| Alternative workflows | A) Reorder groups. B) Removing last contact leaves an empty group. |
| Expected result | Contacts can be browsed by group. |
| Error scenarios | Duplicate group name: 409. Over 20 groups: 422. |
| Dependencies | FR-CONTACTS-003. |
| Acceptance criteria | AC1 A contact can belong to multiple groups. AC2 Deleting a group never deletes contacts. AC3 Group names are 1 to 30 characters, sanitised. AC4 Groups are visible only to their owner. |

### FR-CONTACTS-006 — Mute Contact

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | A user mutes a contact so messages arrive silently. |
| Preconditions | Contact exists. |
| Trigger | User toggles Mute. |
| Main workflow | 1) Choose duration (1 hour, 8 hours, 1 week, until turned off). 2) Mute flag is saved. 3) Messages are still delivered and stored. 4) No badges, sounds, push or email for that contact. |
| Alternative workflows | A) Mute expires automatically. |
| Expected result | Quiet conversation, nothing lost. |
| Error scenarios | Save failure: toggle reverts with error. |
| Dependencies | FR-NOTIF-005. |
| Acceptance criteria | AC1 Muted contact's messages still appear in history. AC2 No notifications of any type fire while muted. AC3 Mute is reversible and the sender is not informed. |

### FR-CONTACTS-007 — Search Contacts and Users

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users search their contacts and discoverable users. |
| Preconditions | Verified user. |
| Trigger | User types in the search box. |
| Main workflow | 1) Input is debounced (300 ms, minimum 2 characters). 2) Backend searches own contacts first, then discoverable users by exact username or exact email. 3) Results show display name, avatar and relationship state. |
| Alternative workflows | A) No results: empty state with a suggestion to add an SMS contact. B) Search by mobile number only if the target enabled number discoverability (FR-PRIVACY-005). |
| Expected result | Relevant results without exposing private users. |
| Error scenarios | Rate limit hit: 429 with message. Query too short: no request sent. |
| Dependencies | FR-PRIVACY-001, FR-PRIVACY-005, CC-02. |
| Acceptance criteria | AC1 Private profiles never appear. AC2 Global user search requires exact match (no browsing or enumeration). AC3 Maximum 20 searches per minute per user. AC4 Blocked users are excluded in both directions. |

### FR-CONTACTS-008 — Import Contacts (With Permission)

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent (import creates SMS contacts only, no messages sent) |
| Description | Users import contacts from a vCard or CSV file, or the browser Contact Picker where supported, after giving explicit permission. |
| Preconditions | Verified user. |
| Trigger | User chooses "Import contacts". |
| Main workflow | 1) Permission notice explains what is read and that nothing is uploaded until confirmed. 2) User picks a file or contacts. 3) Client parses and shows a preview with duplicates and invalid numbers highlighted. 4) User selects rows and confirms. 5) Backend creates SMS contacts. 6) Summary shown (added, skipped, invalid). |
| Alternative workflows | A) Cancel at preview: nothing is stored. B) Matching registered users are offered as Chikka requests, never auto-added. |
| Expected result | Selected entries become SMS contacts. |
| Error scenarios | Malformed file: readable parse error. Over 500 rows: rejected with limit message. Permission denied in picker: manual add offered. |
| Dependencies | FR-CONTACTS-002, FR-PRIVACY-007. |
| Acceptance criteria | AC1 No contact data leaves the browser before the user confirms the preview. AC2 Imported contacts do not imply SMS consent. AC3 Raw import files are never stored. AC4 Import is limited to 500 rows. AC5 Consent to import is recorded (FR-PRIVACY-007). |

### FR-CONTACTS-009 — Contact Requests (Pending List)

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users view incoming and outgoing contact requests. |
| Preconditions | Signed in. |
| Trigger | User opens the Requests tab, or follows a notification. |
| Main workflow | 1) Incoming and outgoing lists load with sender, note and date. 2) Incoming rows offer Accept and Reject (FR-CONTACTS-010). 3) Outgoing rows offer Cancel. 4) Badge counts update in real time. |
| Alternative workflows | A) Empty state with explanation. B) Requests older than 30 days expire automatically. |
| Expected result | Users see and manage pending requests. |
| Error scenarios | Request already resolved elsewhere: row removed with message. |
| Dependencies | FR-CONTACTS-001, FR-NOTIF-007. |
| Acceptance criteria | AC1 Cancelling an outgoing request removes it for the recipient. AC2 Expired requests no longer appear. AC3 Lists are paginated. |

### FR-CONTACTS-010 — Accept or Reject Contact Request

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | A user accepts or rejects an incoming request. |
| Preconditions | A pending incoming request exists. |
| Trigger | User selects Accept, Reject, or Reject and block. |
| Main workflow | 1) Accept: mutual contact rows are created in one transaction. 2) Requester is notified. 3) Both users see each other's allowed presence. 4) Reject: request is closed silently, no notification to requester. |
| Alternative workflows | A) Reject and block applies FR-CONTACTS-004. B) Accept and add to group. |
| Expected result | Relationship matches the decision. |
| Error scenarios | Request cancelled meanwhile: friendly message. Transaction failure: no partial relationship. |
| Dependencies | FR-CONTACTS-009, FR-NOTIF-007. |
| Acceptance criteria | AC1 Accept creates exactly two linked contact rows atomically. AC2 A rejected requester gets no signal and may re-request only after 7 days. AC3 Decisions are audit logged. |

### FR-CONTACTS-011 — Favourite Contacts

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users mark contacts as favourites. |
| Preconditions | Contact exists. |
| Trigger | User toggles the star. |
| Main workflow | 1) Flag saved. 2) Contact appears in a Favourites section at the top. 3) Unstar removes it. |
| Alternative workflows | A) Favourite filter. |
| Expected result | Quick access to key contacts. |
| Error scenarios | Save failure: toggle reverts. |
| Dependencies | FR-CONTACTS-003. |
| Acceptance criteria | AC1 Toggle is keyboard operable with an accessible name. AC2 Favourites persist across sessions. AC3 Favourite status is visible only to the owner. |

### FR-CONTACTS-012 — Unblock Contact

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | A user removes a block. |
| Preconditions | Block exists. |
| Trigger | User selects Unblock in the blocked list. |
| Main workflow | 1) Confirmation. 2) Block removed. 3) Contact returns to the list if the relationship existed; otherwise a new request is required. 4) Messages sent while blocked remain hidden. |
| Alternative workflows | A) Unblock an SMS number: inbound SMS handling resumes. |
| Expected result | Interaction is possible again, not retroactive. |
| Error scenarios | Save failure: remains blocked with error. |
| Dependencies | FR-CONTACTS-004, FR-PRIVACY-006. |
| Acceptance criteria | AC1 Unblocking is audit logged. AC2 Messages received during the block are not delivered retroactively. AC3 Unblocking does not re-add a removed contact. |

### FR-CONTACTS-013 — Recent Contacts

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | A recent list shows the people the user last interacted with. |
| Preconditions | At least one conversation exists. |
| Trigger | User opens the Recent tab or the new message picker. |
| Main workflow | 1) Backend returns the latest 20 contacts by last message time. 2) Entries show last-message preview (respecting privacy) and time. 3) Selecting opens the conversation. |
| Alternative workflows | A) Empty state. B) User clears recent list (hides, does not delete messages). |
| Expected result | Fast return to ongoing conversations. |
| Error scenarios | Load error with retry. |
| Dependencies | FR-MSG-012. |
| Acceptance criteria | AC1 Ordered by latest activity. AC2 Blocked contacts excluded. AC3 Clearing the list does not delete conversations. |

### FR-CONTACTS-014 — Online and Offline Status Display

| Field | Detail |
|---|---|
| Module | B — Contacts |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Contacts display presence consistently across the app. |
| Preconditions | Contact relationship exists; contact shares presence. |
| Trigger | Presence event, or list render. |
| Main workflow | 1) Client subscribes to presence for visible contacts only. 2) UI shows Online, Away, Busy or Offline with "last seen" when allowed. 3) SMS contacts show no presence. |
| Alternative workflows | A) Contact hides status: "Status hidden". B) Connection lost: stale indicators greyed with "unknown". |
| Expected result | Accurate presence without leaking hidden states. |
| Error scenarios | Subscription failure: fall back to polling every 60 seconds or hide indicators. |
| Dependencies | FR-AUTH-013, FR-PRIVACY-005. |
| Acceptance criteria | AC1 Updates visible within 5 seconds. AC2 Status uses text plus icon, not colour alone. AC3 Last seen is hidden when the contact opted out. |

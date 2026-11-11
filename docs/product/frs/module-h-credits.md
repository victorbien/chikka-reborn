# Module H — SMS Credits (`CREDIT`)

Part of the [Functional Requirements Specification](../functional-requirements.md).

**Two ledgers, never mixed.**
- **Live credits** are the real balance. They change only through live-mode SMS acceptance, refunds, administrator adjustments and (Phase 4) paid top-ups.
- **Demo credits** are a separate balance used only in simulation mode so the credit experience can be demonstrated. Every demo ledger entry has `is_simulated = true`, is labelled SIMULATED in the UI, has no monetary value, and can never be converted into live credits.

This reconciles two rules: simulation must never deduct real credits and incur no cost, and the product must demonstrate deduction, history and low-credit behaviour. See OPEN-02 for the alternative of not modelling demo credits at all.

**Units.** 1 credit equals one GSM-7 segment to the base-rate country. Each destination country has a multiplier (FR-CREDIT-002). Amounts are stored as integers (credits x 100) to avoid floating-point errors.

---

### FR-CREDIT-001 — Credit Balance Display

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** (shows the balance for the current mode) |
| Description | Users always see their available balance. |
| Preconditions | Signed in. |
| Trigger | Page load, or balance change. |
| Main workflow | 1) The header shows the balance for the active mode: "Demo credits 40 SIMULATED" or "Credits 120". 2) The balance updates in real time after changes. 3) Clicking opens the credits page with the balance, recent activity and rates. |
| Alternative workflows | A) Pending reservation (a send in progress) is shown as "reserved". |
| Expected result | The user never has to guess their balance. |
| Error scenarios | Balance load failure: shows "unavailable" and disables SMS send rather than guessing. |
| Dependencies | FR-CREDIT-007. |
| Acceptance criteria | AC1 The balance equals the sum of ledger entries. AC2 Demo and live balances are never combined. AC3 The balance has an accessible label including its type. |

### FR-CREDIT-002 — Per-Country Pricing

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | Admin, User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Credit cost per segment is configured per destination country. |
| Preconditions | Admin access for edits. |
| Trigger | Admin edits rates, or a user previews cost. |
| Main workflow | 1) Admin sets a credit multiplier per country, with an effective-from date. 2) Rates are versioned. 3) Users see the rate in the preview (FR-SMS-002). 4) The rate used is stored on each message. |
| Alternative workflows | A) Missing rate: sending is blocked in live mode, and uses the default demo rate in simulation. |
| Expected result | Transparent, auditable costs. |
| Error scenarios | Negative or zero rate: 422. |
| Dependencies | FR-ADMIN-005. |
| Acceptance criteria | AC1 Changes need no deployment. AC2 Rate changes never alter past messages. AC3 Changes are audit logged with admin ID. AC4 The user sees the same rate the server charges. |

### FR-CREDIT-003 — Credit Deduction and Refund (Live)

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | System |
| Priority / Phase | MVP / 2 |
| Mode | **Live only** (simulation uses FR-CREDIT-006) |
| Description | Credits are deducted when the provider accepts a live message and refunded if it fails permanently. |
| Preconditions | Message sent in live mode. |
| Trigger | Provider acceptance, or permanent failure. |
| Main workflow | 1) At queue time the estimated cost is reserved against the available balance. 2) On `accepted` the reservation becomes a deduction in the ledger. 3) On permanent failure after retries, a compensating refund entry is written. 4) Retries do not create additional deductions. 5) Each entry logs user ID, message ID, provider, country, segments, amount and timestamp. |
| Alternative workflows | A) Provider rejects before acceptance: the reservation is released without a ledger deduction. B) Segment count differs from the estimate: the difference is adjusted once. |
| Expected result | Users pay only for accepted messages, and are refunded for permanent failures. |
| Error scenarios | Ledger write fails after acceptance: the entry is retried from a durable job and reconciled. |
| Dependencies | FR-SMS-009, FR-SMS-010, FR-SMS-012. |
| Acceptance criteria | AC1 Deduction and ledger entry are committed atomically. AC2 Refunds happen exactly once per message. AC3 No deduction occurs for simulation messages. AC4 The ledger is append-only. AC5 Concurrent sends cannot overdraw the balance. |

### FR-CREDIT-004 — Credit Top-Up

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | User |
| Priority / Phase | POST-MVP / 4 |
| Mode | **Live only** (no real payment in the hackathon MVP) |
| Description | Users purchase live credits through a payment gateway (gateway undecided, OD-001). |
| Preconditions | Payment gateway integrated. Verified user. |
| Trigger | User selects a credit package. |
| Main workflow | 1) Pick a package. 2) Payment is processed by the gateway. 3) A verified gateway webhook confirms payment. 4) Credits are added by a ledger entry. 5) Receipt shown. |
| Alternative workflows | A) Payment fails or is cancelled: no credit. B) Refunds follow the gateway process. |
| Expected result | Credits are added only after confirmed payment. |
| Error scenarios | Webhook delayed: pending state shown. Duplicate webhook: idempotent. |
| Dependencies | Payment gateway, webhook validation. |
| Acceptance criteria | AC1 Credits never added before confirmation. AC2 Gateway webhooks are signature validated. AC3 Top-up history is visible. AC4 Card data never touches the platform. AC5 Not implemented in the MVP; real money requires explicit human approval. |

### FR-CREDIT-005 — Estimated SMS Cost

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | The cost estimate shared by compose, confirmation and AI optimisation views. |
| Preconditions | Country and segment count known. |
| Trigger | Preview rendering. |
| Main workflow | 1) Cost = segments x country multiplier. 2) Shown in credits, plus an equivalent currency value if prices are configured. 3) Shown as "estimated" until accepted. |
| Alternative workflows | A) Cost not available: FR-SMS-002 alternative A. |
| Expected result | One consistent figure everywhere. |
| Error scenarios | Rate lookup failure: "Cost unavailable". |
| Dependencies | FR-CREDIT-002, FR-SMS-002. |
| Acceptance criteria | AC1 Preview equals the amount reserved. AC2 Cost updates when recipient or text changes. AC3 Simulated estimates say SIMULATED. |

### FR-CREDIT-006 — Simulated Credit Deduction

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | User, System |
| Priority / Phase | MVP / 2 |
| Mode | **Simulation only** |
| Description | Simulation mode deducts demo credits to demonstrate the credit flow, without touching live credits or incurring cost. |
| Preconditions | Simulation mode. |
| Trigger | A simulated message is accepted by `MockSmsProvider`. |
| Main workflow | 1) Each new user receives a one-time demo grant (default 50 demo credits). 2) The same reserve, deduct and refund logic runs against the demo ledger. 3) All entries are marked SIMULATED. 4) Admins can reset a user's demo balance. |
| Alternative workflows | A) Demo credits exhausted: the user sees insufficient-credit behaviour (FR-CREDIT-009), and admins can top up demo credits. |
| Expected result | Credit behaviour can be demonstrated with no cost. |
| Error scenarios | Not applicable. |
| Dependencies | FR-CREDIT-003 logic, FR-SMS-003. |
| Acceptance criteria | AC1 No live ledger entry is created in simulation. AC2 Demo entries are labelled SIMULATED everywhere. AC3 Demo credits cannot be exported to live credits. AC4 Switching modes switches which balance is displayed. |

### FR-CREDIT-007 — Transaction History

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Users view a ledger of credit movements. |
| Preconditions | Signed in. |
| Trigger | User opens Credits, History. |
| Main workflow | 1) Paginated list: date, type (grant, reservation, deduction, refund, adjustment, top-up), amount, running balance, related message. 2) Filter by type, date range, and live or simulated. 3) Export as CSV. |
| Alternative workflows | A) Empty state with explanation. |
| Expected result | Full transparency. |
| Error scenarios | Load failure with retry. |
| Dependencies | FR-CREDIT-003, FR-CREDIT-006. |
| Acceptance criteria | AC1 Each entry records user ID, message ID, provider, country, segments, amount and timestamp. AC2 Running balance reconciles with the displayed balance. AC3 Users see only their own entries. AC4 Simulated entries carry the SIMULATED label. |

### FR-CREDIT-008 — Low-Credit Warning

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | The credits page and compose view warn when the balance is low. |
| Preconditions | Balance under the threshold. |
| Trigger | Balance change, or page load. |
| Main workflow | 1) A banner warns in the credits view and compose screen. 2) A notification is created once per crossing (FR-NOTIF-004). |
| Alternative workflows | A) User sets a custom threshold between 1 and 100. |
| Expected result | Early warning. |
| Error scenarios | Not applicable. |
| Dependencies | FR-NOTIF-004. |
| Acceptance criteria | AC1 Threshold is configurable. AC2 The banner has text and an icon. AC3 It does not block sending. |

### FR-CREDIT-009 — Insufficient Credit Handling

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | User, System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Sends that cannot be covered are refused, with a helpful explanation. |
| Preconditions | Cost exceeds the available balance. |
| Trigger | Send attempt. |
| Main workflow | 1) The server rejects with 402 `INSUFFICIENT_CREDITS` and the shortfall. 2) The UI explains the shortfall and the options: shorten the message (with an AI optimisation shortcut if enabled), top up when available, or contact the administrator. 3) The draft is retained. |
| Alternative workflows | A) Retries that would exceed the balance are not started. |
| Expected result | No overdraft, no data loss. |
| Error scenarios | Balance race: whichever reservation commits first wins. |
| Dependencies | FR-SMS-005, FR-CREDIT-003. |
| Acceptance criteria | AC1 Overdrafts are impossible (concurrency tested). AC2 Draft text preserved. AC3 Error uses the standard error envelope. |

### FR-CREDIT-010 — Administrator Credit Adjustments

| Field | Detail |
|---|---|
| Module | H — Credits |
| User role | Admin |
| Priority / Phase | POST-MVP / 4 (demo-credit adjustments MVP / 2) |
| Mode | **Both** (live adjustments are real) |
| Description | Admins grant, revoke or correct credits with a recorded reason. |
| Preconditions | Admin role and recent re-authentication. |
| Trigger | Admin submits the adjustment form for a user. |
| Main workflow | 1) Select user, ledger (live or demo), signed amount and mandatory reason. 2) Confirmation step shows the resulting balance. 3) A ledger entry of type `adjustment` is written. 4) The user is notified. 5) The action is audit logged. |
| Alternative workflows | A) Adjustments above a threshold (default 1000 credits) need a second admin approval (FUTURE). |
| Expected result | Traceable corrections. |
| Error scenarios | Negative resulting balance: refused unless explicitly allowed. Missing reason: 422. |
| Dependencies | FR-ADMIN-010, CC-03. |
| Acceptance criteria | AC1 Reason is mandatory. AC2 Adjustments are append-only ledger entries. AC3 Admins cannot edit or delete past entries. AC4 Live adjustments need explicit confirmation text. |

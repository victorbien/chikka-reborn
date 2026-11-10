# Module F — AI Chikka Assistant (`AI`)

Part of the [Functional Requirements Specification](../functional-requirements.md). Governing rules are in `.kiro/steering/ai-guidelines.md` and `docs/architecture/ai-architecture.md`.

**Mode.** AI features always use the `AiProvider` abstraction backed by Amazon Bedrock (live). Tests use a fake provider. Any demo-only mock provider would have to be labelled "DEMO AI" in the UI (see OPEN-03); it is not specified here.

**Invariants for every requirement in this module:**
- AI output is a suggestion shown in a review panel. It enters the compose box only when the user explicitly accepts it.
- AI never sends anything. There is no auto-send, scheduled send or background dispatch (FR-AI-006).
- AI failures never block manual composing, sending or reading (FR-AI-012).
- Only the minimum necessary text is sent to the model (FR-AI-013).
- Metadata is logged; message content is not (CC-07).
- AI is Phase 3, so none of this is built in the MVP phases.

---

### FR-AI-001 — Smart Reply Suggestions

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Offer 2 to 3 short reply options based on the recent conversation. |
| Preconditions | AI is enabled for the user (FR-AI-013). A conversation with at least one inbound message exists. |
| Trigger | User presses "Suggest replies". |
| Main workflow | 1) Backend loads the last N messages (default 6) and strips identifiers such as phone numbers. 2) Calls `suggest_replies`. 3) The panel shows suggestions with a loading state. 4) User clicks one to copy it into the compose box (not sent), or dismisses or regenerates. |
| Alternative workflows | A) Regenerate (rate limited). B) SMS conversation: suggestions respect segment limits and show segment count. |
| Expected result | Editable reply drafts. |
| Error scenarios | Timeout, quota or model error: FR-AI-012. Empty or too short context: "Not enough conversation to suggest replies". |
| Dependencies | `AiProvider`, FR-AI-006, FR-AI-007, FR-AI-010. |
| Acceptance criteria | AC1 Returns 2 or 3 suggestions in the conversation's language. AC2 Nothing is inserted until the user clicks. AC3 Selecting never sends. AC4 The compose box stays usable while loading. AC5 Only recent context is sent. |

### FR-AI-002 — Message Translation

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Translate a received message, or the user's draft, into a chosen language. |
| Preconditions | AI enabled. Target language selected. |
| Trigger | User selects "Translate" on a message or in the compose box. |
| Main workflow | 1) User picks the target language (FR-AI-010). 2) Backend calls `translate`. 3) The translation appears beneath the original in a clearly marked panel. 4) For drafts, "Use translation" copies it to the compose box. |
| Alternative workflows | A) Source language auto-detected by the model for display only. B) Show original again with one click. |
| Expected result | Understandable text without losing the original. |
| Error scenarios | Unsupported language: error with options. Failure: user may still send the original (FR-AI-012). Output equals input: shown as "already in this language". |
| Dependencies | FR-AI-010, FR-AI-012. |
| Acceptance criteria | AC1 The original is always preserved and visible. AC2 Translations of received messages are not stored in the conversation, only in AI history if enabled. AC3 Translated draft shows the AI-assisted badge. AC4 Translation never auto-replaces the user's text. |

### FR-AI-003 — Message Rewriting

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Rewrite a draft for clarity or grammar. |
| Preconditions | Draft of at least 3 characters. |
| Trigger | User selects "Improve" with a goal: clarity, grammar, or custom instruction. |
| Main workflow | 1) Backend validates the instruction against an allow-list (custom text is length limited and treated as data). 2) Calls `rewrite`. 3) A before-and-after diff view is shown. 4) User accepts, edits or discards. |
| Alternative workflows | A) Accept part of the rewrite. B) Regenerate. |
| Expected result | Improved text, meaning preserved. |
| Error scenarios | Failure: original draft untouched. Output blank or over the limit: discarded with a message. |
| Dependencies | FR-AI-006, FR-AI-007. |
| Acceptance criteria | AC1 Original is retained until the user accepts. AC2 Custom instructions cannot override the system prompt (injection tested). AC3 Prompts are fixed constants with user content passed as structured data. AC4 Result carries an AI-assisted badge once accepted. |

### FR-AI-004 — SMS Length Optimisation

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock); segment counts computed by the platform |
| Description | Shorten a draft to fit a target number of SMS segments while preserving meaning. |
| Preconditions | SMS draft exists. |
| Trigger | User selects "Fit to SMS" and a target (1 segment or a chosen maximum). |
| Main workflow | 1) The platform computes current encoding, characters and segments. 2) Backend calls the model with the target. 3) The platform recomputes characters, segments and cost for the result (never trusts the model's counts). 4) The panel shows before and after with counts and credits. 5) User accepts, edits or discards. |
| Alternative workflows | A) The model indicates that meaning cannot be preserved in the target: this is shown plainly, with the closest option. B) Suggest switching to GSM-7 by replacing characters (such as smart quotes) to avoid Unicode. |
| Expected result | A shorter draft with verified counts. |
| Error scenarios | Result still over target: shown with an "Over target" notice. |
| Dependencies | FR-SMS-002, FR-CREDIT-005. |
| Acceptance criteria | AC1 Counts shown are computed server-side. AC2 Meaning loss is disclosed, not hidden. AC3 Nothing is sent. AC4 Accepted text carries an AI-assisted badge. |

### FR-AI-005 — Conversation Summary

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Summarise the recent part of a conversation. |
| Preconditions | At least 5 messages in scope. |
| Trigger | User selects "Summarise". |
| Main workflow | 1) User selects scope (last 20 messages by default, or last 24 hours). 2) Backend calls `summarise`. 3) A summary panel shows a concise paragraph. 4) User can copy the summary or dismiss it. |
| Alternative workflows | A) Summary in a chosen language (FR-AI-010). |
| Expected result | Quick catch-up. |
| Error scenarios | Too few messages: friendly message. Failure: FR-AI-012. |
| Dependencies | FR-AI-013. |
| Acceptance criteria | AC1 The summary is never inserted into the conversation automatically. AC2 Dismissing has no side effects. AC3 Scope is shown so the user knows what was summarised. AC4 Disabled for conversations the user has excluded from AI. |

### FR-AI-006 — Mandatory User Approval Before Sending

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User, System |
| Priority / Phase | POST-MVP / 3 (applies from the first release of any AI feature) |
| Mode | Live and Simulation |
| Description | AI-generated content is never sent without a deliberate user action. |
| Preconditions | AI content is present in a draft. |
| Trigger | User attempts to send. |
| Main workflow | 1) Accepting AI text only places it in the compose box. 2) The user may edit it. 3) Sending requires the normal send action and the confirmation dialog for SMS (FR-SMS-008). |
| Alternative workflows | None. There is no setting that weakens this requirement. |
| Expected result | The user is the author of every sent message. |
| Error scenarios | Any API request attempting to send AI content without a user-initiated send request is rejected. |
| Dependencies | FR-SMS-008, FR-MSG-001. |
| Acceptance criteria | AC1 No AI endpoint calls a send function. AC2 There is no auto-send, scheduled AI send or background dispatch. AC3 An automated test proves that AI endpoints cannot create messages. AC4 This requirement is not configurable. |

### FR-AI-007 — AI-Assisted Badge

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live and Simulation |
| Description | Drafts that were composed or significantly changed by AI are visibly marked before sending. |
| Preconditions | AI text accepted into a draft. |
| Trigger | Accepting an AI suggestion. |
| Main workflow | 1) The draft shows an "AI-assisted" badge with text. 2) Editing the text keeps the badge unless the user clears the AI content entirely. 3) The SMS confirmation dialog shows it. 4) After sending, the message record stores `ai_assisted = true` for the sender's own history. |
| Alternative workflows | A) Minor edits (punctuation) after accepting do not remove the badge. |
| Expected result | Transparent AI involvement. |
| Error scenarios | Not applicable. |
| Dependencies | FR-AI-006. |
| Acceptance criteria | AC1 Badge is visible on unsent drafts. AC2 Badge is not visible to the recipient. AC3 Badge has a text alternative. AC4 The flag is recorded on the message. |

### FR-AI-008 — Tone Adjustment

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Adjust the tone of a draft: formal, casual, friendly or professional. |
| Preconditions | Draft exists. |
| Trigger | User selects a tone. |
| Main workflow | 1) Tone is validated against the fixed list. 2) Backend calls `rewrite` with the tone instruction. 3) The result is shown beside the original. 4) User accepts, regenerates or discards. |
| Alternative workflows | A) Preview several tones side by side (rate limited). |
| Expected result | Same meaning, different register. |
| Error scenarios | FR-AI-012. |
| Dependencies | FR-AI-003. |
| Acceptance criteria | AC1 Only the four defined tones are accepted. AC2 Original stays available. AC3 Facts, names and numbers are preserved (evaluated by tests with sample fixtures). |

### FR-AI-009 — AI Message Composition

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Draft a full message from a short prompt. |
| Preconditions | AI enabled. |
| Trigger | User selects "Compose with AI" and enters a brief prompt. |
| Main workflow | 1) User describes the message (maximum 300 characters), optionally picks tone and target language. 2) Backend calls `complete` with the fixed composition prompt. 3) The draft appears in the panel. 4) User edits and accepts into the compose box. |
| Alternative workflows | A) SMS target: the draft is constrained to a maximum segment count. |
| Expected result | A first draft the user controls. |
| Error scenarios | Prompt rejected by validation or policy: neutral message. FR-AI-012 for provider errors. |
| Dependencies | FR-AI-006, FR-AI-007. |
| Acceptance criteria | AC1 Output is not placed in the compose box until accepted. AC2 The prompt cannot alter system instructions. AC3 The badge is applied on acceptance. |

### FR-AI-010 — Language Selection

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Users choose input and output languages for AI features. |
| Preconditions | Profile language set. |
| Trigger | User opens the language picker. |
| Main workflow | 1) The picker lists supported languages (initially English, Filipino/Tagalog, Cebuano, Spanish, Japanese, Arabic; configurable). 2) The choice applies to translation, composition and summaries. 3) The default is the profile language. |
| Alternative workflows | A) "Same language as conversation" is the default for smart replies. |
| Expected result | Output in the intended language. |
| Error scenarios | Language not in list: 422. |
| Dependencies | FR-AUTH-007. |
| Acceptance criteria | AC1 Language codes are validated against the supported list. AC2 Prompts instruct the model to answer in the target language. AC3 Right-to-left output displays correctly. AC4 Translation to Unicode languages warns about SMS segmentation cost. |

### FR-AI-011 — AI Request History

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User, Admin |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Users can review and delete their recent AI requests. Admins see aggregates only. |
| Preconditions | AI request completed. |
| Trigger | User opens Settings, AI history. |
| Main workflow | 1) Each request stores: feature, timestamp, language, accepted or dismissed, model ID, token counts and latency. 2) If history content is enabled, input and output text are stored with RLS and retained for 30 days. 3) The list is paginated and filterable by feature. 4) The user can delete entries or clear all. |
| Alternative workflows | A) User turns off content history: only metadata is kept. B) Admin view shows counts and token totals only (FR-ADMIN-006). |
| Expected result | Transparency and cost visibility without leaking content. |
| Error scenarios | Deletion failure: error with retry. |
| Dependencies | FR-ADMIN-006, CC-07. |
| Acceptance criteria | AC1 Content is only visible to its owner. AC2 Content is never written to application logs. AC3 Content older than 30 days is purged. AC4 Admins cannot read content from the dashboard. |

### FR-AI-012 — Failure Handling, Fallback and Rate Limits

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User, System |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | AI failures degrade gracefully and usage is limited. |
| Preconditions | An AI request is made. |
| Trigger | Timeout, throttle, quota, invalid output or provider outage. |
| Main workflow | 1) Retry once for transient errors with a short backoff. 2) On failure return a structured error with a user-readable message ("Suggestions are unavailable right now"). 3) Log the provider detail server-side only. 4) The UI keeps the compose box and send actions fully usable. |
| Alternative workflows | A) Per-user limit (default 30 requests per hour) returns 429 with remaining time. B) A kill switch disables AI features globally (FR-ADMIN-013). |
| Expected result | AI problems never block messaging. |
| Error scenarios | Output fails validation (empty, wrong language, too long): treated as failure. |
| Dependencies | `AiProvider`, CC-02. |
| Acceptance criteria | AC1 Provider error details never reach the client. AC2 Manual sending works while AI is failing (tested). AC3 Rate limits are enforced server-side. AC4 Request timeout is 15 seconds. |

### FR-AI-013 — AI Privacy Controls and Data Minimisation

| Field | Detail |
|---|---|
| Module | F — AI Assistant |
| User role | User |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Users control whether AI features are used, and requests send only what is needed. |
| Preconditions | AI feature available. |
| Trigger | First AI use, and Settings changes. |
| Main workflow | 1) On first use, a notice explains that selected message text is sent to an AI service, what is kept, and that AI never sends messages. The user accepts or declines (recorded as consent, FR-PRIVACY-007). 2) Settings allow turning AI off globally or per conversation. 3) The backend redacts phone numbers, emails and long digit sequences from context before the call. |
| Alternative workflows | A) Declined: AI controls are hidden or disabled with an explanation. B) Withdrawn consent stops all further AI use immediately. |
| Expected result | Informed, reversible participation. |
| Error scenarios | Consent record save fails: AI remains disabled. |
| Dependencies | FR-PRIVACY-007. |
| Acceptance criteria | AC1 No AI request is made without recorded consent. AC2 Context is limited to the minimum (default last 6 messages). AC3 Redaction is unit tested. AC4 Withdrawal takes effect on the next request. |

# AI Assistant API

**Document:** CHKR-API-006  
**Project:** Chikka Reborn  
**Version:** 2.0  
**Status:** Implemented (Module F)  
**Last Revised:** November 2026  

---

## Purpose

Documents the AI assistant endpoints. All of them return drafts for the user to review. None sends a message. Design: ADL-021 in [architecture-decisions.md](../architecture/architecture-decisions.md).

## Base Path

`/api/v1/ai`. Every endpoint needs a signed-in user with a verified email. Responses use the standard envelope (`data`, `request_id`; errors as `error.code`, `error.message`, `error.details`).

## AI Safety Invariant

> **No AI endpoint sends a message.** The frontend puts a draft in the message box only when the user accepts it, and the user sends it with a separate, explicit action. Accepting a draft shows an "AI-assisted" badge on the message being written.

## Access rules

Each AI request passes these checks in order:

| Check | Failure |
|---|---|
| Administrator switch (`system_settings.ai_enabled`) | `503 ai_disabled_by_admin` |
| The user turned the assistant on (`PUT /ai/settings`, default off) | `403 ai_not_enabled` |
| Hourly limit (`system_settings.ai_user_limit_per_hour`, default 30) | `429 rate_limited` with `Retry-After` |
| Conversation features: caller is a member (else `404 not_found`) and has not turned AI off for that conversation | `403 ai_disabled_for_conversation` |

Optimising an SMS that already fits in the target segment count is answered locally: no model call, no limit hit, nothing logged.

## Common response fields

Every draft response includes:

| Field | Meaning |
|---|---|
| `assistance_id` | Id to report the user's decision against. `null` if the log write failed or no model call was made |
| `model_id` | Model that answered (`mock-ai-1` for the demo provider) |
| `latency_ms` | Time spent on the model call |
| `simulated` | `true` when the demo provider answered. The UI says so |
| `message` | Set when there is no usable draft: `"Couldn't generate a suggestion..."` (empty or invalid model output, `200`) or a refusal by the model |

## Errors

| Status | Code | When | User impact |
|---|---|---|---|
| 422 | `validation_error` | Unknown field, empty or oversize text, unsupported language, bad count | Field message |
| 422 | `no_context` | The conversation has no messages the assistant may read | Message in panel |
| 502 | `ai_unavailable` | Timeout, outage, throttling or a credential problem at the provider. `details.reason` is `timeout`, `throttled`, `unavailable` or `configuration`. Timeouts and outages are retried once first | Panel shows an error; the message box keeps working |
| 429 | `rate_limited` | Hourly limit | Panel shows that AI is paused |

Provider error text, prompts and message content never appear in errors.

---

## GET /ai/status

Whether the assistant is available and on for the caller.

```json
{ "data": { "available": true, "enabled": false, "simulated": true,
  "model_id": "mock-ai-1", "max_text_chars": 1600,
  "languages": [ { "code": "en", "name": "English" }, { "code": "fil", "name": "Filipino (Tagalog)" } ] } }
```

Languages: `en`, `fil`, `es`, `ceb`, `ilo`, `hil`, `ja`, `zh`, `ko`, `fr`. Quality for regional languages depends on the model (OD-002).

## PUT /ai/settings

`{ "enabled": true }` turns the assistant on or off for the caller. Recorded in the audit log as a `consent` event (`ai.enabled`, `ai.disabled`). Returns the new status.

## POST /ai/suggest-replies

`{ "conversation_id": "uuid", "context_message_count": 10, "count": 3 }` (`context_message_count` 1-20, `count` 1-5). Chikka conversations only.

Returns `suggestions` (distinct, at most `count`).

## POST /ai/translate

`{ "text": "...", "target_language": "fil", "source_language": "en" }`. `source_language` is optional (auto-detect) and must differ from the target. Text is 1-1600 characters.

Returns `original_text`, `translated_text`, `source_language`, `target_language`.

## POST /ai/rewrite

`{ "text": "...", "instruction": "make_professional", "tone": null }`.

`instruction` is one of `make_professional`, `make_friendly`, `make_formal`, `make_casual`, `shorten`, `improve_clarity`, `fix_grammar`, `adjust_tone`. `adjust_tone` requires `tone` (`formal`, `casual`, `friendly`, `professional`). Returns `original_text`, `rewritten_text`, `instruction`.

## POST /ai/optimise-sms

`{ "text": "...", "max_segments": 1 }` (`max_segments` 1-10). The encoding is detected server-side.

```json
{ "data": {
  "original_text": "...", "optimised_text": "...",
  "original":  { "characters": 181, "units": 181, "segments": 2, "encoding": "gsm7" },
  "optimised": { "characters": 52,  "units": 52,  "segments": 1, "encoding": "gsm7" },
  "max_segments": 1, "within_target": true, "meaning_preserved": true,
  "assistance_id": "uuid", "model_id": "...", "latency_ms": 900, "simulated": false, "message": null } }
```

- Segment counts come from the server's GSM-7 / Unicode analysis (160/153 and 70/67 per segment). They are estimates; the carrier decides the final split.
- `optimised_text` is `null` with an explanatory `message` when the model says the meaning cannot be kept, when the output is invalid, or when the rewrite saves no segment. Nothing is silently truncated.
- `within_target` is `false` when the shorter version still exceeds `max_segments`.
- `meaning_preserved` is the model's own claim and is not verified. The user must read the draft.
- No cost or saving is stated. Prices depend on the provider and verified routes.
- Typographic quotes, dashes and ellipses in the output are replaced with GSM-7 characters.

## POST /ai/summarise

`{ "conversation_id": "uuid", "message_count": 20, "length": "medium" }` (`message_count` 2-50, `length` `short`, `medium` or `long`). Chikka conversations only. Returns `summary` and `messages_summarised`.

## POST /ai/compose

`{ "prompt": "Tell my friend I will be 15 minutes late", "context": [], "max_length": 160, "language": "fil" }`. `prompt` is 1-300 characters, `context` up to 5 short strings used for tone only, `max_length` 20-1600, `language` optional. Output longer than `max_length` is rejected, not truncated.

Returns `composed_text`, `character_count` and `segments` (the SMS size estimate).

## POST /ai/assistance/{assistance_id}/decision

`{ "decision": "accepted" | "edited" | "dismissed" }`. Records what the user did with a draft. Only the owner can update the row; anyone else gets `404`. The frontend calls it fire-and-forget.

---

## Privacy

- Conversation features send at most the newest 20 (replies) or 50 (summary) text messages, each cut to 500 characters, within a 6000-character budget. Lines are labelled `me` or `them`; names and ids are not sent.
- Emails and numbers of eight or more digits in conversation context are replaced with `[email]` and `[number]`. The user's own draft and compose prompt are sent as written.
- `ai_assistance_logs` keeps feature, model, prompt version, language, outcome, token counts, latency, error code, the user's decision and a SHA-256 of the output. It never stores prompts, drafts or conversation text. Application logs hold the same metadata.
- Cleared and hidden messages, messages deleted for everyone, and conversations where the member turned AI off are never read.

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
| 2.0 | November 2026 | Kiro | Implemented. Opt-in and status endpoints, decision endpoint, `adjust_tone` and `make_professional`, summary length, segment objects (`gsm7` / `ucs2`), `502 ai_unavailable`, empty output as `200` with a message |

# AI Assistant API

**Document:** CHKR-API-006  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Documents all AI assistant endpoints. All endpoints return suggestions only — none trigger message sending.

## Base Path

`/api/v1/ai`

---

## AI Safety Invariant

> **No AI endpoint sends a message. All AI endpoints return suggestions for user review.**
> 
> The frontend places AI output in the compose field only when the user explicitly accepts a suggestion. The user then sends the message via a separate explicit action. This is a permanent, non-configurable constraint.

---

## POST /ai/suggest-replies

Generate smart reply suggestions based on conversation context.  
**Auth:** Required  
**Phase:** 3  
**FR:** FR-AI-001

**Request:**
```json
{
  "conversation_id": "uuid",
  "context_message_count": 10,
  "count": 3
}
```

Fields:
- `conversation_id` — the conversation to generate replies for
- `context_message_count` — number of recent messages to include as context (default 10, max 20)
- `count` — number of suggestions to generate (default 3, max 5)

**Response 200:**
```json
{
  "data": {
    "suggestions": [
      "Salamat! Ikaw din!",
      "Maayos naman, salamat. Ikaw?",
      "Okay lang! Kumusta ka rin?"
    ],
    "model_id": "anthropic.claude-3-haiku-...",
    "latency_ms": 1240
  },
  "request_id": "..."
}
```

**Errors:**
- `404 NOT_FOUND` — conversation does not exist or user is not a participant
- `422 VALIDATION_ERROR` — invalid count or context parameters
- `502 PROVIDER_ERROR` — Bedrock unavailable (non-blocking; user can still type manually)
- `429 RATE_LIMITED` — AI request limit exceeded

---

## POST /ai/translate

Translate a message into a specified language.  
**Auth:** Required  
**Phase:** 3  
**FR:** FR-AI-002

**Request:**
```json
{
  "text": "I hope you are feeling better soon.",
  "target_language": "fil",
  "source_language": "en"
}
```

Fields:
- `text` (required) — text to translate (max 1600 chars)
- `target_language` (required) — BCP 47 language tag (e.g. `fil`, `ceb`, `ilo`, `en`, `ja`)
- `source_language` (optional) — BCP 47 tag; omit for auto-detect

**Response 200:**
```json
{
  "data": {
    "original_text": "I hope you are feeling better soon.",
    "translated_text": "Umaasa akong mabilis kang mabuting muli.",
    "source_language": "en",
    "target_language": "fil",
    "model_id": "anthropic.claude-3-haiku-...",
    "latency_ms": 980
  },
  "request_id": "..."
}
```

**Supported language codes (non-exhaustive):**
`en` (English), `fil` (Filipino/Tagalog), `ceb` (Cebuano), `ilo` (Ilocano), `hil` (Hiligaynon), `ja` (Japanese), `zh` (Chinese), `ko` (Korean), `es` (Spanish), `fr` (French)

> **Note:** Actual language support depends on the selected Bedrock model (OD-002). Verify supported languages when model is finalised.

**Errors:** `422` — unsupported language code; `502 PROVIDER_ERROR`

---

## POST /ai/rewrite

Rewrite a draft message per a specified instruction.  
**Auth:** Required  
**Phase:** 3  
**FR:** FR-AI-003

**Request:**
```json
{
  "text": "hey can we meet tmrw",
  "instruction": "make_formal"
}
```

Valid `instruction` values:
- `improve_clarity` — improve readability and clarity
- `fix_grammar` — correct grammar and spelling only
- `make_formal` — shift to formal/professional tone
- `make_casual` — shift to casual/conversational tone
- `shorten` — reduce length while preserving meaning (distinct from SMS optimisation)

**Response 200:**
```json
{
  "data": {
    "original_text": "hey can we meet tmrw",
    "rewritten_text": "Hi, would you be available to meet tomorrow?",
    "instruction": "make_formal",
    "model_id": "...",
    "latency_ms": 870
  },
  "request_id": "..."
}
```

---

## POST /ai/optimise-sms

Shorten a message to fit within SMS segment limits while preserving meaning.  
**Auth:** Required  
**Phase:** 3  
**FR:** FR-AI-004

**Request:**
```json
{
  "text": "I just wanted to let you know that the team meeting has been rescheduled from Wednesday to next Thursday at 3pm in the main conference room.",
  "max_segments": 1,
  "encoding": "gsm7"
}
```

Fields:
- `text` (required) — original message (max 1600 chars)
- `max_segments` (required) — target maximum segment count (1–10)
- `encoding` — `gsm7` (160 chars/segment) or `unicode` (70 chars/segment)

**Response 200:**
```json
{
  "data": {
    "original_text": "I just wanted to let you know that...",
    "optimised_text": "Team meeting moved: next Thu 3pm, main conf room.",
    "original_length": 137,
    "optimised_length": 49,
    "original_segments": 1,
    "optimised_segments": 1,
    "encoding": "gsm7",
    "meaning_preserved": true,
    "model_id": "...",
    "latency_ms": 1100
  },
  "request_id": "..."
}
```

If meaning cannot be preserved within the segment limit:
```json
{
  "data": {
    "meaning_preserved": false,
    "message": "The message cannot be shortened to 1 segment without losing important information. Consider splitting into 2 messages.",
    "optimised_text": null
  }
}
```

The AI never silently truncates a message. If meaning preservation is not possible, it says so explicitly.

---

## POST /ai/summarise

Summarise a conversation thread.  
**Auth:** Required (must be a conversation participant)  
**Phase:** 3  
**FR:** FR-AI-005

**Request:**
```json
{
  "conversation_id": "uuid",
  "message_count": 20
}
```

- `message_count` — number of most recent messages to summarise (default 20, max 50)

**Response 200:**
```json
{
  "data": {
    "summary": "Maria and Jose discussed plans for the weekend. They agreed to meet on Saturday at 3pm near the SM mall. Jose mentioned he would bring food.",
    "messages_summarised": 18,
    "model_id": "...",
    "latency_ms": 1850
  },
  "request_id": "..."
}
```

---

## POST /ai/compose

Compose a full message from a brief user prompt.  
**Auth:** Required  
**Phase:** 3

**Request:**
```json
{
  "prompt": "Tell my mom I arrived safely and will call her tonight",
  "context": ["Previous messages for tone reference"],
  "max_length": 160,
  "language": "fil"
}
```

Fields:
- `prompt` (required) — user's intent description (max 300 chars)
- `context` (optional) — recent messages to inform tone/language
- `max_length` (optional) — target character limit (useful for SMS)
- `language` (optional) — target language BCP 47 code

**Response 200:**
```json
{
  "data": {
    "composed_text": "Nanay, nakarating na ako nang ligtas. Tatawag ako mamaya ng gabi.",
    "character_count": 64,
    "language_detected": "fil",
    "model_id": "...",
    "latency_ms": 1320
  },
  "request_id": "..."
}
```

---

## AI Rate Limits and Error Behaviour

All AI endpoints share these behaviours:

| Scenario | Response | User Impact |
|---|---|---|
| Provider timeout | `502 PROVIDER_ERROR` | Error shown in panel; compose field remains active |
| Rate limit exceeded | `429 RATE_LIMITED` with retry-after header | "AI features temporarily paused" message; compose field active |
| Empty/unusable response | `200` with `null` result + `message` | "Couldn't generate suggestion. Try again." |
| Invalid input | `422 VALIDATION_ERROR` | Field-level error message |

AI failures **never** block manual message composition or sending.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

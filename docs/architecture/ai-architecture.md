# AI Architecture

**Document:** CHKR-ARCH-006  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document defines the architecture of the Chikka Reborn AI subsystem — how AI features are structured, how Amazon Bedrock is integrated, prompt design, safety constraints, and the user approval flow that governs all AI-generated content.

## Scope

All AI features (Phase 3+). The AI subsystem has no runtime dependencies on SMS features and can be developed and deployed independently.

---

## 1. AI Subsystem Overview

```mermaid
graph TB
    subgraph "Frontend"
        COMPOSE[Message Compose]
        AI_BTN[AI Feature Buttons]
        REVIEW[AI Suggestion Review Panel]
        ACCEPT[Accept / Edit / Dismiss]
    end

    subgraph "FastAPI Backend"
        AI_ROUTE[/api/v1/ai/*]
        AI_SVC[AiService]
        LOG_SVC[AiUsageLogger]
    end

    subgraph "Provider Layer"
        ABSTRACT[AiProvider ABC]
        BEDROCK[BedrockAiProvider]
    end

    subgraph "AWS"
        BROCK_API[Amazon Bedrock\nInvokeModel API]
    end

    subgraph "Database"
        AI_LOGS[(ai_usage_logs\nmetadata only)]
    end

    AI_BTN --> AI_ROUTE
    AI_ROUTE --> AI_SVC
    AI_SVC --> ABSTRACT
    ABSTRACT --> BEDROCK
    BEDROCK --> BROCK_API
    BROCK_API -->> BEDROCK
    BEDROCK -->> AI_SVC
    AI_SVC --> LOG_SVC
    LOG_SVC --> AI_LOGS
    AI_SVC -->> AI_ROUTE
    AI_ROUTE -->> REVIEW
    REVIEW --> ACCEPT
    ACCEPT -->|user approves| COMPOSE
    COMPOSE -->|user explicitly sends| MSG_ROUTE[POST /messages or /sms/send]
```

**Critical:** The arrow from `ACCEPT` to `COMPOSE` populates the compose field only. No AI path leads directly to a send endpoint. The user must explicitly trigger the send.

---

## 2. Provider Abstraction

All AI calls go through `AiProvider` ABC. `BedrockAiProvider` is the production implementation. A `MockAiProvider` is used in tests.

```python
# providers/ai/bedrock_provider.py
import boto3
from .base import AiProvider

class BedrockAiProvider(AiProvider):
    def __init__(self, settings: Settings):
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.model_id = settings.bedrock_model_id

    async def translate(self, text: str, target_language: str, ...) -> str:
        prompt = TRANSLATE_SYSTEM_PROMPT
        user_content = f"<text>{text}</text>\n<target>{target_language}</target>"
        return await self._invoke(prompt, user_content)

    async def _invoke(self, system: str, user: str, max_tokens: int = 512) -> str:
        # Uses httpx.AsyncClient to call Bedrock synchronously via thread pool
        # or awaits native async Bedrock client when available
        ...
```

> **⚠ Model Selection:** The specific Bedrock model (e.g. `anthropic.claude-3-haiku-20240307-v1:0`) is an open decision (OD-002). The `BEDROCK_MODEL_ID` environment variable allows swapping without code changes. Model availability must be confirmed in the target AWS region before Phase 3 begins (DEP-006).

---

## 3. AI Features and Endpoints

| Feature | Endpoint | Input | Output |
|---|---|---|---|
| Smart Replies | `POST /ai/suggest-replies` | `conversation_id`, context count, suggestion count | `list[str]` suggestions |
| Translation | `POST /ai/translate` | `text`, `target_language`, optional `source_language` | Translated string |
| Rewriting | `POST /ai/rewrite` | `text`, `instruction` | Rewritten string |
| Tone Adjustment | `POST /ai/rewrite` | `text`, `instruction=make_formal\|make_casual` | Adjusted string |
| SMS Optimisation | `POST /ai/optimise-sms` | `text`, `max_segments`, `encoding` | Optimised text, char count, segment count, `meaning_preserved` flag |
| Conversation Summary | `POST /ai/summarise` | `conversation_id`, `message_count` | Summary paragraph |
| AI Compose | `POST /ai/compose` | `prompt`, optional `context` | Composed message |

All endpoints return suggestions only. None trigger message send.

---

## 4. Prompt Architecture

### Design Rules

1. System prompts are **static constants** defined in `services/ai_service.py`. They are never constructed dynamically from user input.
2. User-supplied content is injected as **structured XML-tagged data** within the user message turn, not as raw text appended to the system prompt.
3. Prompts explicitly instruct the model to return **only the requested content** — no preamble, no meta-commentary, no "Sure, here is..." filler.
4. Prompts instruct the model to respond in **the language of the target message** (for translation features) or the conversation's dominant language (for replies/summaries).

### Example: Translation Prompt

```python
TRANSLATE_SYSTEM_PROMPT = """
You are a precise translator for a messaging platform.
Your task: translate the text provided in <text> tags into the language specified in <target> tags.
Rules:
- Return ONLY the translated text. No preamble. No explanation. No quotation marks around the output.
- Preserve the original tone (formal, casual, emotional) in the translation.
- If the text is already in the target language, return it unchanged.
- If the meaning cannot be faithfully translated, return the original text unchanged.
"""

def build_translate_user_message(text: str, target_language: str, source_language: str | None) -> str:
    source_hint = f"<source>{source_language}</source>\n" if source_language else ""
    return f"{source_hint}<target>{target_language}</target>\n<text>{text}</text>"
```

### Example: Smart Reply Prompt

```python
SMART_REPLY_SYSTEM_PROMPT = """
You are a messaging assistant generating reply suggestions.
You will receive a conversation history in <conversation> tags.
Your task: generate exactly {count} short, natural reply options.
Rules:
- Return a JSON array of strings only. Example: ["Reply 1", "Reply 2", "Reply 3"]
- No preamble. No numbering. No explanation.
- Each reply must be 1–2 sentences maximum.
- Replies must be contextually appropriate and in the same language as the last message.
- Do not suggest replies that contain personal opinions, political content, or inappropriate material.
"""
```

---

## 5. AI Safety Constraints

These constraints are architectural — they cannot be disabled by configuration or user settings.

| Constraint | Implementation |
|---|---|
| No auto-send | No AI endpoint POSTs to `/messages` or `/sms/send`. Frontend places AI output in compose field only on explicit user action. |
| User review required | All AI features display output in a review panel. `ACCEPT` is a separate user action. |
| No message content in logs | `ai_usage_logs` stores only: feature, model_id, input_tokens, output_tokens, latency_ms, success. Zero message content. |
| No sensitive data in prompts | AI requests send only the minimum context needed. Full conversation histories are summarised to N recent messages before sending. |
| AI-assisted badge | Any message with `is_ai_assisted = true` shows a badge in the compose UI. Badge removed from sent history visible to recipient. |
| Graceful failure | AI failure returns a user-readable error. The compose field and send button remain fully functional. |

---

## 6. AI Usage Logging

```sql
-- ai_usage_logs table
-- Never stores message content
INSERT INTO ai_usage_logs (
    user_id, feature, model_id,
    input_tokens, output_tokens, latency_ms,
    success, error_code
) VALUES (...);
```

Metrics exposed in admin dashboard:
- Feature usage counts (per feature, per day/week/month)
- Average and p95 latency per feature
- Total input/output tokens (for cost monitoring)
- Failure rate per feature

---

## 7. AI Error Handling

| Error Scenario | User Experience | System Behaviour |
|---|---|---|
| Bedrock timeout | "AI assistant is taking longer than expected. You can still type and send manually." | Logged; 502 returned to frontend |
| Bedrock quota exceeded | "AI features are temporarily unavailable." | Logged; 429 returned to frontend |
| Model unavailable in region | Application startup warning; AI features disabled | Admin notified via startup log |
| Prompt returned empty response | "Couldn't generate a suggestion. Try again." | Logged as soft failure |
| Model returns disallowed content | Filtered by Bedrock content moderation | Logged; user sees generic retry message |

---

## 8. Token Budget Guidelines

*Estimates. Verify with selected model. Subject to change when OD-002 is resolved.*

| Feature | Est. Input Tokens | Est. Output Tokens | Notes |
|---|---|---|---|
| Smart Reply (3 suggestions) | 200–500 | 50–100 | Recent 10 messages as context |
| Translation | 50–300 | 50–300 | Scales with message length |
| Rewriting | 100–400 | 100–400 | Scales with message length |
| SMS Optimisation | 100–300 | 50–200 | Short output target |
| Conversation Summary | 500–2000 | 100–300 | Recent 20 messages |
| AI Compose | 50–200 | 100–400 | User prompt + optional context |

Per-user hourly AI request rate limits are configurable to control cost (see NFR-SEC-006).

---

## 9. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

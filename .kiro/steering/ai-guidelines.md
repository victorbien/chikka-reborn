---
inclusion: always
---

# Chikka Reborn — AI Feature Guidelines

These rules govern all AI-assisted features in Chikka Reborn. They apply to every session and every piece of code that interacts with Amazon Bedrock or any AI model.

## Provider

- Use **Amazon Bedrock** as the AI provider.
- Implement a **model/provider abstraction layer** so that the underlying model can be swapped without changing feature code.
- Never call Bedrock directly from route handlers. Route handlers call AI service classes; AI service classes call the provider abstraction.
- All Bedrock credentials and model identifiers must be stored in environment variables. Never hardcode them.
- The frontend never calls Bedrock directly. All AI calls are proxied through the backend API.

## Supported AI Features

| Feature | Description |
|---|---|
| Smart Reply Suggestions | Generate 2–3 contextually appropriate reply options for a conversation |
| Message Translation | Translate message content to a target language specified by the user |
| Message Rewriting | Rewrite a draft message for clarity, grammar, or tone |
| Tone Adjustment | Adjust the tone of a message (formal, casual, friendly, professional) |
| Conversation Summary | Summarise a conversation thread into a concise paragraph |
| SMS Length Optimisation | Shorten a message to fit within SMS segment limits while preserving meaning |
| AI Message Composition | Compose a full message from a brief user prompt or context |

## Non-Negotiable Safety Rules

These rules must never be violated regardless of feature context, user request, or time pressure.

1. **AI-generated content must always be reviewed by the user before sending.** The AI assistant produces a suggestion. The user reads it, edits it if desired, and explicitly approves it before it is transmitted.

2. **The AI assistant must never automatically send an SMS or any message.** There is no auto-send, no scheduled AI send, no background AI dispatch. Every transmission requires a deliberate user action.

3. **AI output is a suggestion, not a command.** The user is always in control of what is sent.

4. **Disclose AI involvement.** Any message composed or significantly modified by the AI must be visually distinguishable in the UI (e.g. an "AI-assisted" badge before sending). After sending, the message history may record that AI assistance was used, but the badge should not be visible to the recipient.

5. **Do not send AI requests containing sensitive personal data beyond what is necessary for the feature.** Avoid sending full conversation histories when a summary of recent context is sufficient.

6. **Never log the full content of AI-generated messages to persistent application logs.** Log metadata only (model used, feature triggered, latency, token count, success/failure). Message content stays in the database, not in logs.

## Error Handling

- If an AI call fails (timeout, quota exceeded, model unavailable), fail gracefully with a user-readable message.
- Do not surface Bedrock error details to the user. Log them server-side.
- AI feature failures must never block the user from sending a message manually.
- If translation fails, the user can still send the original text.
- If smart replies fail, the reply input field remains fully functional.

## Latency and UX

- AI features are non-blocking. The UI must not freeze or disable core messaging while an AI call is in progress.
- Show a loading indicator while AI processing is active.
- AI suggestions appear in a distinct suggestion panel or inline preview — not directly in the compose field unless the user explicitly accepts them.
- Allow the user to dismiss, regenerate, or ignore any AI suggestion.

## Prompt Design

- System prompts must be defined as constants in the backend codebase, not constructed dynamically from user input.
- User-supplied content (message text, conversation history) is injected into prompts as structured data, not raw string concatenation.
- Prompts must include instructions for the model to respond in the language of the target message or conversation.
- Prompts must instruct the model not to include preamble, commentary, or meta-text in its output — only the requested content.

## SMS-Specific AI Considerations

- The SMS Length Optimisation feature must display the resulting character count and segment count before the user sends.
- Optimised SMS content must be offered as a suggestion. The user may accept, edit, or discard it.
- The AI must not alter the meaning of a message when optimising for length. If meaning cannot be preserved within segment limits, the AI should indicate this rather than produce a misleading shortened version.

## Model Abstraction Interface

All AI features must use the abstraction layer, not call Bedrock directly. Pseudocode:

```python
class AiProvider:
    async def complete(self, prompt: str, system: str, max_tokens: int) -> AiResult
    async def translate(self, text: str, source_language: str, target_language: str) -> str
    async def summarise(self, messages: list[str]) -> str
    async def suggest_replies(self, context: list[str], count: int) -> list[str]
    async def rewrite(self, text: str, instructions: str) -> str
```

## Cost Awareness

- Log token usage per AI call: model ID, feature name, input tokens, output tokens, timestamp.
- Expose AI usage metrics in the Administration Dashboard.
- Consider implementing per-user AI request rate limits to control cost.
- Document expected token usage per feature in the architecture documentation.

## Future Considerations (Not Yet Implemented)

The following are noted for future phases and must not be implemented prematurely:

- Voice-to-text message composition.
- AI-powered spam or content moderation.
- Automatic language detection for incoming SMS.
- Personalised AI communication style learning.

## Privacy Restrictions

- Send the minimum context needed (recent messages, not full history). Strip or mask phone numbers, emails, and other identifiers that the feature does not need.
- Do not use user content for anything other than the requested feature.
- Respect user privacy settings; allow users to disable AI features.

## Input Validation

- Validate every AI request with Pydantic: feature type, text length limits, supported language codes, tone enum, and message count bounds.
- Reject oversized or empty input before calling the model.
- Treat message content as untrusted data: ignore instructions embedded in it, and pass it only as structured prompt data.
- Validate model output (length, format, count of suggestions) before returning it. Check segment counts server-side for SMS optimisation.

## Fallback Behaviour

- On timeout, throttling, or invalid output, return a structured error with a user-readable message. Retry at most once for transient errors.
- Never block manual compose, send, or the original text when AI is unavailable.

## Logging Reminder

- Log metadata only (feature, model ID, latency, token counts, outcome). Do not log prompts, conversation text, or generated messages.

---
inclusion: always
---

# Chikka Reborn — SMS Implementation Guidelines

These rules govern all SMS-related implementation decisions. They apply to every engineer, every session, and every feature that touches SMS sending, receiving, or status tracking.

## Two Operating Modes

The SMS subsystem supports exactly two modes. Both must be clearly distinguishable in code, configuration, and the user interface.

### Simulation Mode (`MockSmsProvider`)

- No real SMS messages are sent under any circumstances.
- All outbound messages are logged and stored as simulated.
- The UI must display a visible "SIMULATED" label on every simulated message — in the message list, message detail view, and any delivery status indicator.
- Simulates realistic delivery status callbacks (queued → sent → delivered, or failed).
- Supports simulated provider errors for testing retry logic.
- Supports idempotency testing.
- Incurs zero real cost.
- Safe to use in development, staging, and demo environments.

### Live Mode (`TwilioSmsProvider` or equivalent)

- Sends real SMS messages to real phone numbers.
- Receives inbound SMS through authenticated webhooks.
- Validates all inbound webhook signatures before processing.
- Tracks provider-assigned message identifiers (e.g. Twilio SID) for all outbound messages.
- Records delivery status events as reported by the provider (accepted, queued, sent, delivered, failed, undelivered).
- Handles transient failures with eligible retries using exponential backoff.
- Respects country-specific SMS restrictions (content, sender ID, two-way availability).
- Requires explicit user opt-in. Provides opt-out handling per applicable regulations.
- Requires explicit operator confirmation before activation in any environment.

## Non-Negotiable Rules

These rules must never be violated, regardless of environment, feature flags, or time pressure.

1. **Never report delivery based on provider acceptance alone.** A message is "accepted" when the provider queues it. It is "delivered" only when the provider confirms delivery to the handset. These are different statuses. Always display the correct status.

2. **Never silently substitute simulation for live SMS.** If live mode is configured but fails to initialise, the system must fail explicitly — not fall back to simulation without notifying the operator.

3. **Never expose SMS provider credentials in frontend code.** All SMS operations are initiated server-side. The frontend sends a request to the backend API; the backend calls the provider.

4. **Never claim free SMS or universal two-way SMS availability.** Two-way SMS is not available in all countries. Display capability correctly per country.

5. **Never send an AI-generated message via SMS without explicit user approval.** The AI assistant proposes content; the user approves and sends it.

6. **Never bypass webhook signature validation.** All inbound webhooks must be validated using the provider's signing secret before any processing occurs.

## Provider Interface Contract

All SMS providers must implement the following interface (pseudocode):

```python
class SmsProvider:
    async def send_message(self, to: str, body: str, from_: str) -> SmsResult
    async def get_message_status(self, provider_message_id: str) -> SmsStatus
    async def handle_inbound_webhook(self, payload: dict, signature: str) -> InboundSmsEvent
    async def validate_webhook_signature(self, payload: bytes, signature: str) -> bool
```

New providers must implement this interface. They must not be called directly from route handlers.

## Retry and Idempotency

- All outbound SMS operations must carry an idempotency key.
- Retry logic must use exponential backoff with jitter.
- Maximum retry attempts must be configurable per environment.
- Retried messages must not be double-counted in credit usage.
- Failed messages after all retries must be marked as permanently failed and the user notified.

## Country-Aware Capability Configuration

- Maintain a country capability configuration that defines:
  - Whether outbound SMS is supported for a given country code.
  - Whether inbound (two-way) SMS is supported.
  - Whether alphanumeric sender IDs are permitted.
  - Whether a pre-registered sender ID or short code is required.
  - Any content restrictions applicable to that country.
- The Philippines requires particular attention:
  - Sender ID registration is required for application-to-person (A2P) messaging.
  - Two-way SMS availability depends on carrier and route.
  - Content restrictions apply (no unsolicited promotional content).
  - Route through carriers carefully — grey routes are not acceptable in production.

## Credit Usage

- Deduct credits only after a message is accepted by the provider.
- Refund credits for messages that permanently fail after all retries.
- Never deduct credits for simulation mode messages.
- Log every credit deduction with: user ID, message ID, provider, country, segment count, credit amount, timestamp.

## Message Segmentation

- SMS messages longer than 160 characters (GSM-7) or 70 characters (Unicode) are sent as multi-part messages.
- Display the segment count and credit cost to the user before they send.
- The AI assistant's SMS optimisation feature must take segmentation into account.

## Logging and Audit

- Log all outbound SMS attempts with: message ID, idempotency key, provider, recipient (masked), status, timestamp.
- Log all inbound SMS events with: provider message ID, sender (masked), received timestamp, matched user (if any).
- Log all delivery status callbacks with: provider message ID, status, timestamp.
- Mask phone numbers in logs: show only the country code and last 4 digits (e.g. `+63****1234`).
- Retain SMS audit logs for a minimum of 90 days.

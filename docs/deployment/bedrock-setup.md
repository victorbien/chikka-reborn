# Amazon Bedrock Setup

**Project:** Chikka Reborn
**Status:** Prepared. The Bedrock adapter is tested against fakes only; it has not called a real model.
**Last Revised:** November 2026

The first deployment can run `AI_PROVIDER_MODE=mock` (canned drafts, no external call). Switch to `bedrock` only after the steps below. The server then refuses to start unless `BEDROCK_REGION`, `BEDROCK_MODEL_ID` and `BEDROCK_API_KEY` are all set, and never falls back to the mock.

## 1. Access requirements

| Requirement | Detail |
|---|---|
| AWS account | Owned by the organisation, with billing alerts and a budget set before enabling |
| Region | One region where your chosen model is offered. Set `BEDROCK_REGION` to it (for example the region code shown in the Bedrock console). The adapter calls `https://bedrock-runtime.<region>.amazonaws.com/model/<model id>/converse` |
| Model access | Open the model in the Bedrock console model catalogue and confirm you can invoke it in that region. Many models are available by default; some need a one-time use-case form or Marketplace subscription, which an administrator with the right permissions must accept |
| Model ID | Set `BEDROCK_MODEL_ID` to the exact model ID or **inference profile** ID shown in the console. Some models can only be called through an inference profile in a region; use that ID if the plain model ID is rejected |
| Data handling | Read the provider's data-handling terms for the chosen model before sending user text. The platform sends only recent, masked context (see section 5), but the user's own draft is sent as written |

## 2. Credentials and IAM permissions

The adapter authenticates with a **Bedrock API key** sent as a bearer token (`BEDROCK_API_KEY`). Per AWS, a long-term key is backed by an IAM user, and AWS recommends long-term keys only for exploration; short-term keys last at most 12 hours. This has two consequences for production:

- Create a **dedicated IAM user** for the key, not a person's account, and attach a policy limited to invoking the one model:

  ```json
  {
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": [
        "arn:aws:bedrock:<region>::foundation-model/<model id>",
        "arn:aws:bedrock:<region>:<account id>:inference-profile/<profile id>"
      ]
    }]
  }
  ```

  `Converse` requires `bedrock:InvokeModel`. The app does not stream, so `InvokeModelWithResponseStream` is not needed. Remove the inference-profile line if you use a plain model ID. Add no other permission, and no `bedrock:*`, console, IAM or data-plane access.
- Set an **expiry** on the key and put a calendar reminder to rotate it. Rotation means: generate a new key, update the secret, restart, delete the old key. The adapter does not refresh keys by itself. If AWS key lifetimes become a problem, an SDK or role-based credential adapter would need to be added behind `AiProvider` (this needs an ADR for the new dependency).

Store the key only in the backend secret store. Never in Vercel, the repository or logs.

## 3. Usage limits and cost control

| Control | Where | Default |
|---|---|---|
| Per-user hourly requests | `system_settings.ai_user_limit_per_hour` | 30 |
| Platform kill switch | `system_settings.ai_enabled` | on |
| User opt-in | Each user must enable the assistant (recorded, off by default), and can disable it per conversation | off |
| Output tokens | `AI_MAX_OUTPUT_TOKENS` | 600 |
| Timeout | `AI_TIMEOUT_SECONDS` | 15 s, one retry for transient failures |
| Input size | Text up to 1,600 characters, context up to 20 messages (summary 50), 6,000 characters total | fixed in `modules/ai/settings.py` |
| AWS side | AWS Budgets alert and a Bedrock service quota review | set by the operator |

Usage is logged as metadata only: feature, model ID, token counts, latency and outcome in `ai_assistance_logs`. The admin dashboard shows it (`GET /api/v1/admin/ai/metrics`). Set `AI_COST_PER_1K_INPUT_USD` and `AI_COST_PER_1K_OUTPUT_USD` from the model's price page to get a cost estimate there; unset means no figure is shown.

## 4. Error handling

| Bedrock result | Platform behaviour |
|---|---|
| 429 (throttled) | One retry, then `502 ai_unavailable` with a generic message. The compose box keeps working |
| Timeout / 5xx / network | Same |
| 401 / 403 (bad key, no model access, wrong region) | Not retried. Logged as `configuration`. The user sees the same generic message. Operators see `bedrock error` with the status code in logs |
| Guardrail or content filter stop | "The assistant can't help with this message" and nothing is shown |
| Malformed or out-of-bounds output | "Couldn't generate a suggestion", nothing partial is shown |

Failures never block sending a message by hand. Bedrock error text is never returned to users and prompts and generated text are never logged.

## 5. Safety properties to keep

- AI output is only a draft. Nothing is sent without a deliberate user action, and AI-assisted drafts are labelled before sending.
- System prompts are constants. User text is passed as JSON data, and the prompts tell the model to ignore instructions inside it. This reduces prompt injection; it does not eliminate it, which is why output is parsed, bounded and never acted on automatically.
- Context is limited and masked (emails and long numbers become `[email]`, `[number]`).

## 6. Verification before enabling

1. In the console playground, invoke the exact `BEDROCK_MODEL_ID` in `BEDROCK_REGION` with the IAM user's key to prove access and region.
2. Staging with `AI_PROVIDER_MODE=bedrock`: the log shows `preflight ok` with no AI warning, `GET /api/v1/ai/status` reports `simulated: false` and the model ID.
3. A test user enables the assistant, requests a translation and a smart reply. Confirm the result is labelled as a suggestion, token counts appear in the admin metrics, and no prompt or draft text appears in the logs.
4. Revoke the key in IAM and repeat: the request fails with the generic message, and sending a message still works.
5. Confirm the AWS bill or Budgets console shows the test usage.

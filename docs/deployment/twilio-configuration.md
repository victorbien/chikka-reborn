# Twilio Configuration

**Project:** Chikka Reborn
**Status:** Prepared. Live SMS is **off** and has never been run against a real Twilio account.
**Last Revised:** November 2026

This document is the configuration reference. The ordered activation checklist and the roll-back are in [sms-live-activation.md](sms-live-activation.md). Where the two overlap, that checklist wins.

## 0. Do not enable live SMS until all of this is true

- [ ] A named person has approved real SMS to real numbers and the cost, in writing (date and name recorded)
- [ ] Twilio credentials are in the hosting secret store (not in the repository, Vercel or logs)
- [ ] A sender is bought or registered **for each destination country** and its status is confirmed
- [ ] Recipient consent handling is in place: users must confirm they have permission before each new recipient, and STOP replies are honoured (both are implemented; the operator confirms the wording is acceptable)
- [ ] Country and provider requirements for each enabled destination are confirmed with Twilio and recorded as verification evidence
- [ ] Terms and Privacy Notice are published (audit SEC-009), because SMS involves other people's phone numbers
- [ ] Staging has completed the test procedure in section 7

If any box is open, keep `SMS_PROVIDER_MODE=mock` and `SMS_LIVE_CONFIRMED=false`. The backend refuses to start in live mode without confirmation, credentials and `SMS_PUBLIC_BASE_URL`, and never falls back to simulation silently.

## 1. Twilio account

1. Create or use a Twilio account owned by the organisation, not a person's trial login. Trial accounts can only message verified numbers and prepend a trial notice.
2. Fund it. Set a **usage trigger / budget alert** so unexpected volume is noticed.
3. Messaging -> **Geo permissions**: enable only the destination countries you will serve. Everything else stays off; this is a hard backstop behind the platform's own country table.
4. Create a **separate subaccount per environment** (staging, production). Use the subaccount's SID and Auth Token, so a leak in staging cannot spend production funds.
5. Store `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` only in the backend secret store. The Auth Token is also the webhook signing secret. Rotate it in the console if it is ever exposed, then update the secret and restart.

## 2. Sender configuration

The platform sends from numbers listed in the active provider configuration (`provider_configurations.sender_numbers`, E.164) and, where a country allows it, a registered alphanumeric sender ID stored in that country's capability row (`provider_settings.sender_id`).

| Need | Action |
|---|---|
| Two-way (replies reach the app) | Buy an SMS-capable number in Twilio that supports the destination route. Add it to the provider's sender numbers (SMS administration, or `PATCH /api/v1/admin/sms/providers/{id}`). Replies are routed by (platform number, remote number), so keep enough numbers for the number of concurrent conversations: with too few, new recipients get `sender_capacity` |
| One-way alphanumeric sender ID | Register it with Twilio for the country. Record it in that country's capability version. Alphanumeric senders cannot receive replies, and the platform shows "replies unsupported" |
| Registration status | Set `registered_sender_status` per country only after Twilio or the carrier confirms it |

Never put a sender number or SID in the frontend or the repository.

## 3. Webhook URLs

Set `SMS_PUBLIC_BASE_URL=https://<api domain>` (origin only, no path, no trailing slash). It must be exactly what Twilio calls, because Twilio signs the complete URL and the backend rebuilds that URL from this setting, not from request headers.

| Purpose | URL | Configure in |
|---|---|---|
| Inbound SMS (A message comes in) | `https://<api domain>/api/v1/webhooks/twilio/inbound`, method POST | Twilio console -> Phone Numbers -> the number -> Messaging configuration, for **each sender number** |
| Delivery callbacks | `https://<api domain>/api/v1/webhooks/twilio/status?sms_id=<delivery id>` | Nothing to configure. The backend sends a `StatusCallback` with every message |
| Fallback URL | leave empty | A fallback URL would receive unsigned-looking duplicates |

If a proxy or CDN rewrites the host, scheme or path, every signature check fails. The URL the app is reached at must be the URL in `SMS_PUBLIC_BASE_URL`.

## 4. Signature validation

Implemented in `integrations/sms/twilio.py` and `modules/sms/webhooks.py`:

- Twilio sends `X-Twilio-Signature`: base64 HMAC-SHA1, keyed with the Auth Token, over the full URL followed by every POST parameter sorted by name.
- The backend checks it on the raw request bytes before parsing or storing anything, with a constant-time comparison. A missing or wrong signature returns 403 `invalid_signature` and is audited as `sms.webhook_rejected`.
- If validation cannot run (for example a missing secret) it fails closed with 503, never open.
- There is no development bypass. Simulation uses its own signer (`x-mock-signature`) and its own route.
- Events are de-duplicated by provider message ID (`MessageSid`, and `sid:status` for callbacks). Twilio webhooks carry no timestamp, so there is no time-window replay protection beyond that.
- Bodies over 64 KB are refused.

Known gap (audit SEC-005): the per-IP webhook rate limit runs before the signature check. Do not rely on it as protection, and make sure `FORWARDED_ALLOW_IPS` is correct so one client cannot exhaust the shared budget.

## 5. Country-specific requirements

The platform ships a country table (`sms_country_capabilities`) that is **deliberately conservative**: a destination is unsupported until an administrator publishes a version marked supported **with verification evidence**.

Per country you intend to enable, confirm with Twilio (the Messaging country guidelines and the regulatory/sender-registration pages for that country) and record in the capability version:

- outbound SMS allowed, and from which sender types
- whether an alphanumeric sender ID is allowed, and whether it must be pre-registered
- whether two-way is available on the route
- content restrictions and opt-out rules
- price per segment (`credit_cost_per_segment` is set by hand; the provider price lookup is informational only)

### Philippines (seeded as `UNVERIFIED`)

- A2P sender registration is required before sending. Until `registered_sender_status` is confirmed, the platform blocks sends.
- Two-way support depends on the carrier and route. Keep `inbound_support = requires_verification` until a real reply has been received on that route.
- No unsolicited promotional content. No grey routes: use only routes Twilio documents for the country.
- Opt-out keywords are the English set today. Filipino equivalents must be reviewed by native speakers before a Philippine launch.
- Requirements change. Re-check Twilio's current Philippines guidance on the day you enable it, and keep the evidence (link, date, who checked) in the capability version's notes.

This document makes no statement that any country's requirements are met. That is the operator's confirmation.

## 6. Consent and opt-out in the product

- Before the first message to a recipient the sender must confirm they have permission (recorded per sender and recipient with the notice version, `SMS_ATTESTATION_VERSION`). A recipient replying is not consent.
- `STOP` and equivalents are recorded per number immediately and block all later sends from every user. `START` lifts it.
- Twilio may also answer STOP itself and block later sends (error 21610). Both are recorded.

## 7. Test procedure

Stage 1: no Twilio account needed (always run first)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/flows/test_sms.py tests/flows/test_sms_live.py -q
```

These exercise send, callbacks, inbound, signatures, opt-out and country gating against an in-process fake that uses Twilio's real signature algorithm.

Stage 2: Twilio **test credentials** (no delivery, no charge)

```powershell
$env:TWILIO_TEST_ACCOUNT_SID = "<test sid>"; $env:TWILIO_TEST_AUTH_TOKEN = "<test token>"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_twilio_test_credentials.py -q
```

Skipped when the variables are absent. It does not prove delivery or inbound.

Stage 3: staging, live, **one approved recipient you control**

1. Set the staging secrets and `SMS_PROVIDER_MODE=live`, `SMS_LIVE_CONFIRMED=true`, `SMS_PUBLIC_BASE_URL`. Confirm the container log shows `preflight ok` and the live-SMS warning, and that `GET /api/v1/sms/status` as a user reports mode `live`.
2. In SMS administration publish one country version (the recipient's), set sender numbers, then **Activate** the live provider (you type the environment name).
3. Use two accounts: a verified sender and the approved phone number as recipient, with consent confirmed.
4. Send one message. Expect, in order: `queued`, `accepted` (labelled "Accepted by provider", not delivered), `sent`, then `delivered` only after a **signed** callback. Check the audit rows and Twilio's message log show the same SID.
5. Reply from the phone: it appears in the same conversation. Send `STOP`: the next send is refused with the opt-out message. Send `START`.
6. Send an unsigned `curl -X POST https://<api>/api/v1/webhooks/twilio/inbound -d "From=%2B15550000000"`: expect 403.
7. Watch SMS administration -> delivery health for a day (rejected signatures, failed callbacks, unrouted replies).

Stage 4: production repeats stage 3 with the production subaccount, a fresh approval and a pause switch ready (SMS administration -> Pause all sending). Roll-back: [rollback-procedure.md](rollback-procedure.md) section 4.

None of these live stages has been run.

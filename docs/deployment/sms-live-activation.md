# Live SMS Activation

**Project:** Chikka Reborn  
**Status:** Checklist. Live sending is implemented and tested against a fake Twilio, and has **not** been run against a real account.  
**Last Revised:** November 2026  

---

## What is done and what is not

Done in code and covered by automated tests (no network, Twilio replaced by an in-process fake that uses Twilio's real signature algorithm): Twilio send, provider message ID storage, status callbacks, inbound webhook, signature verification, error classification and retries, consent, opt-out, country gating, rate limits, administration and the live-mode UI labelling.

Not verified, because it needs things only a human can supply: a real Twilio account, funding, geo permissions, sender numbers and (for the Philippines) sender registration. Nothing in this repository sends a real SMS to a real number unless every step below is completed by an operator.

## Activation checklist

Work through these in order, in the target environment. Do not skip a step because simulation works.

1. **Human approval.** Real SMS to real numbers, and any cost, need explicit approval (development principles). Record who approved and when.
2. **Twilio account.** Funded; messaging enabled; the destination countries enabled under *Messaging -> Geo permissions*.
3. **Sender.** Buy or register at least one SMS-capable number per environment. For the Philippines, A2P sender registration must be approved by the carrier or provider first. Two-way depends on the route; confirm it with Twilio, do not assume it.
4. **Secrets.** Put `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` in the hosting secret store. Never in the repository, the frontend or logs.
5. **Environment variables.** `SMS_PROVIDER_MODE=live`, `SMS_LIVE_CONFIRMED=true` (set by an operator for this environment only), `SMS_PUBLIC_BASE_URL=https://<public backend origin>` (exactly what Twilio will call; HTTPS), and a real `APP_SECRET_KEY`. The server refuses to start if any is missing. It never starts in simulation instead.
6. **Twilio console webhook.** On the sender number, set *A message comes in* to `POST https://<origin>/api/v1/webhooks/twilio/inbound`. Delivery callbacks need no console setting: each message carries its own `StatusCallback` URL.
7. **Database configuration (as an administrator, in SMS administration or the API).**
   - Set the provider's *sender numbers* (E.164) and *sender registration status*.
   - For each country you will serve, publish a capability version with `outbound_support = supported` **only with verification evidence** (the database requires it), `price_units_per_segment` set, `registered_sender_status = registered` where registration is required, and the real `inbound_support` (use `requires_verification` until two-way is proven).
   - Confirm and activate the live provider: `POST /admin/sms/providers/{id}/activate` with the environment name. This records who confirmed live and for which environment.
8. **Review the failure tables.** Check `backend/app/integrations/sms/errors.py` (Twilio error code -> class) against Twilio's current error catalogue. Unknown codes are treated as permanent, which is safe but may need tuning.
9. **Test with Twilio test credentials (no delivery, no charge).** Set `TWILIO_TEST_ACCOUNT_SID` and `TWILIO_TEST_AUTH_TOKEN` and run `pytest tests/integration/test_twilio_test_credentials.py`. Without both variables the tests are skipped.
10. **First real message.** Send one message from a test account to a phone you control, approved in step 1. Confirm in order: `queued`, `accepted` (the UI says "Accepted by provider", not delivered), `sent`, `delivered` from a signed callback. Reply from the phone and confirm it arrives in the same conversation. Send `STOP` from the phone and confirm further sends are refused, then `START`.
11. **Watch.** Use SMS administration -> delivery health during the first day: rejected signatures, failed callbacks, unrouted replies, failure rate.

## Roll back

Set `SMS_PROVIDER_MODE=mock` and `SMS_LIVE_CONFIRMED=false` and restart. Messages still queued for the live provider are held (never sent through the simulation) and expire to `failed` after `SMS_QUEUE_MAX_AGE_SECONDS`. To stop sending without a restart, use *Pause all sending* in SMS administration.

## Facts to verify with Twilio before launch

These are assumptions taken from public documentation and must be confirmed against the actual account:

- No documented idempotency key exists on message creation, so duplicate prevention is ours. A request that times out is treated as an unknown outcome and **not** resent; it fails after `SMS_AMBIGUOUS_WINDOW_SECONDS` unless a callback proves what happened.
- Status callbacks can arrive out of order and more than once. Handled by rank and de-duplication on (message ID, status); not yet observed against real traffic.
- Whether Twilio itself answers `STOP` and blocks later sends (error 21610). The platform records an opt-out in both cases, but the confirmation text sent to the recipient is Twilio's.
- Inbound webhooks carry no timestamp, so replay protection is de-duplication on the message ID, not a time window.
- Pricing: `credit_cost_per_segment` is configured by hand per country. The provider pricing lookup (`get_country_capabilities`) is informational and never enables a route.

## Known limitations

- The worker and the real-time hub run inside each backend process. One instance is fine; several instances share work safely (rows are leased) but real-time pushes only reach clients connected to the same instance until cross-instance fan-out exists.
- Simulated callbacks are scheduled in memory. A restart drops callbacks not yet delivered; the polling reconciliation then settles such messages from the simulation's own status lookup.
- Credits: this phase shows an estimated cost and records nothing in the ledger. Deduction after provider acceptance, and refunds on permanent failure, are Phase 4 (module H). Nothing is charged today, in either mode.
- Live OTP delivery for phone verification still uses the unavailable-live placeholder; verifying a number for live mode needs that wiring.
- Opt-out keywords are the English set from the requirements. Filipino equivalents need review by native speakers before a Philippine launch.
- Inbound MMS is not supported: the text is kept and a note is shown.
# Risk Register

**Document:** CHKR-PM-003  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Living Document  
**Last Revised:** November 2026  

---

## Purpose

The authoritative risk register for Chikka Reborn. Documents all identified risks with their likelihood, impact, mitigation strategies, and current status. Supersedes the risk section in `docs/risks-and-dependencies.md` (legacy) with this canonical, ID-based register.

## Scope

All phases. All risk categories.

---

## Risk Rating Matrix

| Likelihood \ Impact | Low | Medium | High |
|---|---|---|---|
| **High** | 🟡 Medium | 🟠 High | 🔴 Critical |
| **Medium** | 🟢 Low | 🟡 Medium | 🟠 High |
| **Low** | 🟢 Low | 🟢 Low | 🟡 Medium |

---

## Active Risks

### RISK-001 — Philippine SMS Two-Way Availability
**Category:** Product / Technical  
**Likelihood:** High | **Impact:** High | **Level:** 🔴 Critical  
**Phase:** 2  

**Description:** Two-way (inbound) SMS in the Philippines requires carrier agreements, registered sender IDs, and specific virtual number types. This may not be achievable quickly or cost-effectively. If unavailable, the core product use case (Lolo Ben replying to Marites) cannot be demonstrated.

**Impact if realised:** SMS-to-Internet messaging unavailable for PH at Phase 2 launch. Core product differentiation reduced.

**Mitigation:**
- Document outbound-only as the Phase 2 launch baseline for PH.
- Display inbound capability status accurately in the UI — never claim it is available if it is not.
- Engage Twilio PH routing team early (begin Phase 1).
- Initiate sender ID registration immediately (DEP-008).

**Owner:** Operations  
**Status:** ⬜ Open — action required Phase 1  
**Review Date:** Phase 2 start

---

### RISK-002 — Supabase Realtime Concurrency Ceiling
**Category:** Architecture  
**Likelihood:** Medium | **Impact:** Medium | **Level:** 🟡 Medium  
**Phase:** 1–2  

**Description:** Supabase Realtime has documented connection limits per plan tier. Hitting these limits during Phase 1–2 growth would degrade real-time messaging.

**Mitigation:**
- Monitor connection counts from Phase 1 launch.
- Architecture pre-designs the custom WS/Redis migration path (ADL-008).
- Upgrade Supabase plan at 70% of connection limit.
- Trigger custom WS evaluation if limits are projected to be reached within 3 months.

**Owner:** Engineering  
**Status:** ⬜ Open — monitoring required Phase 1  
**Review Date:** Phase 2 planning

---

### RISK-003 — Amazon Bedrock Regional Availability
**Category:** AI / Infrastructure  
**Likelihood:** Medium | **Impact:** High | **Level:** 🟠 High  
**Phase:** 3  

**Description:** Bedrock is not available in all AWS regions. If the backend hosting region doesn't support the required model, AI features cannot function.

**Mitigation:**
- Confirm Bedrock model availability in target region before Phase 3 begins (DEP-006, DEP-007).
- AI provider abstraction allows swapping to a different model or provider without changing feature code.

**Owner:** Engineering / DevOps  
**Status:** ⬜ Open — resolve before Phase 3  
**Review Date:** Phase 2 end

---

### RISK-004 — Philippine A2P Sender Registration Delay
**Category:** Compliance / Operations  
**Likelihood:** High | **Impact:** High | **Level:** 🔴 Critical  
**Phase:** 6  

**Description:** Philippine carrier A2P SMS registration requires business documentation submission and approval, which can take weeks to months.

**Mitigation:**
- Begin registration immediately (do not wait for Phase 6).
- Grey routes are never used in production.
- Simulation mode is always available while registration is pending.

**Owner:** Operations  
**Status:** ⬜ Open — begin Phase 1 parallel track  
**Review Date:** Monthly until resolved

---

### RISK-005 — Credit Ledger Race Condition
**Category:** Architecture / Data Integrity  
**Likelihood:** Medium | **Impact:** High | **Level:** 🟠 High  
**Phase:** 2  

**Description:** Concurrent SMS sends from the same user could cause a race condition in credit deduction, resulting in a negative balance.

**Mitigation:**
- Use `SELECT FOR UPDATE` on `credit_accounts` within credit deduction transaction.
- Database `CHECK (balance >= 0)` constraint as final guard.
- Concurrency integration test required (UT-CRED-002, AC-4-004).

**Owner:** Engineering  
**Status:** ⬜ Open — address in Phase 2 credit service implementation

---

### RISK-006 — Webhook Replay Attack
**Category:** Security  
**Likelihood:** Medium | **Impact:** Medium | **Level:** 🟡 Medium  
**Phase:** 2  

**Description:** SMS providers may send duplicate webhook events. Processing twice could cause double refunds or incorrect status.

**Mitigation:**
- Unique constraint on `(provider_message_id, provider_status)` in `sms_delivery_events`.
- Idempotency check before any webhook processing.
- Test: UT-RECV-005.

**Owner:** Engineering  
**Status:** ⬜ Open — address in Phase 2 webhook implementation

---

### RISK-007 — AI Prompt Injection via User Content
**Category:** Security / AI  
**Likelihood:** Medium | **Impact:** Medium | **Level:** 🟡 Medium  
**Phase:** 3  

**Description:** User-provided message content could manipulate AI model outputs in unexpected ways.

**Mitigation:**
- Inject user content as structured XML-tagged data, not raw string concatenation.
- Static system prompts define model role and prohibit instruction overriding.
- All AI output reviewed by user before sending — user is the last line of defence.
- Test: UT-AI-007 (prompt injection).

**Owner:** Engineering  
**Status:** ⬜ Open — address in Phase 3 prompt design

---

### RISK-008 — Phone Number Recycling (Inbound SMS Routing)
**Category:** Product / Privacy  
**Likelihood:** Low | **Impact:** High | **Level:** 🟡 Medium  
**Phase:** 2  

**Description:** Mobile carriers recycle phone numbers. A recycled number previously linked to one Chikka user could route inbound SMS to the wrong account.

**Mitigation:**
- Unlink phone numbers when accounts are deleted.
- Do not route inbound SMS to deleted/inactive accounts.
- Consider periodic re-verification prompt after long inactivity.
- Document limitation in Privacy Policy.

**Owner:** Engineering / Product  
**Status:** ⬜ Open — address in Phase 2 inbound SMS design

---

### RISK-009 — Data Breach
**Category:** Security  
**Likelihood:** Low | **Impact:** High | **Level:** 🟡 Medium  
**Phase:** All  

**Description:** A breach of the production database would expose user profiles, phone numbers, message content, and credit history.

**Mitigation:**
- RLS on all tables.
- Service role key never in frontend.
- Phone numbers masked in logs.
- Secrets rotation policy.
- OWASP review Phase 6.
- Penetration test before production launch.

**Owner:** Engineering / Operations  
**Status:** ⬜ Open — ongoing; full review Phase 6

---

### RISK-010 — Open Decision Delays (OD-001 through OD-008)
**Category:** Project Management  
**Likelihood:** Medium | **Impact:** Medium | **Level:** 🟡 Medium  
**Phase:** All  

**Description:** Eight open decisions have not yet been resolved. Delays in resolving them could block phase starts.

**Mitigation:**
- Three decisions are immediately blocking (OD-003, OD-008, OD-006) — resolve this week.
- Remaining decisions have defined resolution deadlines in `docs/project-management/decision-log.md`.

**Owner:** Product / DevOps  
**Status:** ⬜ Open — escalate immediately

---

## Closed Risks

None yet. Risks move to this section when their trigger condition no longer exists or the mitigation has been fully implemented.

---

## Risk Review Schedule

| Frequency | Activity |
|---|---|
| Each phase start | Review all open risks; add new ones identified during planning |
| Each phase end | Update status; close resolved risks |
| Monthly | Review RISK-004 (PH sender registration) status |
| Phase 6 | Full risk review before production launch |

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft — 10 active risks |

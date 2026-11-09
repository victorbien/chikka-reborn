# Disaster Recovery

**Document:** CHKR-DEPLOY-005  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Defines the disaster recovery plan for Chikka Reborn — what constitutes a disaster, recovery objectives, recovery procedures for each failure scenario, and the annual DR drill process.

## Scope

Production environment. Phase 6 and onwards.

---

## 1. Recovery Objectives

| Metric | Target | Notes |
|---|---|---|
| **RTO** (Recovery Time Objective) | 2 hours | Maximum acceptable downtime before service restored |
| **RPO** (Recovery Point Objective) | 1 hour | Maximum acceptable data loss (time since last restore point) |
| **MTTR** (Mean Time to Recovery) | Target < 1 hour | Average across all incident types |

---

## 2. Failure Scenarios and Recovery Procedures

### Scenario 1 — Frontend Outage (Vercel)

**Symptoms:** Application inaccessible. Vercel status shows an incident.  
**RTO:** 15 minutes  
**Recovery:**

```
1. Check Vercel status: https://www.vercel-status.com
2. If Vercel incident: wait for Vercel resolution (no action needed)
3. If our deployment caused the issue:
   a. Vercel dashboard → Deployments → select previous working deploy
   b. Click "Promote to Production"
4. Verify: GET https://chikka-reborn.app → returns app shell
```

**Prevention:** Vercel maintains global CDN redundancy. Frontend outages caused by Vercel itself are outside our control.

---

### Scenario 2 — Backend Outage (Hosting Platform)

**Symptoms:** API returns 502/503. `/health` check fails.  
**RTO:** 30 minutes  
**Recovery:**

```
1. Check hosting platform status page (Render/Railway/Fly.io)
2. Check /health endpoint for specific failure:
   - database: error → see Scenario 3
   - sms_provider unreachable → SMS features degraded; messaging continues
3. If platform incident: wait or trigger a new deploy to healthy instance
4. If application crash:
   a. Check application logs for ERROR/CRITICAL
   b. Fix the cause (if code bug: hotfix PR → merge → auto-deploy)
   c. If urgent: roll back to previous Docker image tag
5. Verify: GET /health → {"status":"healthy"}
```

---

### Scenario 3 — Database Failure (Supabase)

**Symptoms:** API returns 500 errors. Logs show DB connection errors.  
**RTO:** 1 hour  
**RPO:** 1 hour (PITR granularity on Supabase Pro)  
**Recovery:**

```
1. Check Supabase status: https://status.supabase.com
2. If Supabase incident: wait for Supabase resolution
3. If data corruption from a bad migration:
   a. Identify the last known good point in time
   b. In Supabase dashboard → Database → Backups → Point-in-Time Recovery
   c. Restore to identified point
   d. WARNING: data written after restore point is lost
   e. Notify users if data loss occurred
4. Verify application health after restore
5. Re-apply any safe migrations if needed
```

**PITR availability:** Supabase Pro plan required. Confirm this is enabled before production launch (AC-6-008).

---

### Scenario 4 — Bad Database Migration

**Symptoms:** Application behaves unexpectedly after a migration. Constraint violations in logs.  
**RTO:** 1 hour  
**Recovery:**

```
1. Immediately:
   a. Assess whether the migration is reversible (additive) or destructive
   b. If additive (new column, new table): create a forward-fix migration
   c. If destructive (dropped column, data loss): use PITR restore

2. For forward fix:
   a. Write and test rollback migration in development
   b. Apply to staging: verify fix
   c. Apply to production
   d. Document in migration history

3. For PITR restore: follow Scenario 3 procedure
```

---

### Scenario 5 — SMS Provider (Twilio) Outage

**Symptoms:** Outbound SMS fails. Delivery status callbacks stop. Inbound webhooks stop arriving.  
**Impact:** SMS features down; Chikka-to-Chikka messaging continues.  
**RTO:** N/A (depends on Twilio resolution)  
**Recovery:**

```
1. Check Twilio status: https://status.twilio.com
2. If Twilio outage:
   a. Notify users via in-app banner: "SMS delivery is delayed due to a provider issue."
   b. Queue outbound SMS with retry (existing retry mechanism handles this)
   c. Monitor Twilio status; retries will resume automatically when provider recovers
3. If persistent outage (> 4 hours):
   a. Evaluate switching to an alternative SMS provider
   b. This requires implementing a new SmsProvider adapter (see architecture docs)
   c. Decision requires engineering lead approval
```

**SMS simulation mode** is always available as a fallback for testing. It is never used silently as a substitute for live mode.

---

### Scenario 6 — AI Provider (Amazon Bedrock) Outage

**Symptoms:** All AI features return errors. Logs show Bedrock connectivity failures.  
**Impact:** AI features down; all messaging features continue normally.  
**RTO:** N/A (depends on AWS resolution)  
**Recovery:**

```
1. Check AWS status: https://health.aws.amazon.com
2. If Bedrock outage:
   a. AI features degrade gracefully (non-blocking — per NFR-AVAIL-002)
   b. No user action needed for messaging
   c. Show user-facing message: "AI features are temporarily unavailable."
3. Monitor AWS health; AI features resume automatically when Bedrock recovers
4. Log AI failures during outage for support reference
```

---

### Scenario 7 — Security Breach

**Symptoms:** Unauthorised access detected. Unusual data access patterns. External report of breach.  
**RTO:** Immediate containment; recovery timeline depends on scope  
**Response:**

```
IMMEDIATE (within 1 hour):
1. Rotate all compromised secrets immediately
   a. Supabase service role key
   b. Twilio auth token
   c. AWS access keys
2. Invalidate all user sessions (Supabase Auth → revoke all tokens)
3. If data exfiltrated: contact legal counsel immediately
4. Document everything from this point forward

INVESTIGATION:
5. Review application logs for unauthorised access patterns
6. Review Supabase audit logs
7. Identify attack vector

REMEDIATION:
8. Fix vulnerability
9. Deploy fix
10. Restore from backup if data was corrupted

NOTIFICATION:
11. Notify affected users per Privacy Policy requirements
12. Notify relevant data protection authority if required (GDPR, NPC Philippines)
```

---

## 3. Backup Verification

Backups must be verified before they are needed. Schedule:

| Activity | Frequency | Owner |
|---|---|---|
| Confirm PITR is enabled | Monthly | DevOps |
| Test restore from backup on staging | Quarterly | DevOps |
| Verify backup retention period | Monthly | DevOps |
| DR drill (simulate Scenario 3) | Annually (Phase 6+) | Engineering lead |

---

## 4. Incident Communication

### Internal

- Immediately notify the engineering channel with: symptom, estimated impact, first response actions.
- Update every 30 minutes during active incident.

### External (to users)

- Use an in-app banner for service-impacting issues.
- Use a status page (TBD — tool not yet selected) for production incidents.
- For data loss incidents: direct notification to affected users required.

---

## 5. Post-Incident Review

After every production incident with user impact:

1. Timeline of events (what happened, when, who responded).
2. Root cause analysis.
3. Impact assessment (users affected, data affected, duration).
4. What worked well.
5. Action items to prevent recurrence (with owner and due date).
6. Document in `docs/project-management/decision-log.md` if architectural changes result.

---

## 6. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

# Performance Test Plan

**Document:** CHKR-QA-005  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Defines the performance and load testing approach, test scenarios, tools, targets, and Phase 6 execution plan for Chikka Reborn.

## Scope

Phase 6 production hardening. Preliminary performance measurements from Phase 1 onwards.

---

## 1. Performance Targets (from NFRS)

| Metric | Target | Source |
|---|---|---|
| Chikka-to-Chikka message latency | < 500ms end-to-end (p95) | NFR-PERF-001 |
| REST API response time | < 300ms (p95, excluding SMS + AI) | NFR-PERF-002 |
| AI feature response time | < 5s (p95) | NFR-PERF-003 |
| Frontend Lighthouse score | ≥ 85 (mobile + desktop) | NFR-PERF-004 |
| SMS send throughput | 100 initiations/minute/env | NFR-PERF-005 |
| Concurrent WebSocket connections (Phase 1) | 1,000 | NFR-SCALE-002 |
| Production uptime | 99.5% monthly | NFR-AVAIL-001 |

---

## 2. Performance Test Types

| Type | When | Tool | Purpose |
|---|---|---|---|
| Baseline benchmarks | Phase 1 launch | pytest-benchmark + Playwright | Establish baseline for key endpoints |
| Load test | Phase 6 | k6 or Locust | Validate system at 1,000 concurrent users |
| Stress test | Phase 6 | k6 | Find the system's breaking point |
| WebSocket concurrency test | Phase 2 (Supabase Realtime check) | k6 WebSocket | Verify Realtime handles expected connections |
| Frontend performance audit | Phase 1, Phase 5 | Lighthouse CI | Verify Lighthouse score ≥ 85 |
| Database query benchmarks | Phase 1 | EXPLAIN ANALYZE | Verify no N+1 queries, index usage |

---

## 3. Load Test Scenarios (Phase 6)

### Scenario 1 — Steady State (1,000 Users)

```
Duration: 10 minutes
Ramp: 0 → 1,000 users over 2 minutes → hold 8 minutes

Actions per virtual user (randomised):
- 30% browse conversation list
- 30% read message history
- 20% send Chikka messages (1 per 10s)
- 10% send SMS (simulation mode)
- 10% idle / typing

Targets:
- p95 API response: < 300ms
- p95 message delivery: < 500ms
- Error rate: < 0.5%
- No memory leak (stable heap over 10 min)
```

### Scenario 2 — SMS Burst

```
Duration: 2 minutes
Pattern: 100 SMS send requests per minute (peak burst)

Targets:
- All requests accepted (202) or correctly rate-limited (429)
- No duplicate credits deducted
- No dropped requests
- Retry queue drains within 60s of burst end
```

### Scenario 3 — WebSocket Concurrency

```
Duration: 5 minutes
Pattern: 1,000 clients connect and subscribe to conversation channels

Targets:
- All 1,000 connections established within 30s
- Message broadcast latency < 500ms at 1,000 clients
- No dropped connections after steady state
```

### Scenario 4 — Database Concurrent Credit Operations

```
Pattern: 50 concurrent SMS send requests from the same user

Targets:
- Balance never goes negative
- Credit deductions total exactly (cost × successful sends)
- No deadlocks
```

---

## 4. k6 Script Skeleton

```javascript
// performance/scenarios/steady-state.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import ws from 'k6/ws';

export const options = {
  scenarios: {
    steady_state: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 1000 },
        { duration: '8m', target: 1000 },
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<300'],
    http_req_failed: ['rate<0.005'],
    ws_connecting: ['p(95)<1000'],
  },
};

export default function () {
  const token = getTestUserToken();

  // Browse conversation list
  const r = http.get(`${BASE_URL}/api/v1/conversations`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  check(r, { 'conversations 200': (r) => r.status === 200 });

  sleep(Math.random() * 5 + 1);
}
```

---

## 5. Frontend Performance Monitoring

### Lighthouse CI (Every Build)

```yaml
# .github/workflows/lighthouse.yml
- name: Run Lighthouse CI
  uses: treosh/lighthouse-ci-action@v11
  with:
    urls: |
      https://staging.chikka-reborn.app/login
      https://staging.chikka-reborn.app/app/messages
    budgetPath: ./lighthouse-budget.json
    uploadArtifacts: true
```

```json
// lighthouse-budget.json
[
  {
    "path": "/*",
    "timings": [
      { "metric": "first-contentful-paint", "budget": 2000 },
      { "metric": "largest-contentful-paint", "budget": 3500 },
      { "metric": "total-blocking-time", "budget": 300 }
    ],
    "scores": [
      { "category": "performance", "minScore": 0.8 },
      { "category": "accessibility", "minScore": 0.9 }
    ]
  }
]
```

---

## 6. Database Query Performance

### Key Queries to Benchmark

| Query | Expected | Index Used |
|---|---|---|
| `SELECT messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 50` | < 10ms | `idx_messages_conversation_id` |
| `SELECT contacts WHERE owner_id = ?` | < 5ms | `idx_contacts_owner_id` |
| `SELECT outbound_sms WHERE sender_user_id = ? ORDER BY created_at DESC LIMIT 20` | < 10ms | `idx_outbound_sms_sender` |
| `SELECT credit_accounts WHERE user_id = ? FOR UPDATE` | < 5ms | PK lookup |
| `SELECT country_capabilities WHERE country_code = ?` | < 2ms | `idx_country_capabilities_code` |

Run `EXPLAIN (ANALYZE, BUFFERS)` on each after Phase 1 data load. Flag any sequential scans on tables expected to have > 1,000 rows.

---

## 7. Phase-by-Phase Performance Milestones

| Phase | Performance Activity |
|---|---|
| 1 | Baseline API benchmarks. Lighthouse first pass on staging. |
| 2 | WebSocket connection test (Supabase Realtime plan limit check). DB query benchmarks. |
| 3 | AI endpoint latency measured against 5s target. |
| 5 | Lighthouse score must reach ≥ 85 (AC-5-007). |
| 6 | Full load test scenarios 1–4. Stress test. Break-point analysis. |

---

## 8. Performance Issue Escalation

| Severity | Trigger | Action |
|---|---|---|
| Critical | API p95 > 1000ms under normal load | Stop Phase progression; investigate before proceeding |
| High | API p95 300–1000ms | Investigate within 48h; fix before Phase completion |
| Medium | Lighthouse score 70–84 | Fix before Phase 5 completion |
| Low | Single slow query (> 50ms) | Add to backlog; fix in next sprint |

---

## 9. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |

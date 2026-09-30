# Proposed acceptance targets

These targets require stakeholder agreement and a production test environment. They are not measured interview results.

| ID / area | Measurable target | Verification |
|---|---|---|
| NFR-01 Security | TLS 1.2+; OIDC with MFA for privileged actors; deny unauthorised object access on every protected route; no critical/high exploitable findings at release | Threat model, API authorisation tests, SAST/dependency/DAST review |
| NFR-02 Availability | 99.9% monthly API availability excluding agreed maintenance; payment ingestion remains independent of SMS/FMIS | Synthetic probes, failure drills, measured error budget |
| NFR-03 Performance | At 5,000 payments/minute, payment commit p95 <1s and p99 <3s; report p95 <2s; overnight 1M-obligation scan completes within 30min | Load test including concurrent duplicates, queue/lock/DB metrics |
| NFR-04 Scalability | Double API workers without duplicate financial effects; scan paginates at ≤10,000 obligations per transaction | Multi-instance concurrency test and explain plans |
| NFR-05 Auditability | 100% enforcement and monetary transitions have correlation/actor/time/policy evidence; audit export delivered daily to write-protected storage | Cross-check ledger transitions to events; tamper/restore drill |
| NFR-06 Privacy | Mask contacts in operational lists/logs; no identifiers in payment URLs; proposed seven-year audit retention with lawful hold | Log scan, privacy review, retention/erasure tests |
| NFR-07 Accessibility | WCAG 2.2 AA; ≥44px touch controls; keyboard completion; no horizontal scrolling at 768px; labelled errors and screen-reader status | Automated accessibility checks plus keyboard/screen-reader manual review |
| NFR-08 Observability | Alert within 5min for ingestion error >1%, queue oldest age >5min, or unresolved FMIS batch >30min; correlation spans across jobs | Inject failures and confirm alert delivery/runbook |
| NFR-09 Reliability | Zero duplicate payments/journals under retry, crash and concurrent request tests; notification delivery is at-least-once with business deduplication | Fault injection around commit/response boundary |
| NFR-10 Recoverability | Proposed ledger RPO ≤5min, RTO ≤60min; quarterly restore/reconciliation drill | PITR rehearsal and provider/FMIS comparison |
| NFR-11 Maintainability | Versioned API/schema/rules; changes require reviewed migration/rollback plan and regression tests; setup runnable in one documented command | Clean-machine build and upgrade rehearsal |

Balance safety is a release gate independent of throughput. Slow processing should create visible backpressure rather than acknowledge uncommitted money. Capacity tests must include realistic data distributions, indexes, gateway delay and cold caches; tiny synthetic seeds cannot establish these targets.

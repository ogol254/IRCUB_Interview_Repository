# Implementation plan and baseline review

Read the complete Word assessment on 2026-09-30 before changes. Scope: Section 1 and Section 3 only. Sections 2, 4, 5 and 6 remain unchanged.

1. Preserve the original examples as historical reference; replace their role in the submission with one runnable Python/FastAPI/PostgreSQL/Redis/React solution (updated per candidate instruction).
2. Add schema, explicit water-account/billing-period links, synthetic seeds, reporting functions and transactional penalty routine. Test multi-payment and multi-account cases.
3. Implement configured tariffs, bounded payment workers, database idempotency, authenticated callbacks, FMIS batching/mock and cache-aside reports.
4. Build an accessible tablet payment journey using an officer API credential entered at runtime, never provider HMAC secrets in the browser.
5. Run unit, integration, SQL and frontend checks; record executed evidence and environmental limitations.
6. Write Section 3 requirements, models, stakeholder diagrams and acceptance criteria; update existing coloured Word answers while preserving questions.

Baseline gaps: no database schema/infrastructure; in-memory payment uniqueness/replay state; floating-point API amounts; no durable FMIS batch; no Redis implementation; no integrated frontend; Section 3 answer.md missing. Original backend tests are replaced with unit/integration tests for the improved in-place Python modules.

Estimation assumption to resolve explicitly: average the latest three actual meter values into three consumption intervals requires four actual readings. Lower readings require an explicit rollover flag. Penalty month semantics and snapshot recalculation will be documented rather than silently changed.

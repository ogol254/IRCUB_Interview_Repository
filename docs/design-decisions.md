# Section 1 engineering decisions

| Decision | Reason | Trade-off / limit |
|---|---|---|
| Keep Python/FastAPI and the existing section directories | Candidate requested continuity; original algorithms remain recognisable | No .NET conversion or unnecessary layered directory tree |
| psycopg parameterised SQL over an ORM | Assessment is SQL-heavy; locks, constraints and transaction boundaries are visible | Schema changes are explicit migrations; no automatic model migrations |
| Explicit account/billing period on water assessment | A payer can have multiple accounts; due date is not billing month | Added fields must be supplied for linked water bills |
| Decimal/numeric money, numeric JSON parsed directly as Decimal | Large financial numbers cannot lose cents during JSON parsing | API returns money as strings; UI validates a smaller safe integer-cent range |
| Bounded asyncio workers with DB uniqueness | Concurrent IO without unlimited tasks; database protects multiple API instances | Queue is in memory, so callers retry unchanged keys after process loss |
| Persist financial effect and item receipt together | Bulk response loss cannot require guessing which items committed | Independent item commits require per-item result handling |
| Redis versioned cache-aside keys | Transactional invalidation and no stale repopulation race | DB version read per report; global version row can limit high-volume writes |
| Durable FMIS membership and stable batch ID | Prevent new journals after an accepted-but-lost response | Integration contract must provide idempotency/lookup; failed batches need evidence review |
| Serialize FMIS posting and bound request coordinators | Preserve pool capacity and avoid competing batch claims | Demonstration prioritises correctness over parallel posting throughput |
| One React form with plain CSS and Lucide icons | Clear tablet journey without framework/tooling excess | Shared component library would become useful with more screens |
| Runtime officer key, provider HMAC never in React | Demonstrate protected APIs without implementing Section2 user management | Local-only authentication model; production OIDC/object permissions remain design scope |
| Keep original HTML as historical reference; SQL entry filenames forward to new queries | Preserve provenance without duplicate active implementations | README/Word point to the real app, not the HTML sketch |

Business-rule assumptions are separately documented in component READMEs: explicit rollover, three actual consumption intervals derived from four readings, started overdue months, non-compounding current-unpaid penalty snapshots, USD and UTC reporting. Section3 policy assumptions are proposed requirements, not silently applied to Section1.

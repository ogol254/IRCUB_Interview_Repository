# PostgreSQL answers — Section 1, Database Q1–Q3

Requires PostgreSQL 16. Compose initializes a new `pgdata` volume with migrations 001–003 and `seed/001_demo.sql`. Run from the repository root:

```sh
python scripts/setup.py
docker compose up -d postgres redis
docker compose exec postgres psql -U ircub -d ircub
```

Within psql, demonstrate:

```sql
SELECT * FROM quarterly_collections('2026-01-01','2027-01-01');
SELECT * FROM collection_efficiency('2026-09-30T23:59:59Z');
SELECT * FROM water_arrears('2026-09-30');
BEGIN;
CALL apply_overdue_penalties('2026-09-30');
CALL apply_overdue_penalties('2026-09-30');
COMMIT;
SELECT * FROM penalty_history;
```

For a native PostgreSQL installation, create an empty `ircub` database with a local role; apply migration files in filename order using `psql -v ON_ERROR_STOP=1 -f <file>`, then seed. These are ordered bootstrap migrations, not safe to rerun against existing tables. An existing Docker volume does not rerun init scripts; inspect it rather than assuming migrations ran. `docker compose down` preserves data. Do not remove volumes unless intentionally discarding test data.

## Supplied model and extensions

| Change | Why it is required | Assessment relationship |
|---|---|---|
| `assessment.account_no`, `billing_period` | Payer can own multiple water accounts; due date is not billing month | Database Q2, preserves assessment principal |
| `meter_reading.rollover_confirmed` | Explicitly distinguish a rollover from invalid lower history | Backend water estimation |
| `assessment.penalty_amount`, `penalty_history` | Snapshot and unique same-day evidence | Database Q3 |
| Global `payment.external_ref` unique | Prevent concurrent duplicates regardless of callback key | Backend validation and API questions |
| Composite assessment/payer/revenue FK | Payment cannot settle another payer/revenue's assessment | Financial allocation safety |
| `failed_payment` | Durable rejected item and reasons | Backend Q2/Q3 |
| `idempotency_record`, `callback_replay`, `payment_processing_log` | Request hashes, replay identity and recoverable item results | Backend Q3; item receipt and financial effect share transaction |
| `fmis_batch`, `fmis_batch_line`, payment membership | Immutable group membership, attempts and returned reference | Backend Q4 |
| `mock_fmis_journal` | Mock accepts a batch once even when reply is lost | Backend Q4 demonstration |
| `report_version` + insert trigger | Transactional cache-key invalidation | Backend Q5; correctness independent of Redis |

Money is `numeric(18,2)` and Python Decimal. Demonstration currency is USD only; mixing currencies in totals is prohibited. `payment.assessment_id` is optional to preserve the supplied model: the officer form records unallocated collections. Q2 and penalties include only assessment-linked payments. Full allocation across penalties, instalments and multiple debts is Section 3 design scope, not a hidden POC feature.

## Q1 — quarterly collections and 50M-row design

The function validates an exactly one-year financial period, creates four three-month intervals from the supplied start, then cross-joins *all* revenue types (including inactive types with historical collections). Left joining payments produces zero totals. Window sums calculate running totals and quarterly shares; an empty quarter's share is 0 rather than division by zero. UTC date boundaries and exclusive end avoid end-of-day errors.

Index `(paid_at,revenue_code) INCLUDE(amount,currency)` supports range filtering and covering opportunities. Index-only scans depend on visibility-map coverage and vacuum; INCLUDE is not a promise of index-only execution. For selective revenue reports consider `(revenue_code,paid_at) INCLUDE(amount)`, at the cost of write/storage overhead. `external_ref` unique B-tree is for callbacks, not quarterly aggregation. `assessment_id INCLUDE(amount)` supports allocation/efficiency. Append-heavy date ranges may benefit from a small BRIN index after measuring correlation. For an entire year's large fraction, sequential/parallel scans can outperform B-trees.

At 50M rows consider monthly range partitions on `paid_at` for pruning/retention. Do **not** copy the original answer's partitioning claim blindly: PostgreSQL partitioned unique constraints must include the partition key. `(external_ref,paid_at)` would allow duplicate references on different dates. A production partition migration therefore needs a nonpartitioned global reference registry claimed in the *same transaction* as the partitioned payment insert, plus composite payment/date FKs. This demo deliberately remains nonpartitioned to keep authoritative global uniqueness. [PostgreSQL partition limitations](https://www.postgresql.org/docs/16/ddl-partitioning.html#DDL-PARTITIONING-DECLARATIVE-LIMITATIONS).

Explain the underlying aggregation, since EXPLAIN of a PL/pgSQL function alone hides internal scans:

```sql
ANALYZE payment;
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT revenue_code,sum(amount) FROM payment
WHERE paid_at >= '2026-01-01T00:00:00Z' AND paid_at < '2027-01-01T00:00:00Z'
GROUP BY revenue_code;
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM quarterly_collections('2026-01-01','2027-01-01');
```

Check estimated versus actual rows, reads/hits, heap fetches, sort spills, parallel workers and execution time. On partitions confirm only relevant children are scanned. Seed-data plans validate syntax, not 50M-row latency. A daily summary table can reduce full-year query cost but adds rebuild/reconciliation responsibility.

## Q2 — collection efficiency

Payments are aggregated once per assessment *before* joining bills. Bills link accounts by `account_no`, never payer alone. Collection is for each billed cohort up to `as_of`, not all cash received in the billing month. Two seed payments (100 + 200) against a 1000 domestic bill yield 300 collected /30%; a second commercial account for the same payer independently yields 2000/0. Outstanding arrears exclude payments after the selected as-of date and use strictly more than 90 days. Ties have deterministic account ordering. Penalties are separate from this principal-efficiency metric.

## Q3 — penalty policy and transaction semantics

Assumption: charge **started** overdue monthly anniversaries; not overdue=0; day after due date=month 1; exact three-month anniversary=3; day after it=4. Current unpaid principal at the run-date cutoff is multiplied by cumulative rate `min(months,3)*5% + max(months-3,0)*10%`, capped at original principal. This is a snapshot recalculation, not compounding or daily accumulation; later principal payments can reduce the recalculated penalty. The source does not specify pro-rating or preserving already accrued historical penalties, so a different agency policy requires sign-off and a versioned change.

Procedure locks assessments in ID order. Application allocation locks the same row. Unique `(assessment_id,penalty_date)` guarantees same-day insertion once; update occurs only for the successful insert. Caller transaction covers history and assessment. Same-day recalculation deliberately does not change after a later payment; next-day run reflects it. Run against the current business date; backdated runs are for tests and are not a full temporal ledger of historical statuses.

## Tests

From root, install Python dependencies and run `python -m pytest tests/test_database.py -q`. Tests create and remove fresh isolated databases, never mutate the demonstration ledger. Includes shifted FY, empty quarters, inactive revenues, multi-payment/multi-account correctness, not overdue, first/third/fourth months, partial payment, cap, concurrent same-day execution and rollback.

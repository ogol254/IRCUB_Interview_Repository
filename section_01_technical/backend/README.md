# Python API — Section 1 Backend Q1–Q5

Python 3.13, FastAPI, psycopg async pool, Redis and httpx. The existing backend directory is the application: `payment_api.py` routes/authentication; `payment_processor.py` bounded workers and allocation; `water_bill.py` configured tariff calculation; `fmis_service.py` journal lifecycle; `cache.py` reporting; `mock_fmis.py` executable integration partner. Direct parameterised SQL makes transaction boundaries and assessment queries inspectable. No additional service layers are needed for nine interview questions.

## Prerequisites and configuration

Docker Desktop/Engine with Compose v2, Python 3.13 for native run/tests. PostgreSQL 16 and Redis 7 can run through Compose. Node is needed only for the frontend. From root:

```sh
python scripts/setup.py
docker compose up --build -d
```

`.env` contains randomly generated `POSTGRES_PASSWORD`, `CALLBACK_SECRET`, `OFFICER_API_KEY`, `FMIS_API_KEY`. It is ignored and setup preserves existing values. Never commit it. Native launcher loads `.env`; direct uvicorn needs `DATABASE_URL`, `REDIS_URL`, `FMIS_URL` and these credentials exported. `CORS_ORIGINS` defaults to `http://localhost:5173`. `MOCK_FMIS_MODE`: normal / transient / permanent / accept-timeout. Tariffs, worker count, queue capacity, report TTL and bank GL live in `config.json`; tariff amounts are Decimal strings, not business-logic constants.

For native development (root working directory):

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate ; macOS/Linux: source .venv/bin/activate
python -m pip install -r section_01_technical/backend/requirements.txt
docker compose up -d postgres redis
python scripts/run_backend.py --fmis
# second terminal, same environment:
python scripts/run_backend.py
```

Swagger: http://localhost:8000/docs ; OpenAPI: http://localhost:8000/openapi.json ; health: http://localhost:8000/health ; mock Swagger: http://localhost:8001/docs. Health checks PostgreSQL; Redis is optional. Docker volumes initialize migrations/seed once; see [database setup](../database/README.md).

## Water billing

Domestic configured marginal bands are 0–10 at 50, next 20 at 75, remainder at 110, plus service 200. Examples: 0→200; 10→700; 11→775; 30→2200; 31→2310. Confirm rollover explicitly: 99990→15 on five digits =25 units, amount1825. An unexplained lower value is invalid, not automatically billed as huge consumption. Estimated consumption is the Decimal mean of the last three **actual consumption intervals**, derived from four chronological actual meter values; estimated values are excluded. The endpoint accepts these intervals or loads the latest four actual database readings with {"estimate":true,"meter_no":"M-001"}. Missing history is rejected. Numeric JSON payments are parsed directly as Decimal; returned money uses decimal strings. The wording “last 3 actual readings” is ambiguous about cumulative register values; this interpretation avoids billing the register total. Agency confirmation is required for another policy. Decimal values are retained until final cent rounding (half up).

```sh
curl -X POST http://localhost:8000/api/v1/water/calculate -H "Content-Type: application/json" -H "X-Officer-Key: $OFFICER_API_KEY" -d '{"previous":"99990","current":"15","digits":5,"rollover":true}'
```

## Payment capture and notifications

Officer bulk endpoint accepts JSON array, provider callback a single object. Optional `assessment_id` allocates principal; omission creates unallocated collections. Required fields: payer_id, revenue_code, amount as decimal string, channel, external_ref; currency defaults USD. Unknown fields reject an item. Amount >0, at most two decimals; payer/revenue valid and active. Stored rejections include all applicable reasons. No full callback bodies/credentials are written to logs.

```sh
curl -X POST http://localhost:8000/api/v1/payments/bulk \
  -H "X-Officer-Key: $OFFICER_API_KEY" -H "Idempotency-Key: officer-demo-001" \
  -H "Content-Type: application/json" \
  -d '[{"payer_id":1,"revenue_code":"WATER","amount":"12.50","channel":"MOBILE_MONEY","external_ref":"DEMO-OFFICER-001"}]'
curl http://localhost:8000/api/v1/payments/PAYMENT_UUID -H "X-Officer-Key: $OFFICER_API_KEY"
```

Environment variables in these curl commands are shell variables you load from your local `.env`; generated values are intentionally absent from this README. In PowerShell use `curl.exe`, `$env:OFFICER_API_KEY` and `--data-binary @file.json` to avoid quoting differences. `python scripts/smoke.py` signs and runs complete local examples without printing secrets.

Provider: HMAC-SHA256 over ASCII Unix seconds + `.` + exact raw JSON bytes. Headers `X-Timestamp`, `X-Signature` (hex), `Idempotency-Key`. Signature verified with constant-time comparison; ±300-second window. Repeat same key/body returns original receipt; same key/different bytes=409; same signature under another key=409. Idempotency remains in PostgreSQL across process restarts. Timestamp must be fresh even when fetching a stored result. Provider can resend a fresh signed unchanged body under the original key.

```sh
printf '%s' '{"payer_id":1,"assessment_id":1,"revenue_code":"WATER","amount":"10.00","channel":"MOBILE_MONEY","external_ref":"DEMO-CALLBACK-001"}' > callback.json
timestamp=$(date +%s)
signature=$(python -c 'import os,hmac,hashlib,sys; print(hmac.new(os.environ["CALLBACK_SECRET"].encode(),sys.argv[1].encode()+b"."+open("callback.json","rb").read(),hashlib.sha256).hexdigest())' "$timestamp")
curl -X POST http://localhost:8000/api/v1/payments/callback \
  -H 'Content-Type: application/json' -H "X-Timestamp: $timestamp" \
  -H "X-Signature: $signature" -H 'Idempotency-Key: callback-demo-001' --data-binary @callback.json
```

HTTP: 200 item summary (including mixed/rejected batch), 400 malformed envelope/missing key, 401 unauthenticated/invalid signature/time, 409 conflicting key/replay, 413 oversized body, 422 invalid typed query/billing inputs, 404 missing payment, 503 infrastructure failure with correlation ID. A 200 with rejected items is **not** a financial acceptance. OpenAPI describes callback headers and payload; use Swagger Authorize for officer routes.

## Concurrency, recovery and transactions

Four async workers consume a bounded queue (128); submission waits on capacity. Three concurrent request coordinators leave database pool capacity for workers, preventing pool starvation behind advisory locks. Request-level PostgreSQL session lock serializes same key; unique key stores body hash. Each item transaction includes either payment/allocation **or** failed_payment, plus `payment_processing_log` result. If the process dies before a bulk response is stored, retry reuses committed item results and finishes remaining items. Queue is not durable; no successful HTTP acknowledgement is returned until item results are committed. Retrying unchanged key/body is the recovery contract.

Unique external reference protects different keys/processes. Assessment row lock serializes allocation/penalty snapshots; composite FK enforces payer/revenue match. Database insertion trigger invalidates reports transactionally. Bulk items are independently committed, so clients must inspect per-item results; bulk is intentionally not all-or-nothing. Operational SQL review is available for rejected rows; a rejection-management UI is outside Section 1.

## FMIS

```sh
curl -X POST 'http://localhost:8000/api/v1/fmis/post?day=2026-01-15' -H "X-Officer-Key: $OFFICER_API_KEY"
curl http://localhost:8000/api/v1/fmis/batches -H "X-Officer-Key: $OFFICER_API_KEY"
curl http://localhost:8001/journals -H "X-FMIS-Key: $FMIS_API_KEY"
```

Journal claims unbatched successful payments by UTC business date, groups revenue→configured GL, debits collection GL, credits revenue lines, validates balance before HTTP. Persisted batch membership prevents posting a payment twice. Session lock serializes claims and posts; attempts persist **before** sending. Three attempts total, delays 1s/2s. Retry only 408/429/5xx/timeouts/network; permanent errors immediately mark FAILED/manual review. A failed payment's batch cannot be silently regenerated. For manual resolution compare provider and FMIS lookup by the same batch ID; approve a controlled retry of that batch only after evidence review. No manual-reset endpoint is exposed in the interview demo.

The mock persists batch/hash/reference; changing an existing batch returns409. Set `MOCK_FMIS_MODE=accept-timeout` in `.env`, recreate mock container (`docker compose up -d --force-recreate mock-fmis`), and post a new day: first acceptance commits but reply exceeds 3s; retry returns the same reference. `permanent` demonstrates422/one attempt; `transient` demonstrates503/three attempts. Revert to normal afterwards.

Reconcile [queries/reconciliation.sql](../database/queries/reconciliation.sql): compare day/currency/GL amounts and counts, then drill from payment external reference→batch membership→journal→FMIS reference. Two-way comparison must identify both missing and extra FMIS entries. Production requires a provider statement and authenticated FMIS exports; the local mock is not evidence that a real FMIS honours the contract.

## Redis reports

Cache-aside key includes namespace, database version, currency and FY start/end. TTL60s; miss computes PostgreSQL data and populates Redis. Repeatable-read snapshot pairs totals/version. Payment insert bumps version in the same transaction, so stale concurrent writers populate obsolete keys and cannot revive a stale report. Old keys expire naturally. Redis connection/read/write timeout is short; failures log and return DB data. Version read costs a DB roundtrip; one global version row is deliberately simple but a write hotspot at high volume. Production could use per-period versions after measurement. Financial integrity never relies on Redis.

## Tests and troubleshooting

`python -m pytest -q` from root runs units plus integration tests against local PostgreSQL/Redis. Isolated disposable test databases require CREATE DATABASE permission on the **local demo role**; production API must use a non-superuser least-privilege role. `python -m pytest -m 'not integration' -q` runs units only. See root TEST-REPORT.md for actual evidence.

Windows async driver needs selector event-loop policy; use `scripts/run_backend.py`. Native URLs use127.0.0.1 to avoid IPv6 stalls. Missing credentials fail startup; port conflicts require changing Compose mapping and frontend API URL. Inspect `docker compose logs backend postgres mock-fmis`. A 503 after a partial bulk commit calls for unchanged-key retry. An FMIS timeout never justifies a new journal ID.

Local API keys are a deliberate narrow interview control, not production user management. Production needs OIDC/object authorisation, provider-specific secret rotation, rate limits/body streaming limits at ingress, TLS, restricted DB roles, audit protection and backups. Those are design boundaries, not an implemented Section 2 POC.

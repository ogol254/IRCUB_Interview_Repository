import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4
import httpx
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from psycopg.types.json import Jsonb
from redis.asyncio import Redis
from .db import create_pool, one, rows
from .settings import required
from .payment_processor import PaymentProcessor, PaymentInput
from .water_bill import WaterBillingService
from .cache import SummaryCache
from .fmis_service import FmisPostingService


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for key in (
            "payment_id",
            "batch_id",
            "attempt",
            "reason",
            "reasons",
            "correlation_id",
        ):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
log = logging.getLogger("ircub.api")


@asynccontextmanager
async def lifespan(app):
    for name in (
        "CALLBACK_SECRET",
        "OFFICER_API_KEY",
        "FMIS_API_KEY",
        "FMIS_URL",
        "REDIS_URL",
    ):
        required(name)
    app.state.pool = create_pool()
    await app.state.pool.open(wait=True)
    app.state.processor = PaymentProcessor(app.state.pool)
    await app.state.processor.start()
    app.state.request_gate = asyncio.Semaphore(3)
    app.state.fmis_gate = asyncio.Semaphore(1)
    app.state.redis = Redis.from_url(
        required("REDIS_URL"), socket_connect_timeout=0.3, socket_timeout=0.3
    )
    app.state.cache = SummaryCache(app.state.pool, app.state.redis)
    app.state.http = httpx.AsyncClient()
    app.state.fmis = FmisPostingService(app.state.pool, app.state.http)
    yield
    await app.state.processor.close()
    await app.state.http.aclose()
    await app.state.redis.aclose()
    await app.state.pool.close()


app = FastAPI(title="IRCUB Section 1 Interview API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Officer-Key", "Idempotency-Key"],
)
officer_header = APIKeyHeader(name="X-Officer-Key", auto_error=False)


async def officer(key=Depends(officer_header)):
    if not key or not hmac.compare_digest(key, required("OFFICER_API_KEY")):
        raise HTTPException(401, "invalid officer credential")


@app.middleware("http")
async def errors(request, call_next):
    correlation = str(uuid4())
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request_failed", extra={"correlation_id": correlation})
        response = JSONResponse(
            status_code=503,
            content={
                "detail": "Service unavailable. Retry the unchanged request with the same Idempotency-Key.",
                "correlation_id": correlation,
            },
        )
    response.headers["X-Correlation-ID"] = correlation
    return response


def verify(raw, signature, timestamp):
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        raise HTTPException(401, "invalid timestamp")
    if abs(int(time.time()) - ts) > 300:
        raise HTTPException(401, "timestamp outside five-minute window")
    expected = hmac.new(
        required("CALLBACK_SECRET").encode(),
        timestamp.encode() + b"." + raw,
        hashlib.sha256,
    ).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "invalid HMAC signature")


async def handle(request, bulk, callback=False):
    async with app.state.request_gate:
        return await handle_locked(request, bulk, callback)


async def handle_locked(request, bulk, callback=False):
    raw = await request.body()
    if len(raw) > 256000:
        raise HTTPException(413, "request too large")
    signature = request.headers.get("X-Signature", "")
    if callback:
        verify(raw, signature, request.headers.get("X-Timestamp", ""))
    key = request.headers.get("Idempotency-Key", "").strip()
    if not 1 <= len(key) <= 100:
        raise HTTPException(400, "Idempotency-Key required (1–100 characters)")
    key = ("provider:" if callback else "officer:") + key
    try:
        payload = json.loads(
            raw,
            parse_float=Decimal,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("non-finite JSON")
            ),
        )
        items = payload if bulk else [payload]
        if (
            not isinstance(items, list)
            or not 1 <= len(items) <= 100
            or any(not isinstance(p, dict) for p in items)
        ):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(
            400, "expected payment object or bulk array of 1–100 objects"
        )
    digest = hashlib.sha256(raw).hexdigest()
    async with app.state.pool.connection() as conn:
        # Session lock survives intermediate commits. Crash releases it; item results survive.
        await conn.execute("SELECT pg_advisory_lock(hashtextextended(%s,0))", (key,))
        await conn.commit()
        try:
            async with conn.transaction():
                old = await one(
                    conn, "SELECT * FROM idempotency_record WHERE key=%s", (key,)
                )
                if old:
                    if old["body_hash"] != digest:
                        raise HTTPException(
                            409, "idempotency key reused with changed payload"
                        )
                    if old["response"] is not None:
                        return old["response"]
                else:
                    if callback:
                        replay = await one(
                            conn,
                            "INSERT INTO callback_replay(signature) VALUES(%s) ON CONFLICT DO NOTHING RETURNING signature",
                            (signature,),
                        )
                        if not replay:
                            raise HTTPException(
                                409, "callback replay under different key"
                            )
                    await conn.execute(
                        "INSERT INTO idempotency_record(key,body_hash) VALUES(%s,%s)",
                        (key, digest),
                    )
            results = await asyncio.gather(
                *(app.state.processor.submit(p, key, i) for i, p in enumerate(items))
            )
            response = {
                "received": len(items),
                "accepted": sum(r["status"] == "ACCEPTED" for r in results),
                "rejected": sum(r["status"] == "REJECTED" for r in results),
                "results": results,
            }
            async with conn.transaction():
                await conn.execute(
                    "UPDATE idempotency_record SET response=%s WHERE key=%s",
                    (Jsonb(response), key),
                )
            return response
        finally:
            await conn.execute(
                "SELECT pg_advisory_unlock(hashtextextended(%s,0))", (key,)
            )
            await conn.commit()


@app.get("/health")
async def health():
    async with app.state.pool.connection() as conn:
        await conn.execute("SELECT 1")
    return {"status": "ok", "database": "ok"}


@app.post(
    "/api/v1/payments/callback",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": PaymentInput.model_json_schema()}
            },
        },
        "parameters": [
            {
                "name": name,
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
            }
            for name in ("X-Timestamp", "X-Signature", "Idempotency-Key")
        ],
    },
    description="X-Timestamp: Unix seconds; X-Signature: hex HMAC-SHA256(timestamp + dot + exact raw body); Idempotency-Key required. Same key/body returns stored result; changed body = 409. Accepted/rejected item summary = 200; auth = 401; malformed = 400; replay = 409.",
)
async def callback(request: Request):
    return await handle(request, False, True)


@app.post(
    "/api/v1/payments/bulk",
    dependencies=[Depends(officer)],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 100,
                        "items": PaymentInput.model_json_schema(),
                    }
                }
            },
        },
        "parameters": [
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
            }
        ],
    },
)
async def bulk(request: Request):
    return await handle(request, True)


@app.get("/api/v1/payments/{payment_id}", dependencies=[Depends(officer)])
async def payment(payment_id: UUID):
    async with app.state.pool.connection() as conn:
        result = await one(
            conn, "SELECT * FROM payment WHERE payment_id=%s", (payment_id,)
        )
    if not result:
        raise HTTPException(404, "payment not found")
    result["amount"] = str(result["amount"])
    return result


@app.get("/api/v1/payers", dependencies=[Depends(officer)])
async def payers(q: str = Query(min_length=2, max_length=100)):
    async with app.state.pool.connection() as conn:
        return await rows(
            conn,
            """SELECT p.payer_id,p.full_name,p.tin,p.phone FROM payer p WHERE p.tin ILIKE %s OR p.phone ILIKE %s OR EXISTS(SELECT 1 FROM water_account w WHERE w.payer_id=p.payer_id AND w.account_no ILIKE %s) ORDER BY p.full_name LIMIT 20""",
            tuple("%" + q + "%" for _ in range(3)),
        )


@app.get("/api/v1/revenues", dependencies=[Depends(officer)])
async def revenues():
    async with app.state.pool.connection() as conn:
        return await rows(
            conn,
            "SELECT revenue_code,name,category FROM revenue_type WHERE is_active ORDER BY name",
        )


class BillingRequest(BaseModel):
    previous: Decimal | None = None
    current: Decimal | None = None
    digits: int = 5
    rollover: bool = False
    actual_consumptions: list[Decimal] | None = None
    meter_no: str | None = None
    estimate: bool = False


@app.post("/api/v1/water/calculate", dependencies=[Depends(officer)])
async def water(body: BillingRequest):
    try:
        if body.estimate:
            if not body.meter_no:
                raise ValueError("meter_no required for database estimation")
            async with app.state.pool.connection() as conn:
                actual = await rows(
                    conn,
                    "SELECT * FROM meter_reading WHERE meter_no=%s AND reading_type='ACTUAL' ORDER BY reading_date DESC LIMIT 4",
                    (body.meter_no,),
                )
            result = WaterBillingService().estimate_from_readings(actual, body.digits)
        else:
            result = WaterBillingService().bill(
                **body.model_dump(exclude={"meter_no", "estimate"})
            )
        return json.loads(json.dumps(result, default=str))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/v1/reports/quarterly", dependencies=[Depends(officer)])
async def summary(start: date, end: date):
    try:
        if end != start.replace(year=start.year + 1):
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "financial year must span one calendar year")
    return await app.state.cache.summary(start, end)


@app.post("/api/v1/fmis/post", dependencies=[Depends(officer)])
async def fmis(day: date):
    async with app.state.fmis_gate:
        return await app.state.fmis.post_day(day)


@app.get("/api/v1/fmis/batches", dependencies=[Depends(officer)])
async def batches():
    async with app.state.pool.connection() as conn:
        return await rows(
            conn, "SELECT * FROM fmis_batch ORDER BY created_at DESC LIMIT 100"
        )

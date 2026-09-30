import asyncio
import hashlib
import json
import logging
from decimal import Decimal, InvalidOperation
from uuid import uuid4
import httpx
from .db import one, rows
from .settings import CONFIG, required

log = logging.getLogger("ircub.fmis")


def validate_journal(lines):
    try:
        for line in lines:
            for field in ("debit", "credit"):
                value = Decimal(str(line[field]))
                if (
                    not value.is_finite()
                    or value < 0
                    or value != value.quantize(Decimal(".01"))
                ):
                    raise ValueError("journal amounts must be finite nonnegative cents")
            if not isinstance(line.get("gl_code"), str) or not line["gl_code"].strip():
                raise ValueError("GL code required")
    except (InvalidOperation, KeyError, TypeError) as exc:
        raise ValueError("invalid journal line") from exc
    debit = sum((Decimal(str(l["debit"])) for l in lines), Decimal(0))
    credit = sum((Decimal(str(l["credit"])) for l in lines), Decimal(0))
    if (
        not lines
        or debit <= 0
        or debit != credit
        or any(
            Decimal(str(l["debit"])) < 0
            or Decimal(str(l["credit"])) < 0
            or (Decimal(str(l["debit"])) > 0) == (Decimal(str(l["credit"])) > 0)
            for l in lines
        )
    ):
        raise ValueError("journal must have positive balanced debit/credit lines")


def transient(status):
    return status in (408, 429) or status >= 500


class FmisPostingService:
    def __init__(self, pool, client, sleep=asyncio.sleep):
        self.pool, self.client, self.sleep = pool, client, sleep

    async def post_day(self, day):
        # Global session advisory lock prevents concurrent claim/post; journal persists before HTTP.
        async with self.pool.connection() as conn:
            await conn.execute("SELECT pg_advisory_lock(87002)")
            await conn.commit()
            try:
                async with conn.transaction():
                    batch = await one(
                        conn,
                        "SELECT * FROM fmis_batch WHERE business_date=%s AND status='PENDING' ORDER BY created_at LIMIT 1",
                        (day,),
                    )
                    if not batch:
                        payments = await rows(
                            conn,
                            "SELECT payment_id FROM payment WHERE paid_at>=%s::date::timestamp AT TIME ZONE 'UTC' AND paid_at<(%s::date+1)::timestamp AT TIME ZONE 'UTC' AND batch_id IS NULL ORDER BY payment_id FOR UPDATE",
                            (day, day),
                        )
                        if not payments:
                            return {"status": "EMPTY"}
                        batch_id = uuid4()
                        await conn.execute(
                            "INSERT INTO fmis_batch(batch_id,business_date,currency,status) VALUES(%s,%s,'USD','PENDING')",
                            (batch_id, day),
                        )
                        await conn.execute(
                            "UPDATE payment SET batch_id=%s WHERE payment_id=ANY(%s)",
                            (batch_id, [p["payment_id"] for p in payments]),
                        )
                        grouped = await rows(
                            conn,
                            "SELECT p.revenue_code,r.gl_code,sum(p.amount) amount FROM payment p JOIN revenue_type r USING(revenue_code) WHERE batch_id=%s GROUP BY p.revenue_code,r.gl_code ORDER BY p.revenue_code",
                            (batch_id,),
                        )
                        total = sum((g["amount"] for g in grouped), Decimal(0))
                        lines = [
                            {
                                "gl_code": CONFIG["collection_gl"],
                                "debit": str(total),
                                "credit": "0",
                            }
                        ] + [
                            {
                                "gl_code": g["gl_code"],
                                "debit": "0",
                                "credit": str(g["amount"]),
                            }
                            for g in grouped
                        ]
                        validate_journal(lines)
                        for line in lines:
                            await conn.execute(
                                "INSERT INTO fmis_batch_line(batch_id,gl_code,debit,credit) VALUES(%s,%s,%s,%s)",
                                (
                                    batch_id,
                                    line["gl_code"],
                                    Decimal(line["debit"]),
                                    Decimal(line["credit"]),
                                ),
                            )
                        batch = await one(
                            conn,
                            "SELECT * FROM fmis_batch WHERE batch_id=%s",
                            (batch_id,),
                        )
                    lines = await rows(
                        conn,
                        "SELECT gl_code,debit,credit FROM fmis_batch_line WHERE batch_id=%s ORDER BY id",
                        (batch["batch_id"],),
                    )
                    validate_journal(lines)
                body = {
                    "batch_id": str(batch["batch_id"]),
                    "business_date": str(day),
                    "currency": "USD",
                    "lines": json.loads(json.dumps(lines, default=str)),
                }
                error = "maximum attempts exhausted"
                for attempt in range(batch["attempts"] + 1, 4):
                    async with conn.transaction():
                        await conn.execute(
                            "UPDATE fmis_batch SET attempts=%s WHERE batch_id=%s",
                            (attempt, batch["batch_id"]),
                        )
                    try:
                        response = await self.client.post(
                            required("FMIS_URL") + "/journals",
                            json=body,
                            headers={
                                "Idempotency-Key": str(batch["batch_id"]),
                                "X-FMIS-Key": required("FMIS_API_KEY"),
                            },
                            timeout=3,
                        )
                        if response.is_success:
                            ref = response.json()["reference"]
                            async with conn.transaction():
                                await conn.execute(
                                    "UPDATE fmis_batch SET status='POSTED',reference=%s,error=NULL WHERE batch_id=%s",
                                    (ref, batch["batch_id"]),
                                )
                                await conn.execute(
                                    "UPDATE payment SET fmis_status='POSTED' WHERE batch_id=%s",
                                    (batch["batch_id"],),
                                )
                            return {
                                "status": "POSTED",
                                "batch_id": str(batch["batch_id"]),
                                "reference": ref,
                                "attempts": attempt,
                            }
                        error = f"HTTP {response.status_code}"
                        if not transient(response.status_code):
                            break
                    except (httpx.TimeoutException, httpx.NetworkError):
                        error = "network failure or ambiguous timeout"
                    log.warning(
                        "fmis_attempt_failed",
                        extra={
                            "batch_id": str(batch["batch_id"]),
                            "attempt": attempt,
                            "reason": error,
                        },
                    )
                    if attempt < 3:
                        await self.sleep(2 ** (attempt - 1))
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE fmis_batch SET status='FAILED',error=%s WHERE batch_id=%s",
                        (error, batch["batch_id"]),
                    )
                    await conn.execute(
                        "UPDATE payment SET fmis_status='FAILED' WHERE batch_id=%s",
                        (batch["batch_id"],),
                    )
                return {
                    "status": "FAILED",
                    "batch_id": str(batch["batch_id"]),
                    "reason": error,
                    "manual_review": True,
                }
            finally:
                await conn.execute("SELECT pg_advisory_unlock(87002)")
                await conn.commit()

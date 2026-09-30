"""Bounded async workers; PostgreSQL owns financial uniqueness."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, ValidationError
from psycopg.types.json import Jsonb
from .db import one
from .settings import CONFIG

log = logging.getLogger("ircub.payments")


class PaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payer_id: int
    revenue_code: str
    assessment_id: int | None = None
    amount: Decimal
    currency: str = "USD"
    channel: str
    external_ref: str


class PaymentProcessor:
    def __init__(self, pool):
        self.pool = pool
        self.queue = asyncio.Queue(maxsize=CONFIG["queue_capacity"])
        self.workers = []

    async def start(self):
        self.workers = [
            asyncio.create_task(self.worker()) for _ in range(CONFIG["workers"])
        ]

    async def close(self):
        await self.queue.join()
        for task in self.workers:
            task.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)

    async def worker(self):
        while True:
            payload, key, index, future = await self.queue.get()
            try:
                result = await self.process(payload, key, index)
                if not future.done():
                    future.set_result(result)
            except Exception as exc:
                log.exception("payment_worker_failure")
                if not future.done():
                    future.set_exception(exc)
            finally:
                self.queue.task_done()

    async def submit(self, payload, key, index):
        future = asyncio.get_running_loop().create_future()
        await self.queue.put((payload, key, index, future))
        return await asyncio.shield(future)

    async def reject(self, conn, payload, reasons):
        await conn.execute(
            "INSERT INTO failed_payment(payload,reasons) VALUES(%s,%s)",
            (
                Jsonb(payload, dumps=lambda value: json.dumps(value, default=str)),
                "; ".join(reasons),
            ),
        )
        log.warning("payment_rejected", extra={"reasons": reasons})
        return {
            "status": "REJECTED",
            "external_ref": str(payload.get("external_ref", "")),
            "reasons": reasons,
        }

    async def process(self, payload, key, index):
        async with self.pool.connection() as conn, conn.transaction():
            old = await one(
                conn,
                "SELECT result FROM payment_processing_log WHERE request_key=%s AND item_index=%s",
                (key, index),
            )
            if old:
                return old["result"]
            result = await self.process_item(conn, payload)
            await conn.execute(
                "INSERT INTO payment_processing_log(request_key,item_index,result) VALUES(%s,%s,%s)",
                (key, index, Jsonb(result)),
            )
            return result

    async def process_item(self, conn, payload):
        try:
            p = PaymentInput.model_validate(payload)
        except ValidationError as exc:
            return await self.reject(
                conn,
                payload,
                [f"{'.'.join(map(str,e['loc']))}: {e['msg']}" for e in exc.errors()],
            )
        reasons = []
        if (
            not p.amount.is_finite()
            or p.amount <= 0
            or p.amount > Decimal("9999999999999999.99")
            or p.amount != p.amount.quantize(Decimal(".01"))
        ):
            reasons.append("amount must be positive with at most two decimal places")
        if p.currency != "USD":
            reasons.append("only USD supported in this demonstration")
        if p.channel not in ("BANK", "MOBILE_MONEY", "CASH"):
            reasons.append("invalid channel")
        if not p.external_ref.strip() or len(p.external_ref.strip()) > 100:
            reasons.append("external reference must contain 1–100 characters")
        if not await one(
            conn, "SELECT payer_id FROM payer WHERE payer_id=%s", (p.payer_id,)
        ):
            reasons.append("payer does not exist")
        revenue = await one(
            conn,
            "SELECT is_active FROM revenue_type WHERE revenue_code=%s FOR SHARE",
            (p.revenue_code,),
        )
        if not revenue or not revenue["is_active"]:
            reasons.append("revenue code invalid or inactive")
        if p.assessment_id is not None:
            a = await one(
                conn,
                "SELECT * FROM assessment WHERE assessment_id=%s FOR UPDATE",
                (p.assessment_id,),
            )
            if (
                not a
                or a["payer_id"] != p.payer_id
                or a["revenue_code"] != p.revenue_code
            ):
                reasons.append("assessment does not belong to payer/revenue")
            elif not reasons:
                paid = await one(
                    conn,
                    "SELECT coalesce(sum(amount),0) total FROM payment WHERE assessment_id=%s",
                    (p.assessment_id,),
                )
                if p.amount > a["amount_due"] - paid["total"]:
                    reasons.append("payment exceeds outstanding principal")
        if reasons:
            return await self.reject(conn, payload, reasons)
        payment_id = uuid4()
        inserted = await one(
            conn,
            """INSERT INTO payment(payment_id,payer_id,assessment_id,revenue_code,amount,currency,channel,external_ref,paid_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(external_ref) DO NOTHING RETURNING payment_id""",
            (
                payment_id,
                p.payer_id,
                p.assessment_id,
                p.revenue_code,
                p.amount,
                p.currency,
                p.channel,
                p.external_ref.strip(),
                datetime.now(timezone.utc),
            ),
        )
        if not inserted:
            return await self.reject(conn, payload, ["duplicate external reference"])
        if p.assessment_id is not None:
            await conn.execute(
                """UPDATE assessment SET status=CASE WHEN (SELECT sum(amount) FROM payment WHERE assessment_id=%s)>=amount_due THEN 'PAID' ELSE 'PART_PAID' END WHERE assessment_id=%s""",
                (p.assessment_id, p.assessment_id),
            )
        log.info(
            "payment_written_in_transaction", extra={"payment_id": str(payment_id)}
        )
        return {
            "status": "ACCEPTED",
            "payment_id": str(payment_id),
            "external_ref": p.external_ref.strip(),
            "amount": str(p.amount),
            "reasons": [],
        }

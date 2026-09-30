import asyncio
import hashlib
import hmac
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from psycopg.types.json import Jsonb
from .db import create_pool, one, rows
from .settings import required
from .fmis_service import validate_journal


@asynccontextmanager
async def lifespan(app):
    app.state.pool = create_pool()
    await app.state.pool.open(wait=True)
    yield
    await app.state.pool.close()


app = FastAPI(title="IRCUB Mock FMIS", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/journals")
async def journal(request: Request):
    if not hmac.compare_digest(
        request.headers.get("X-FMIS-Key", ""), required("FMIS_API_KEY")
    ):
        raise HTTPException(401, "invalid FMIS credential")
    body = await request.json()
    if request.headers.get("Idempotency-Key") != body.get("batch_id"):
        raise HTTPException(400, "batch/key mismatch")
    try:
        validate_journal(body["lines"])
    except (ValueError, KeyError):
        raise HTTPException(422, "unbalanced or invalid journal")
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    mode = os.getenv("MOCK_FMIS_MODE", "normal")
    if mode == "permanent":
        raise HTTPException(422, "simulated permanent rejection")
    if mode == "transient":
        raise HTTPException(503, "simulated unavailable")
    async with app.state.pool.connection() as conn, conn.transaction():
        ref = "FMIS-" + body["batch_id"]
        inserted = await one(
            conn,
            "INSERT INTO mock_fmis_journal(batch_id,body_hash,reference,journal) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING reference",
            (body["batch_id"], digest, ref, Jsonb(body)),
        )
        old = await one(
            conn,
            "SELECT * FROM mock_fmis_journal WHERE batch_id=%s",
            (body["batch_id"],),
        )
        if old["body_hash"] != digest:
            raise HTTPException(409, "same batch with changed journal")
    # Accepted journal committed, first response delayed beyond client timeout.
    if mode == "accept-timeout" and inserted:
        await asyncio.sleep(4)
    return {"reference": old["reference"]}


@app.get("/journals")
async def journals(request: Request):
    if not hmac.compare_digest(
        request.headers.get("X-FMIS-Key", ""), required("FMIS_API_KEY")
    ):
        raise HTTPException(401, "invalid FMIS credential")
    async with app.state.pool.connection() as conn:
        return await rows(conn, "SELECT * FROM mock_fmis_journal ORDER BY created_at")

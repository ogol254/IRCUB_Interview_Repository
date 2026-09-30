"""Live HTTP checks against the local demonstration; creates synthetic collections."""

import hashlib, hmac, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.env import load

load()
import httpx

base = "http://127.0.0.1:8000"
officer = {"X-Officer-Key": os.environ["OFFICER_API_KEY"]}


def get(path):
    response = httpx.get(base + path, headers=officer, timeout=15)
    response.raise_for_status()
    return response.json()


def post(path, **kwargs):
    response = httpx.post(base + path, timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


def row(ref):
    return {
        "payer_id": 1,
        "revenue_code": "WATER",
        "amount": "1.25",
        "channel": "MOBILE_MONEY",
        "external_ref": ref,
    }


def signed(raw, key):
    ts = str(int(time.time()))
    return {
        "Content-Type": "application/json",
        "X-Timestamp": ts,
        "X-Signature": hmac.new(
            os.environ["CALLBACK_SECRET"].encode(),
            ts.encode() + b"." + raw,
            hashlib.sha256,
        ).hexdigest(),
        "Idempotency-Key": key,
    }


def check(name, condition):
    assert condition, name
    print("PASS:", name)


report = "/api/v1/reports/quarterly?start=2026-01-01&end=2027-01-01"
if "--redis-down" in sys.argv:
    check(
        "live Redis outage returns database report", get(report)["source"] == "database"
    )
    sys.exit()
check("backend health", get("/health")["status"] == "ok")
check("Swagger", httpx.get(base + "/docs").status_code == 200)
check("OpenAPI", "/api/v1/payments/callback" in get("/openapi.json")["paths"])
check("mock health", httpx.get("http://127.0.0.1:8001/health").json()["status"] == "ok")
check("payer search", get("/api/v1/payers?q=WA-001")[0]["tin"] == "TEST-001")
reference = "SMOKE-" + uuid4().hex
raw = json.dumps(row(reference)).encode()
key = uuid4().hex
headers = signed(raw, key)
first = post("/api/v1/payments/callback", content=raw, headers=headers)
check("signed callback committed", first["accepted"] == 1)
check(
    "duplicate callback returns identical receipt",
    post("/api/v1/payments/callback", content=raw, headers=headers) == first,
)
check(
    "payment lookup",
    get("/api/v1/payments/" + first["results"][0]["payment_id"])["external_ref"]
    == reference,
)
bad = {**headers, "X-Signature": "bad"}
check(
    "forged HMAC rejected",
    httpx.post(base + "/api/v1/payments/callback", content=raw, headers=bad).status_code
    == 401,
)
check(
    "replay under another key rejected",
    httpx.post(
        base + "/api/v1/payments/callback",
        content=raw,
        headers={**headers, "Idempotency-Key": uuid4().hex},
    ).status_code
    == 409,
)
before = get(report)
check("cache population and hit", get(report)["source"] == "cache")
reference = "RACE-" + uuid4().hex


def duplicate(_):
    return post(
        "/api/v1/payments/bulk",
        json=[row(reference)],
        headers={**officer, "Idempotency-Key": uuid4().hex},
    )


with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(duplicate, range(8)))
check(
    "concurrent duplicate financial effect once",
    sum(r["accepted"] for r in results) == 1
    and sum(r["rejected"] for r in results) == 7,
)
after = get(report)
check(
    "cache invalidation after commit",
    after["version"] > before["version"] and after["source"] == "database",
)
day = datetime.now(timezone.utc).date().isoformat()
batch = post("/api/v1/fmis/post?day=" + day, headers=officer)
check("live FMIS posting", batch["status"] == "POSTED")
journals = httpx.get(
    "http://127.0.0.1:8001/journals", headers={"X-FMIS-Key": os.environ["FMIS_API_KEY"]}
).json()
check(
    "mock contains one journal for batch",
    sum(j["batch_id"] == batch["batch_id"] for j in journals) == 1,
)
check(
    "second daily post cannot repost payments",
    post("/api/v1/fmis/post?day=" + day, headers=officer)["status"] == "EMPTY",
)
if "--accept-timeout" in sys.argv:
    check("real accepted-timeout recovers in two attempts", batch["attempts"] == 2)
print("Live checks complete; only unique synthetic demonstration payments were added.")

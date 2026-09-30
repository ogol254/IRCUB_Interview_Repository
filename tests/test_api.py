import hashlib, hmac, json, os, time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest

pytestmark = pytest.mark.integration


def payload(ref=None, **kwargs):
    return dict(
        payer_id=1,
        revenue_code="WATER",
        amount="10.00",
        channel="MOBILE_MONEY",
        external_ref=ref or uuid4().hex,
        **kwargs
    )


def officer(key=None):
    return {
        "X-Officer-Key": os.environ["OFFICER_API_KEY"],
        "Idempotency-Key": key or uuid4().hex,
    }


def signed(body, key=None, ts=None):
    timestamp = str(ts or int(time.time()))
    return {
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-Signature": hmac.new(
            os.environ["CALLBACK_SECRET"].encode(),
            timestamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest(),
        "Idempotency-Key": key or uuid4().hex,
    }


def test_health_openapi_and_registry(client):
    assert client.get("/health").json()["database"] == "ok"
    assert client.get("/docs").status_code == 200
    assert "/api/v1/payments/callback" in client.get("/openapi.json").json()["paths"]
    assert (
        client.get("/api/v1/payers?q=WA-001", headers=officer()).json()[0]["tin"]
        == "TEST-001"
    )
    assert client.get("/api/v1/revenues", headers=officer()).status_code == 200
    assert client.get("/api/v1/revenues").status_code == 401
    estimate = client.post(
        "/api/v1/water/calculate",
        json={"estimate": True, "meter_no": "M-001"},
        headers=officer(),
    )
    assert estimate.status_code == 200 and float(estimate.json()["amount"]) == 1450


def test_callback_duplicate_and_changed_payload(client):
    body = json.dumps(payload()).encode()
    headers = signed(body)
    first = client.post("/api/v1/payments/callback", content=body, headers=headers)
    assert first.status_code == 200 and first.json()["accepted"] == 1
    assert (
        client.post("/api/v1/payments/callback", content=body, headers=headers).json()
        == first.json()
    )
    changed = json.dumps(payload()).encode()
    assert (
        client.post(
            "/api/v1/payments/callback",
            content=changed,
            headers=signed(changed, headers["Idempotency-Key"]),
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/payments/callback",
            content=body,
            headers={**headers, "Idempotency-Key": uuid4().hex},
        ).status_code
        == 409
    )


def test_bad_hmac_stale_and_json(client):
    body = json.dumps(payload()).encode()
    headers = signed(body)
    headers["X-Signature"] = "bad"
    assert (
        client.post(
            "/api/v1/payments/callback", content=body, headers=headers
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/payments/callback",
            content=body,
            headers=signed(body, ts=int(time.time()) - 600),
        ).status_code
        == 401
    )
    body = b"broken"
    assert (
        client.post(
            "/api/v1/payments/callback", content=body, headers=signed(body)
        ).status_code
        == 400
    )


def test_bulk_validation_and_separate_failures(client, database):
    import psycopg

    items = [
        payload(),
        {**payload(), "amount": "0", "payer_id": 999, "revenue_code": "RETIRED"},
        payload("SEED-1"),
        {**payload(), "amount": "1.001"},
    ]
    response = client.post(
        "/api/v1/payments/bulk", json=items, headers=officer()
    ).json()
    assert response["accepted"] == 1 and response["rejected"] == 3
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM failed_payment").fetchone()[0] == 3
    id = response["results"][0]["payment_id"]
    assert (
        client.get("/api/v1/payments/" + id, headers=officer()).json()["external_ref"]
        == items[0]["external_ref"]
    )


def test_concurrent_duplicates(client, database):
    import psycopg

    with ThreadPoolExecutor(max_workers=12) as executor:
        responses = list(
            executor.map(
                lambda _: client.post(
                    "/api/v1/payments/bulk",
                    json=[payload("CONCURRENT")],
                    headers=officer(),
                ).json(),
                range(20),
            )
        )
    assert (
        sum(r["accepted"] for r in responses) == 1
        and sum(r["rejected"] for r in responses) == 19
    )
    with psycopg.connect(database) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM payment WHERE external_ref='CONCURRENT'"
            ).fetchone()[0]
            == 1
        )


def test_concurrent_same_request_returns_receipt(client):
    headers = officer()
    item = payload()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: client.post(
                    "/api/v1/payments/bulk", json=[item], headers=headers
                ).json(),
                range(8),
            )
        )
    assert (
        all(result == results[0] for result in results) and results[0]["accepted"] == 1
    )


def test_partial_allocation_and_overpayment(client, database):
    import psycopg

    assert (
        client.post(
            "/api/v1/payments/bulk", json=[payload(assessment_id=1)], headers=officer()
        ).json()["accepted"]
        == 1
    )
    over = {**payload(assessment_id=1), "amount": "1000"}
    assert (
        client.post("/api/v1/payments/bulk", json=[over], headers=officer()).json()[
            "rejected"
        ]
        == 1
    )
    with psycopg.connect(database) as conn:
        assert (
            conn.execute(
                "SELECT status FROM assessment WHERE assessment_id=1"
            ).fetchone()[0]
            == "PART_PAID"
        )


def test_numeric_json_money_preserves_cents(client, database):
    import psycopg

    raw = b'[{"payer_id":1,"revenue_code":"WATER","amount":9007199254740992.01,"channel":"BANK","external_ref":"PRECISION"}]'
    result = client.post(
        "/api/v1/payments/bulk",
        content=raw,
        headers={**officer(), "Content-Type": "application/json"},
    ).json()
    assert result["accepted"] == 1
    id = result["results"][0]["payment_id"]
    assert (
        client.get("/api/v1/payments/" + id, headers=officer()).json()["amount"]
        == "9007199254740992.01"
    )


def test_lost_coordinator_response_reuses_committed_item_results(client, database):
    import psycopg

    key = "RECOVERY"
    headers = officer(key)
    items = [payload(), payload()]
    first = client.post("/api/v1/payments/bulk", json=items, headers=headers).json()
    with psycopg.connect(database) as conn:
        conn.execute(
            "UPDATE idempotency_record SET response=NULL WHERE key='officer:RECOVERY'"
        )
    second = client.post("/api/v1/payments/bulk", json=items, headers=headers).json()
    assert first == second and second["accepted"] == 2
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM payment").fetchone()[0] == 4
        assert conn.execute("SELECT count(*) FROM failed_payment").fetchone()[0] == 0

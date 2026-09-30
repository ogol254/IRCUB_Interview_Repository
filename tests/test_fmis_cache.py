import asyncio, json, os
import httpx
import pytest
import psycopg
from section_01_technical.backend.fmis_service import (
    FmisPostingService,
    validate_journal,
    transient,
)


@pytest.mark.parametrize(
    "status,expected",
    [
        (408, True),
        (429, True),
        (500, True),
        (400, False),
        (401, False),
        (403, False),
        (422, False),
    ],
)
def test_retry_classification(status, expected):
    assert transient(status) == expected


def test_unbalanced_rejected():
    with pytest.raises(ValueError):
        validate_journal([{"gl_code": "1000", "debit": "10", "credit": "0"}])


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1.001"])
def test_invalid_journal_amount(value):
    with pytest.raises(ValueError):
        validate_journal(
            [
                {"gl_code": "1000", "debit": value, "credit": "0"},
                {"gl_code": "4100", "debit": "0", "credit": value},
            ]
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    "status,attempts,final",
    [(503, 3, "FAILED"), (422, 1, "FAILED"), (200, 1, "POSTED")],
)
async def test_fmis_persistence_retry(database, monkeypatch, status, attempts, final):
    from section_01_technical.backend.db import create_pool

    monkeypatch.setenv("FMIS_URL", "http://fmis")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"reference": "MOCK-1"})

    pool = create_pool()
    await pool.open(wait=True)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = FmisPostingService(pool, client, sleep=lambda _: asyncio.sleep(0))
        result = await service.post_day("2026-01-15")
        assert result["status"] == final and len(calls) == attempts
        assert (await service.post_day("2026-01-15"))["status"] == "EMPTY"
    await pool.close()
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT status,attempts FROM fmis_batch").fetchone() == (
            final,
            attempts,
        )


@pytest.mark.integration
async def test_ambiguous_timeout_same_journal(database, monkeypatch):
    from section_01_technical.backend.db import create_pool

    monkeypatch.setenv("FMIS_URL", "http://fmis")
    requests = []
    journals = {}

    def handler(request):
        body = json.loads(request.content)
        key = request.headers["Idempotency-Key"]
        requests.append(key)
        journals.setdefault(key, body)
        if len(requests) == 1:
            raise httpx.ReadTimeout("accepted but response lost", request=request)
        assert journals[key] == body
        return httpx.Response(200, json={"reference": "ONCE"})

    pool = create_pool()
    await pool.open(wait=True)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await FmisPostingService(
            pool, client, sleep=lambda _: asyncio.sleep(0)
        ).post_day("2026-01-15")
        assert (
            result["attempts"] == 2
            and len(journals) == 1
            and result["status"] == "POSTED"
        )
    await pool.close()


@pytest.mark.integration
def test_redis_cache_hit_invalidation(client):
    from tests.test_api import officer, payload

    path = "/api/v1/reports/quarterly?start=2026-01-01&end=2027-01-01"
    import redis

    cache = redis.Redis.from_url(os.environ["REDIS_URL"])
    for key in cache.scan_iter("ircub:summary:*"):
        cache.delete(key)
    first = client.get(path, headers=officer()).json()
    assert first["source"] == "database"
    assert client.get(path, headers=officer()).json()["source"] == "cache"
    assert (
        client.post(
            "/api/v1/payments/bulk", json=[payload()], headers=officer()
        ).json()["accepted"]
        == 1
    )
    second = client.get(path, headers=officer()).json()
    assert second["source"] == "database" and second["version"] > first["version"]


@pytest.mark.integration
async def test_cache_redis_failure(database):
    from redis.exceptions import ConnectionError
    from section_01_technical.backend.db import create_pool
    from section_01_technical.backend.cache import SummaryCache

    class Broken:
        async def get(self, *args):
            raise ConnectionError()

        async def set(self, *args, **kwargs):
            raise ConnectionError()

    pool = create_pool()
    await pool.open(wait=True)
    result = await SummaryCache(pool, Broken()).summary("2026-01-01", "2027-01-01")
    assert result["source"] == "database" and len(result["rows"]) == 12
    await pool.close()

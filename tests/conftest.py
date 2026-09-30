import os
from pathlib import Path
from uuid import uuid4
import pytest
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def database(monkeypatch):
    import psycopg
    from scripts.env import load

    load()
    url = os.environ["DATABASE_URL"]
    name = "ircub_test_" + uuid4().hex
    try:
        admin = psycopg.connect(url, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError:
        pytest.fail("PostgreSQL unavailable: start docker compose up -d postgres redis")
    from psycopg import sql

    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    test_url = url.rsplit("/", 1)[0] + "/" + name
    with psycopg.connect(test_url, autocommit=True) as conn:
        for file in sorted(
            Path("section_01_technical/database/migrations").glob("*.sql")
        ):
            conn.execute(file.read_text())
        conn.execute(
            Path("section_01_technical/database/seed/001_demo.sql").read_text()
        )
    monkeypatch.setenv("DATABASE_URL", test_url)
    yield test_url
    admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    admin.close()


@pytest.fixture
def client(database):
    from fastapi.testclient import TestClient
    from section_01_technical.backend.payment_api import app

    with TestClient(app) as client:
        yield client

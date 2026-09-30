from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import psycopg
import pytest

pytestmark = pytest.mark.integration


def test_quarters_zero_share_running_and_financial_year(database):
    with psycopg.connect(database) as conn:
        result = conn.execute(
            "SELECT * FROM quarterly_collections('2026-01-01','2027-01-01') WHERE revenue_code='WATER'"
        ).fetchall()
        assert len(result) == 4 and result[0][3] == 300 and result[3][4] == 300
        assert result[0][5] == 100 and result[1][5] == 0
        shifted = conn.execute(
            "SELECT quarter_total FROM quarterly_collections('2025-07-01','2026-07-01') WHERE revenue_code='WATER' ORDER BY quarter_no"
        ).fetchall()
        assert [r[0] for r in shifted] == [0, 0, 300, 0]


def test_multiple_payments_multiple_accounts(database):
    with psycopg.connect(database) as conn:
        result = conn.execute(
            "SELECT * FROM collection_efficiency('2026-09-30T23:59:59Z') ORDER BY tariff_class"
        ).fetchall()
        assert result[0][0] == "COMMERCIAL" and result[0][2:] == (2000, 0, Decimal("0"))
        assert result[1][0] == "DOMESTIC" and result[1][2:] == (
            1000,
            300,
            Decimal("30"),
        )
        assert conn.execute("SELECT * FROM water_arrears('2026-09-30')").fetchall() == [
            ("WA-002", 1, Decimal(2000)),
            ("WA-001", 1, Decimal(700)),
        ]


@pytest.mark.parametrize(
    "run,expected",
    [
        ("2026-01-31", 0),
        ("2026-02-01", 0),
        ("2026-02-02", 45),
        ("2026-03-01", 35),
        ("2026-05-01", 105),
        ("2026-06-01", 175),
        ("2028-02-01", 1000),
    ],
)
def test_penalty_cases(database, run, expected):
    with psycopg.connect(database) as conn:
        conn.execute("CALL apply_overdue_penalties(%s)", (run,))
        assert (
            conn.execute(
                "SELECT penalty_amount FROM assessment WHERE assessment_id=1"
            ).fetchone()[0]
            == expected
        )


def test_penalty_concurrent_idempotency(database):
    def call(_):
        with psycopg.connect(database) as conn:
            conn.execute("CALL apply_overdue_penalties('2026-06-01')")

    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(call, range(5)))
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM penalty_history").fetchone()[0] == 3
        assert (
            conn.execute(
                "SELECT penalty_amount FROM assessment WHERE assessment_id=1"
            ).fetchone()[0]
            == 175
        )


def test_penalty_database_rollback(database):
    with psycopg.connect(database) as conn:
        conn.execute("CALL apply_overdue_penalties('2026-06-01')")
        conn.rollback()
        assert conn.execute("SELECT count(*) FROM penalty_history").fetchone()[0] == 0

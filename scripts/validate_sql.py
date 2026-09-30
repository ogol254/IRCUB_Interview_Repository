"""Execute interview queries and EXPLAIN against PostgreSQL; rollback penalties."""

from pathlib import Path
import sys, os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.env import load

load()
import psycopg

with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
    for name in ("q1_quarterly.sql", "q2_efficiency.sql", "reconciliation.sql"):
        cur = conn.execute(
            (Path("section_01_technical/database/queries") / name).read_text()
        )
        counts = []
        while True:
            if cur.description:
                counts.append(len(cur.fetchall()))
            if not cur.nextset():
                break
        print("PASS:", name, "result row counts", counts)
    conn.execute("CALL apply_overdue_penalties('2026-09-30')")
    first = conn.execute("SELECT count(*) FROM penalty_history").fetchone()[0]
    conn.execute("CALL apply_overdue_penalties('2026-09-30')")
    second = conn.execute("SELECT count(*) FROM penalty_history").fetchone()[0]
    assert first == second
    print("PASS: penalty same-day history counts", first, second, "(will roll back)")
    plan = conn.execute(
        "EXPLAIN (ANALYZE,BUFFERS) SELECT revenue_code,sum(amount) FROM payment WHERE paid_at>='2026-01-01T00:00:00Z' AND paid_at<'2027-01-01T00:00:00Z' GROUP BY revenue_code"
    ).fetchall()
    Path("docs/query-plan.txt").write_text("\n".join(row[0] for row in plan) + "\n")
    print("PASS: EXPLAIN ANALYZE saved; small synthetic data only")
    conn.rollback()

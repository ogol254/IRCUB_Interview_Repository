from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from .settings import required


def create_pool():
    return AsyncConnectionPool(
        required("DATABASE_URL"),
        min_size=1,
        max_size=12,
        open=False,
        kwargs={"row_factory": dict_row, "connect_timeout": 5},
    )


async def rows(conn, sql, params=()):
    return await (await conn.execute(sql, params)).fetchall()


async def one(conn, sql, params=()):
    return await (await conn.execute(sql, params)).fetchone()

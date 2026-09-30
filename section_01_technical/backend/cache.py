import json
import logging
from redis.exceptions import RedisError
from .db import one, rows
from .settings import CONFIG

log = logging.getLogger("ircub.cache")


class SummaryCache:
    def __init__(self, pool, redis):
        self.pool, self.redis = pool, redis

    async def summary(self, start, end):
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            state = await one(
                conn,
                "SELECT version,current_database() namespace FROM report_version WHERE id=1",
            )
            version = state["version"]
            key = f"ircub:summary:{state['namespace']}:v{version}:USD:{start}:{end}"
            try:
                cached = await self.redis.get(key)
                if cached:
                    return {
                        "source": "cache",
                        "version": version,
                        "rows": json.loads(cached),
                    }
            except (RedisError, OSError):
                log.warning("redis_read_unavailable")
            data = await rows(
                conn, "SELECT * FROM quarterly_collections(%s,%s)", (start, end)
            )
        data = json.loads(json.dumps(data, default=str))
        try:
            await self.redis.set(key, json.dumps(data), ex=CONFIG["report_ttl"])
        except (RedisError, OSError):
            log.warning("redis_write_unavailable")
        return {"source": "database", "version": version, "rows": data}

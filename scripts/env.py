from pathlib import Path
import os


def load():
    for line in Path(".env").read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key, value)
    os.environ.setdefault(
        "DATABASE_URL",
        f"postgresql://ircub:{os.environ['POSTGRES_PASSWORD']}@127.0.0.1:5432/ircub",
    )
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
    os.environ.setdefault("FMIS_URL", "http://127.0.0.1:8001")

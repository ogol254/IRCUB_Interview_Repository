import json
import os
from pathlib import Path

CONFIG = json.loads(Path(__file__).with_name("config.json").read_text())


def required(name):
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError(f"{name} must be supplied in the environment")
    return value

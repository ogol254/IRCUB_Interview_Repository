import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.env import load

load()
import uvicorn

uvicorn.run(
    (
        "section_01_technical.backend.mock_fmis:app"
        if "--fmis" in sys.argv
        else "section_01_technical.backend.payment_api:app"
    ),
    host="127.0.0.1",
    port=8001 if "--fmis" in sys.argv else 8000,
)

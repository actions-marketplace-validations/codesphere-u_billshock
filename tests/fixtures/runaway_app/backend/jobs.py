import openai
import requests
from fastapi import APIRouter
from sqlalchemy import create_engine

router = APIRouter()
CACHE: dict[str, object] = {}


@router.post("/batch")
def run_batch(prompts: list[str]):
    # BILL012: database engine instantiated inside endpoint
    engine = create_engine("postgresql://localhost/app")
    with engine.connect() as conn:
        # BILL007: unbounded full-table SQL scan
        conn.execute("SELECT * FROM events")

    # BILL004 / BILL003: paid LLM call inside unbounded loop with no max_tokens
    for prompt in prompts:
        res = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
        )
        # BILL013: mutating module-level collection with no size cap
        CACHE[prompt] = res

    # BILL010: outbound HTTP call without timeout
    requests.get("https://metrics.example.com/ping")

    # BILL009: infinite retry loop hitting external service
    while True:
        requests.post("https://queue.example.com/drain", timeout=2.0)

    return {"cached": len(CACHE)}

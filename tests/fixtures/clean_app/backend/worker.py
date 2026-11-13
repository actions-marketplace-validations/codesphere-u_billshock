import threading
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import create_engine, text

router = APIRouter()
stop_event = threading.Event()


@lru_cache(maxsize=256)
def get_engine():
    return create_engine("postgresql://localhost/app")


def get_current_user():
    return {"id": "user_1"}


@router.get("/orders")
def list_orders(user: Annotated[dict[str, str], Depends(get_current_user)]):
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, total FROM orders WHERE user_id = :uid LIMIT 50"),
            {"uid": user["id"]},
        )
        return [dict(r._mapping) for r in rows]


def check_upstream_health() -> bool:
    for _ in range(3):
        resp = httpx.get("https://status.example.com/health", timeout=5.0)
        if resp.status_code == 200:
            return True
    return False


def poll_until_stopped() -> None:
    while not stop_event.is_set():
        httpx.get("https://status.example.com/heartbeat", timeout=2.0)
        stop_event.wait(30.0)

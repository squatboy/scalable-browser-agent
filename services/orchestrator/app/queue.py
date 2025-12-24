from __future__ import annotations
import json
import os
import redis
from typing import Any, Dict

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_KEY = os.getenv("STREAM_KEY", "agent-jobs")


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def enqueue(job_id: str, agent_id: str, payload: Dict[str, Any]) -> str:
    r = get_redis()
    msg_id = r.xadd(
        STREAM_KEY,
        {
            "job_id": job_id,
            "agent_id": agent_id,
            "payload": json.dumps(payload),
        },
        maxlen=10000,
        approximate=True,
    )

    return msg_id

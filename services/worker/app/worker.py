from __future__ import annotations

import asyncio
import json
import os
import traceback
import redis

from .agent_loader import load_agent_module
from .storage import update_job_running, update_job_succeeded, update_job_failed

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_KEY = os.getenv("STREAM_KEY", "agent-jobs")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "workers")
CONSUMER_NAME = os.getenv("CONSUMER_NAME", "worker-1")


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def ensure_group(r: redis.Redis) -> None:
    try:
        r.xgroup_create(
            name=STREAM_KEY, groupname=CONSUMER_GROUP, id="$", mkstream=True
        )
    except redis.ResponseError as e:
        # BUSYGROUP means it already exists
        if "BUSYGROUP" not in str(e):
            raise


async def run_one(agent_id: str, job_id: str, payload: dict) -> dict:
    mod = load_agent_module(agent_id)
    if not hasattr(mod, "run"):
        raise RuntimeError(
            f"agent '{agent_id}' has no async run(payload, ctx) function"
        )

    ctx = {"job_id": job_id, "agent_id": agent_id}
    fn = getattr(mod, "run")

    # run()이 async 함수라고 가정 (계약)
    result = await fn(payload, ctx)
    if not isinstance(result, dict):
        raise RuntimeError("agent.run must return a dict(JSON-serializable)")
    return result


async def main():
    r = get_redis()
    ensure_group(r)

    print(
        f"[worker] listening stream={STREAM_KEY}, group={CONSUMER_GROUP}, consumer={CONSUMER_NAME}"
    )

    while True:
        resp = r.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=CONSUMER_NAME,
            streams={STREAM_KEY: ">"},
            count=1,
            block=5000,
        )

        if not resp:
            continue

        # resp format: [(stream, [(msg_id, {fields})])]
        _, messages = resp[0]
        msg_id, fields = messages[0]

        job_id = fields.get("job_id")
        agent_id = fields.get("agent_id")
        payload_raw = fields.get("payload", "{}")

        try:
            payload = json.loads(payload_raw)
        except Exception:
            payload = {}

        try:
            update_job_running(job_id)
            result = await run_one(agent_id, job_id, payload)
            update_job_succeeded(job_id, result)
            r.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)
            print(f"[worker] job {job_id} SUCCEEDED")
        except Exception as e:
            err = {
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
            update_job_failed(job_id, err)
            r.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)
            print(f"[worker] job {job_id} FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(main())

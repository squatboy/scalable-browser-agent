from __future__ import annotations

import asyncio
import json
import os
import traceback
import redis
import signal

import random

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
    # ---------------------------------------------------------
    # Special case for load testing (KEDA scaling)
    # ---------------------------------------------------------
    if agent_id == "mock-agent":
        delay = payload.get("delay")
        if delay is None:
            delay = random.uniform(20.0, 60.0)
        print(f"[worker] [mock-agent] starting job {job_id} with {delay:.2f}s delay")
        await asyncio.sleep(delay)
        return {
            "status": "success",
            "mock": True,
            "job_id": job_id,
            "slept_for": delay,
        }

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
    # Fail-fast: enforce single concurrency via env
    concurrency = os.getenv("WORKER_CONCURRENCY", "1")
    if str(concurrency) != "1":
        raise SystemExit("WORKER_CONCURRENCY must be 1 for safe operation")

    shutdown_event = asyncio.Event()

    def _handle_sigterm(*_args):
        # Stop pulling new jobs; allow in-flight job to complete
        shutdown_event.set()

    # Register graceful shutdown
    try:
        signal.signal(signal.SIGTERM, _handle_sigterm)
        signal.signal(signal.SIGINT, _handle_sigterm)
    except Exception:
        # Some environments may not allow signal setup; continue
        pass
    r = get_redis()
    ensure_group(r)

    print(
        f"[worker] listening stream={STREAM_KEY}, group={CONSUMER_GROUP}, consumer={CONSUMER_NAME}"
    )

    while not shutdown_event.is_set():
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

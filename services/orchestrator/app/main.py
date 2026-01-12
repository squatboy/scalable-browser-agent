from __future__ import annotations

import uuid
import logging
from fastapi import FastAPI, HTTPException, Request
from .contracts import RunAgentRequest, RunAgentResponse, JobResponse
from .storage import insert_job, get_job
from .queue import enqueue

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent Orchestrator", version="0.2.0")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/v1/run-agent", response_model=RunAgentResponse)
def run_agent(req: RunAgentRequest, request: Request):
    job_id = str(uuid.uuid4())
    agent_id = "browser-use-generic"
    payload = {"task": req.task}

    logger.info(
        "received run-agent request job_id=%s client_ip=%s",
        job_id,
        request.client.host if request.client else "unknown",
    )

    try:
        # 1) DB에 QUEUED로 저장
        insert_job(job_id=job_id, agent_id=agent_id, payload=payload)

        # 2) Redis Streams에 enqueue
        enqueue(job_id=job_id, agent_id=agent_id, payload=payload)

        logger.info("job enqueued job_id=%s agent_id=%s", job_id, agent_id)
    except Exception as e:
        logger.error("failed to enqueue job job_id=%s error=%s", job_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))

    return RunAgentResponse(job_id=job_id)


@app.post("/v1/test-agent", response_model=RunAgentResponse)
def run_test_agent(request: Request):
    """
    Load test endpoint that uses a mock agent (no body required).
    Simulates a 20s-60s task.
    """
    job_id = str(uuid.uuid4())
    agent_id = "mock-agent"
    payload = {"task": "load-test", "is_test": True}

    logger.info(
        "received test-agent request job_id=%s client_ip=%s",
        job_id,
        request.client.host if request.client else "unknown",
    )

    try:
        # 1) DB에 QUEUED로 저장
        insert_job(job_id=job_id, agent_id=agent_id, payload=payload)

        # 2) Redis Streams에 enqueue
        enqueue(job_id=job_id, agent_id=agent_id, payload=payload)

        logger.info("job enqueued job_id=%s agent_id=%s", job_id, agent_id)
    except Exception as e:
        logger.error("failed to enqueue job job_id=%s error=%s", job_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))

    return RunAgentResponse(job_id=job_id)


@app.get("/v1/jobs/{job_id}", response_model=JobResponse)
def read_job(job_id: str):
    row = get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="job_id not found")

    return JobResponse(
        job_id=row["job_id"],
        agent_id=row["agent_id"],
        status=row["status"],
        result=row.get("result"),
        error=row.get("error"),
    )

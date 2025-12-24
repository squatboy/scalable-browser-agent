from __future__ import annotations

import uuid
from fastapi import FastAPI, HTTPException
from .contracts import RunAgentRequest, RunAgentResponse, JobResponse
from .storage import insert_job, get_job
from .queue import enqueue

app = FastAPI(title="Agent Orchestrator", version="0.2.0")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/v1/run-agent", response_model=RunAgentResponse)
def run_agent(req: RunAgentRequest):
    job_id = str(uuid.uuid4())

    # 1) DB에 QUEUED로 저장
    insert_job(job_id=job_id, agent_id=req.agent_id, payload=req.payload)

    # 2) Redis Streams에 enqueue
    enqueue(job_id=job_id, agent_id=req.agent_id, payload=req.payload)

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

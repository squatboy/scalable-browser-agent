from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional, Dict

JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]


class RunAgentRequest(BaseModel):
    agent_id: str = Field(default="sample-echo", description="Which agent to run")
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary JSON payload passed to agent"
    )


class RunAgentResponse(BaseModel):
    job_id: str


class JobResponse(BaseModel):
    job_id: str
    agent_id: str
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

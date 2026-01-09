from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional, Dict

JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]


class RunAgentRequest(BaseModel):
    task: str = Field(..., description="The natural language task for the agent")


class RunAgentResponse(BaseModel):
    job_id: str


class JobResponse(BaseModel):
    job_id: str
    agent_id: str
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

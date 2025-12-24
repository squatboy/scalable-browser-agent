from __future__ import annotations
import json
import os
import psycopg
from psycopg.rows import dict_row
from typing import Any, Optional, Dict

DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def insert_job(job_id: str, agent_id: str, payload: Dict[str, Any]) -> None:
    payload_json = json.dumps(payload)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (job_id, agent_id, status, payload)
                VALUES (%s, %s, 'QUEUED', %s::jsonb)
                """,
                (job_id, agent_id, payload_json),
            )


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT job_id::text, agent_id, status, result, error FROM jobs WHERE job_id = %s",
                (job_id,),
            )
            row = cur.fetchone()
            return row


def update_job_running(job_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status='RUNNING', started_at=now(), updated_at=now()
                WHERE job_id=%s
                """,
                (job_id,),
            )


def update_job_succeeded(job_id: str, result: Dict[str, Any]) -> None:
    result_json = json.dumps(result)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status='SUCCEEDED', result=%s::jsonb, finished_at=now(), updated_at=now()
                WHERE job_id=%s
                """,
                (result_json, job_id),
            )


def update_job_failed(job_id: str, error: Dict[str, Any]) -> None:
    error_json = json.dumps(error)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status='FAILED', error=%s::jsonb, finished_at=now(), updated_at=now()
                WHERE job_id=%s
                """,
                (error_json, job_id),
            )

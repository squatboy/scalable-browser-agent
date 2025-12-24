from __future__ import annotations
import json
import os
import psycopg
from psycopg.rows import dict_row
from typing import Any, Dict

DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def update_job_running(job_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status='RUNNING', started_at=now(), updated_at=now() WHERE job_id=%s",
                (job_id,),
            )


def update_job_succeeded(job_id: str, result: Dict[str, Any]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status='SUCCEEDED', result=%s::jsonb, finished_at=now(), updated_at=now()
                WHERE job_id=%s
                """,
                (json.dumps(result), job_id),
            )


def update_job_failed(job_id: str, error: Dict[str, Any]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status='FAILED', error=%s::jsonb, finished_at=now(), updated_at=now()
                WHERE job_id=%s
                """,
                (json.dumps(error), job_id),
            )

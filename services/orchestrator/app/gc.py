from __future__ import annotations
import os
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL", "")
JOB_TIMEOUT_SECONDS = int(os.getenv("JOB_TIMEOUT_SECONDS", "1800"))  # 30m
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
QUEUED_EXPIRE_SECONDS = int(os.getenv("QUEUED_EXPIRE_SECONDS", "86400"))  # 24h


def run_cleanup() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Timeout RUNNING jobs
            cur.execute(
                f"""
                UPDATE jobs
                SET status='FAILED',
                    error=COALESCE(error, '{{}}'::jsonb) || '{{"reason":"timeout"}}'::jsonb,
                    finished_at=now(),
                    updated_at=now()
                WHERE status='RUNNING'
                  AND started_at < now() - INTERVAL '{JOB_TIMEOUT_SECONDS} seconds'
                RETURNING job_id
                """
            )
            timed_out_rows = cur.fetchall()
            for row in timed_out_rows:
                print(f"[gc] job timeout job_id={row[0]}")
            timed_out = len(timed_out_rows)

            # Expire very old QUEUED jobs (optional policy)
            cur.execute(
                f"""
                UPDATE jobs
                SET status='FAILED',
                    error=COALESCE(error, '{{}}'::jsonb) || '{{"reason":"expired"}}'::jsonb,
                    finished_at=now(),
                    updated_at=now()
                WHERE status='QUEUED'
                  AND created_at < now() - INTERVAL '{QUEUED_EXPIRE_SECONDS} seconds'
                RETURNING job_id
                """
            )
            expired_rows = cur.fetchall()
            for row in expired_rows:
                print(f"[gc] job expired job_id={row[0]}")
            expired = len(expired_rows)

            # Delete old finished jobs
            cur.execute(
                f"""
                DELETE FROM jobs
                WHERE status IN ('SUCCEEDED','FAILED')
                  AND finished_at IS NOT NULL
                  AND finished_at < now() - INTERVAL '{RETENTION_DAYS} days'
                """
            )
            deleted = cur.rowcount

            print(f"[gc] timed_out={timed_out}, expired={expired}, deleted={deleted}")


if __name__ == "__main__":
    run_cleanup()

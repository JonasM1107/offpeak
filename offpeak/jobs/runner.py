"""Shared wrapper for every job: connect, time it, log it to job_runs, never crash silently."""

import os
import sys
import traceback
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Engine

from offpeak import db


class Skip(Exception):
    """Raise inside a job when there is nothing to do (logged as 'skipped', not as an error)."""


def run(job: str, work: Callable[[Engine], int]) -> int:
    """Run work(engine) -> rows written. Returns a process exit code (0 ok/skipped, 1 failed)."""
    url = db.database_url()
    if url is None:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            # On GitHub a missing secret is a setup mistake: fail loudly instead of a green run.
            print(f"{job}: DATABASE_URL is empty. Add it under Settings > Secrets > Actions.")
            return 1
        print(f"{job}: DATABASE_URL is not set, nothing to do.")
        return 0
    engine = db.get_engine(url)
    started = datetime.now(UTC)
    status, rows, message, code = "ok", 0, None, 0
    try:
        rows = work(engine)
    except Skip as reason:
        status, message = "skipped", str(reason)
    except Exception as err:  # the job log must show every failure
        status, message, code = "failed", f"{type(err).__name__}: {err}", 1
        traceback.print_exc()
    db.log_job(engine, job, started, datetime.now(UTC), status, rows, message)
    print(f"{job}: {status}, {rows} rows" + (f" ({message})" if message else ""))
    return code


def main(job: str, work: Callable[[Engine], int]) -> None:
    sys.exit(run(job, work))

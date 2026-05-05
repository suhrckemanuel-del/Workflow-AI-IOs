"""
Scheduled agent runner — wraps APScheduler around agent_jobs from the DB.

On start_scheduler(): loads all enabled jobs and schedules them.
reload_job(agent_id): re-reads the DB row and reschedules (or removes) that job.
stop_scheduler(): shuts down gracefully on app exit.
"""

import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.db import (
    list_agent_jobs,
    get_agent_job,
    update_agent_job,
)
from core.registry import get_workflow, load_entry_function
from core.engine import run_workflow, _client_kb_root
from core.client_resolver import get_client_kb_root

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="UTC")


def _run_agent_job(agent_id: int) -> None:
    job = get_agent_job(agent_id)
    if not job or not job["enabled"]:
        return

    workflow_id = job["workflow_id"]
    inputs = json.loads(job["inputs_json"])
    inputs["_scheduled"] = True
    client_id = job.get("client_id")

    meta = get_workflow(workflow_id)
    if not meta:
        logger.error("Scheduled job %d: workflow '%s' not found", agent_id, workflow_id)
        update_agent_job(agent_id, last_run_at=_now(), last_status="error")
        return

    try:
        fn = load_entry_function(meta)
    except Exception as exc:
        logger.error("Scheduled job %d: could not load workflow: %s", agent_id, exc)
        update_agent_job(agent_id, last_run_at=_now(), last_status="error")
        return

    token = _client_kb_root.set(get_client_kb_root(client_id))
    try:
        result = run_workflow(fn, workflow_id=workflow_id, **inputs)
    except Exception as exc:
        logger.error("Scheduled job %d: run_workflow raised: %s", agent_id, exc)
        update_agent_job(agent_id, last_run_at=_now(), last_status="error")
        return
    finally:
        _client_kb_root.reset(token)

    status = result.get("status", "error")
    update_agent_job(agent_id, last_run_at=_now(), last_status=status)
    logger.info("Scheduled job %d (%s) finished with status=%s", agent_id, workflow_id, status)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _schedule_one(job: dict) -> None:
    job_id = str(job["id"])
    try:
        parts = job["cron_expr"].split()
        if len(parts) != 5:
            raise ValueError(f"Expected 5-field cron, got: {job['cron_expr']!r}")
        minute, hour, day, month, day_of_week = parts
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone="UTC",
        )
        _scheduler.add_job(
            _run_agent_job,
            trigger=trigger,
            args=[job["id"]],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("Scheduled agent job id=%s '%s' @ %s", job_id, job["name"], job["cron_expr"])
    except Exception as exc:
        logger.error("Failed to schedule agent job id=%s: %s", job_id, exc)


def start_scheduler() -> None:
    if _scheduler.running:
        return
    for job in list_agent_jobs():
        if job["enabled"]:
            _schedule_one(job)
    _scheduler.start()
    logger.info("APScheduler started with %d job(s)", len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


def reload_job(agent_id: int) -> None:
    """Re-read the DB and reschedule (or remove) a single job."""
    job_id = str(agent_id)
    job = get_agent_job(agent_id)

    if job is None or not job["enabled"]:
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)
            logger.info("Removed scheduler job id=%s", job_id)
        return

    _schedule_one(job)


def trigger_job_now(agent_id: int) -> None:
    """One-shot immediate execution for manual testing."""
    _run_agent_job(agent_id)

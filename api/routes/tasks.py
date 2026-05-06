import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from core import tasks_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    goal_slug: Optional[str] = None
    due_date: Optional[str] = None       # YYYY-MM-DD
    source: str = "manual"
    recurrence: Optional[str] = None


class TaskPatch(BaseModel):
    status: Optional[str] = None
    delegated_reason: Optional[str] = None
    completed_at: Optional[str] = None
    due_date: Optional[str] = None
    skip_count: Optional[int] = None


class AutoLogBody(BaseModel):
    workflow_id: str
    outcome: str
    note: Optional[str] = ""


class EveningEntry(BaseModel):
    task_id: int
    outcome: str
    note: Optional[str] = ""


class CheckinBody(BaseModel):
    type: str                             # morning | evening
    entries: Optional[list[EveningEntry]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/goals")
def list_goals():
    return [
        {"id": g["id"], "slug": g["slug"], "title": g["title"], "quarter": g["quarter"]}
        for g in tasks_db.list_goals()
        if g["status"] == "active"
    ]


@router.get("/tasks/weekly-report-preview", response_class=PlainTextResponse)
def weekly_report_preview():
    from tasks.weekly_report import build_weekly_report
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    start = monday.strftime("%Y-%m-%d")
    end = sunday.strftime("%Y-%m-%d")
    md, _ = build_weekly_report(start, end)
    return md


@router.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    goal_ref: int | None = None
    if body.goal_slug:
        goal = tasks_db.get_goal_by_slug(body.goal_slug)
        if goal is None:
            raise HTTPException(status_code=404, detail=f"Goal slug '{body.goal_slug}' not found")
        goal_ref = goal["id"]

    task = tasks_db.create_task(
        title=body.title,
        goal_ref=goal_ref,
        due_date=body.due_date,
        source=body.source,
        recurrence=body.recurrence,
    )

    # Mirror to Google Calendar (best-effort; never fail task creation).
    if task.get("due_date"):
        try:
            from tasks.calendar_sync import create_calendar_event
            enriched = dict(task)
            if goal_ref:
                goal = tasks_db.get_goal_by_slug(body.goal_slug) if body.goal_slug else None
                if goal:
                    enriched["goal_title"] = goal["title"]
                    enriched["goal_slug"] = goal["slug"]
            event_id = create_calendar_event(enriched)
            tasks_db.update_task_calendar_event(task["id"], event_id)
            task["calendar_event_id"] = event_id
        except Exception as e:
            logger.warning("Calendar sync failed: %s", e)

    return task


@router.get("/tasks")
def list_tasks(date: Optional[str] = None):
    target = date or datetime.utcnow().strftime("%Y-%m-%d")
    return tasks_db.get_tasks_for_date(target)


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    task = tasks_db.update_task(task_id, **updates)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    new_status = updates.get("status")
    event_id = task.get("calendar_event_id")
    if new_status in ("done", "skipped") and event_id:
        try:
            from tasks.calendar_sync import update_calendar_event
            update_calendar_event(event_id, new_status)
        except Exception as e:
            logger.warning("Calendar update failed: %s", e)

    return task


@router.post("/tasks/auto-log", status_code=201)
def auto_log(body: AutoLogBody):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    task = tasks_db.create_task(
        title=f"[auto] {body.workflow_id}",
        source="auto_log",
        due_date=today,
    )
    tasks_db.update_task(task["id"], status="done", completed_at=datetime.utcnow().isoformat())
    log = tasks_db.create_daily_log(
        log_date=today,
        task_id=task["id"],
        outcome=body.outcome,
        note=body.note or "",
    )
    return {"task": task, "log": log}


@router.post("/tasks/checkin")
def checkin(body: CheckinBody):
    if body.type not in ("morning", "evening"):
        raise HTTPException(status_code=400, detail="type must be 'morning' or 'evening'")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    record = tasks_db.create_checkin(checkin_date=today, checkin_type=body.type)

    if body.type == "morning":
        tasks = tasks_db.get_tasks_for_date(today)
        return {"checkin": record, "tasks": tasks}

    # Evening: log outcomes for each submitted entry
    if not body.entries:
        raise HTTPException(status_code=400, detail="Evening checkin requires entries list")

    logs = []
    for entry in body.entries:
        task = tasks_db.get_task(entry.task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {entry.task_id} not found")
        log = tasks_db.create_daily_log(
            log_date=today,
            task_id=entry.task_id,
            outcome=entry.outcome,
            note=entry.note or "",
        )
        if entry.outcome == "done":
            tasks_db.update_task(entry.task_id, status="done", completed_at=datetime.utcnow().isoformat())
        logs.append(log)

    tasks_db.mark_checkin_responded(record["id"])
    return {"checkin": record, "logs": logs}

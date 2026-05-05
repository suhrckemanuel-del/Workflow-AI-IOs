import json

from fastapi import APIRouter, HTTPException

from api.models import AgentJob, AgentJobCreate, AgentJobUpdate
from api.scheduler import reload_job, trigger_job_now
from core.db import (
    create_agent_job,
    list_agent_jobs,
    get_agent_job,
    update_agent_job,
    delete_agent_job,
)

router = APIRouter()


def _to_model(row: dict) -> AgentJob:
    return AgentJob(
        id=row["id"],
        name=row["name"],
        workflow_id=row["workflow_id"],
        cron_expr=row["cron_expr"],
        inputs_json=row["inputs_json"],
        client_id=row.get("client_id"),
        enabled=bool(row["enabled"]),
        last_run_at=row.get("last_run_at"),
        last_status=row.get("last_status"),
        created_at=row["created_at"],
    )


@router.get("/agents", response_model=list[AgentJob])
def list_agents():
    return [_to_model(r) for r in list_agent_jobs()]


@router.post("/agents", response_model=AgentJob, status_code=201)
def create_agent(body: AgentJobCreate):
    row = create_agent_job(
        name=body.name,
        workflow_id=body.workflow_id,
        cron_expr=body.cron_expr,
        inputs_json=json.dumps(body.inputs),
        client_id=body.client_id,
    )
    reload_job(row["id"])
    return _to_model(row)


@router.get("/agents/{agent_id}", response_model=AgentJob)
def get_agent(agent_id: int):
    row = get_agent_job(agent_id)
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _to_model(row)


@router.patch("/agents/{agent_id}", response_model=AgentJob)
def update_agent(agent_id: int, body: AgentJobUpdate):
    row = get_agent_job(agent_id)
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.cron_expr is not None:
        updates["cron_expr"] = body.cron_expr
    if body.inputs is not None:
        updates["inputs_json"] = json.dumps(body.inputs)
    if body.enabled is not None:
        updates["enabled"] = int(body.enabled)

    if updates:
        row = update_agent_job(agent_id, **updates)

    reload_job(agent_id)
    return _to_model(row)


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: int):
    row = get_agent_job(agent_id)
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    delete_agent_job(agent_id)
    reload_job(agent_id)  # removes from scheduler since row is now gone
    return {"success": True}


@router.post("/agents/{agent_id}/run", status_code=202)
def run_agent_now(agent_id: int):
    """One-shot manual trigger for testing without waiting for the cron."""
    row = get_agent_job(agent_id)
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    trigger_job_now(agent_id)
    updated = get_agent_job(agent_id)
    return {"success": True, "last_status": updated.get("last_status") if updated else None}

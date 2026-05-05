import json

from fastapi import APIRouter, HTTPException, Query

from api.models import RunRecord
from core.db import get_runs, get_run
from core.registry import get_workflow
from core.trust_layer import build_trust_report

router = APIRouter()


@router.get("/runs", response_model=list[RunRecord])
def list_runs(
    workflow_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows = get_runs(workflow_id=workflow_id, limit=limit, offset=offset)
    return [RunRecord(**_with_trust_report(r)) for r in rows]


@router.get("/runs/{run_id}", response_model=RunRecord)
def get_run_by_id(run_id: int):
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return RunRecord(**_with_trust_report(row))


def _with_trust_report(row: dict) -> dict:
    meta = get_workflow(row["workflow_id"])
    inputs = _parse_json(row.get("inputs_json")) or {}
    outputs = _parse_json(row.get("outputs_json")) or {}
    row = dict(row)
    row["trust_report"] = build_trust_report(
        workflow_id=row["workflow_id"],
        status=row["status"],
        inputs=inputs,
        outputs=outputs,
        error=row.get("error_message"),
        duration_seconds=row.get("duration_s"),
        model=row.get("model_used"),
        primary_display_field=meta.primary_display_field if meta else None,
        requires_exa=meta.requires_exa if meta else False,
        test_mode=False,
    )
    return row


def _parse_json(raw: str | None):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

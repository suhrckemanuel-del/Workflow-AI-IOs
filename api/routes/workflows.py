import asyncio
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.models import (
    WorkflowMetaResponse,
    WorkflowInputSpec,
    RunWorkflowRequest,
    RunResponse,
    WorkflowJobStartResponse,
    WorkflowJobStatus,
)
from core.registry import discover_workflows, get_workflow, load_entry_function
from core.engine import run_workflow, _client_kb_root
from core.client_resolver import get_client_kb_root
from core.db import get_runs
from core.trust_layer import build_trust_report
from api.services.error_logger import append_runtime_error

_executor = ThreadPoolExecutor(max_workers=4)
_jobs: dict[str, dict] = {}

router = APIRouter()


def _run_loaded_workflow(meta, fn, workflow_id: str, inputs: dict, test: bool, client: str | None) -> RunResponse:
    try:
        kb_root = get_client_kb_root(client)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client id")
    token = _client_kb_root.set(kb_root)
    try:
        result = run_workflow(fn, workflow_id=workflow_id, **inputs)
    finally:
        _client_kb_root.reset(token)

    if result.get("status") == "error":
        append_runtime_error(
            workflow_id=workflow_id,
            error=result.get("error") or "",
            duration=result.get("duration_seconds") or 0.0,
            inputs=inputs,
        )

    if test and result.get("status") == "success":
        output = result.get("result") or {}
        for file_path in [output.get("file_path"), output.get("csv_file_path")]:
            if not file_path:
                continue
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass

    recent = get_runs(workflow_id=workflow_id, limit=1)
    run_id = recent[0]["id"] if recent else None
    trust_report = build_trust_report(
        workflow_id=workflow_id,
        status=result["status"],
        inputs=inputs,
        outputs=result.get("result"),
        error=result.get("error"),
        duration_seconds=result["duration_seconds"],
        model=recent[0].get("model_used") if recent else None,
        primary_display_field=meta.primary_display_field,
        requires_exa=meta.requires_exa,
        test_mode=test,
    )

    return RunResponse(
        status=result["status"],
        result=result.get("result"),
        duration_seconds=result["duration_seconds"],
        run_id=run_id,
        error=result.get("error"),
        trust_report=trust_report,
    )


def _start_job(job_id: str, meta, fn, workflow_id: str, inputs: dict, test: bool, client: str | None) -> None:
    try:
        _jobs[job_id]["message"] = _status_messages(meta)[0]
        response = _run_loaded_workflow(meta, fn, workflow_id, inputs, test, client)
        _jobs[job_id].update(
            status=response.status,
            message="Done" if response.status == "success" else "Failed",
            response=response.model_dump(),
            error=response.error,
            finished_at=time.time(),
        )
    except Exception as e:
        _jobs[job_id].update(
            status="error",
            message="Failed",
            response=None,
            error=str(e),
            finished_at=time.time(),
        )


def _serialize(meta) -> WorkflowMetaResponse:
    return WorkflowMetaResponse(
        id=meta.id,
        name=meta.name,
        icon=meta.icon,
        description=meta.description,
        order=meta.order,
        inputs=[
            WorkflowInputSpec(
                key=i.key,
                label=i.label,
                type=i.type,
                required=i.required,
                placeholder=i.placeholder,
                choices=i.choices,
            )
            for i in meta.inputs
        ],
        primary_display_field=meta.primary_display_field,
        stats_label=meta.stats_label,
        requires_exa=meta.requires_exa,
        demo_available=meta.demo_available,
        output_fields=meta.output_fields,
    )


def _status_messages(meta) -> list[str]:
    if meta.requires_exa:
        return [
            "Fetching live signals…",
            "Researching the web…",
            "Analysing with Claude…",
            "Generating output…",
        ]
    return ["Running…", "Processing with Claude…", "Generating output…"]


@router.get("/workflows", response_model=list[WorkflowMetaResponse])
def list_workflows():
    return [_serialize(m) for m in discover_workflows()]


@router.get("/workflows/{workflow_id}", response_model=WorkflowMetaResponse)
def get_workflow_by_id(workflow_id: str):
    meta = get_workflow(workflow_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return _serialize(meta)


@router.post("/workflows/{workflow_id}/run", response_model=RunResponse)
def run_workflow_endpoint(
    workflow_id: str,
    body: RunWorkflowRequest,
    test: bool = Query(default=False, description="Run without persisting output to knowledge base"),
    client: str | None = Query(default=None),
):
    meta = get_workflow(workflow_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    try:
        fn = load_entry_function(meta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load workflow: {e}")

    return _run_loaded_workflow(meta, fn, workflow_id, body.inputs, test, client)


@router.post("/workflows/{workflow_id}/run/job", response_model=WorkflowJobStartResponse)
def start_workflow_job(
    workflow_id: str,
    body: RunWorkflowRequest,
    test: bool = Query(default=False, description="Run without persisting output to knowledge base"),
    client: str | None = Query(default=None),
):
    meta = get_workflow(workflow_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    try:
        fn = load_entry_function(meta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load workflow: {e}")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "workflow_id": workflow_id,
        "status": "running",
        "message": "Queued",
        "started_at": time.time(),
        "response": None,
        "error": None,
    }
    _executor.submit(_start_job, job_id, meta, fn, workflow_id, body.inputs, test, client)
    return WorkflowJobStartResponse(job_id=job_id)


@router.get("/workflow-jobs/{job_id}", response_model=WorkflowJobStatus)
def get_workflow_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Workflow job not found. It may have been cleared by a backend restart.")

    elapsed = round(time.time() - job["started_at"], 1)
    response = RunResponse(**job["response"]) if job.get("response") else None
    return WorkflowJobStatus(
        job_id=job_id,
        workflow_id=job["workflow_id"],
        status=job["status"],
        message=job["message"],
        elapsed_seconds=elapsed,
        response=response,
        error=job.get("error"),
    )


@router.post("/workflows/{workflow_id}/run/stream")
async def run_workflow_stream(
    workflow_id: str,
    body: RunWorkflowRequest,
    test: bool = Query(default=False),
    client: str | None = Query(default=None),
):
    meta = get_workflow(workflow_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    try:
        fn = load_entry_function(meta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load workflow: {e}")

    async def generate():
        loop = asyncio.get_event_loop()
        start = time.time()
        messages = _status_messages(meta)
        msg_idx = 0
        last_switch = start

        try:
            kb_root = get_client_kb_root(client)
        except ValueError:
            payload = {
                "status": "error",
                "result": None,
                "duration_seconds": 0,
                "run_id": None,
                "error": "Invalid client id",
                "trust_report": None,
            }
            yield f"event: result\ndata: {json.dumps(payload)}\n\n"
            yield "event: done\ndata: {}\n\n"
            return
        token = _client_kb_root.set(kb_root)
        ctx = copy_context()
        _client_kb_root.reset(token)
        future = loop.run_in_executor(
            _executor,
            lambda: ctx.run(run_workflow, fn, workflow_id=workflow_id, **body.inputs),
        )

        while not future.done():
            elapsed = round(time.time() - start, 1)
            now = time.time()
            # Advance status message every ~8 s
            if msg_idx < len(messages) - 1 and now - last_switch >= 8:
                msg_idx += 1
                last_switch = now
            data = json.dumps({"message": messages[msg_idx], "elapsed": elapsed})
            yield f"event: status\ndata: {data}\n\n"
            await asyncio.sleep(0.8)

        try:
            result = await future
        except Exception as exc:
            duration = round(time.time() - start, 2)
            append_runtime_error(
                workflow_id=workflow_id,
                error=str(exc),
                duration=duration,
                inputs=body.inputs,
            )
            payload = {
                "status": "error",
                "result": None,
                "duration_seconds": duration,
                "run_id": None,
                "error": str(exc),
                "trust_report": None,
            }
            yield f"event: result\ndata: {json.dumps(payload)}\n\n"
            yield "event: done\ndata: {}\n\n"
            return

        if test and result.get("status") == "success":
            output = result.get("result") or {}
            for file_path in [output.get("file_path"), output.get("csv_file_path")]:
                if not file_path:
                    continue
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass

        recent = get_runs(workflow_id=workflow_id, limit=1)
        run_id = recent[0]["id"] if recent else None
        trust_report = build_trust_report(
            workflow_id=workflow_id,
            status=result["status"],
            inputs=body.inputs,
            outputs=result.get("result"),
            error=result.get("error"),
            duration_seconds=result["duration_seconds"],
            model=recent[0].get("model_used") if recent else None,
            primary_display_field=meta.primary_display_field,
            requires_exa=meta.requires_exa,
            test_mode=test,
        )

        payload = {
            "status": result["status"],
            "result": result.get("result"),
            "duration_seconds": result["duration_seconds"],
            "run_id": run_id,
            "error": result.get("error"),
            "trust_report": trust_report,
        }
        yield f"event: result\ndata: {json.dumps(payload)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

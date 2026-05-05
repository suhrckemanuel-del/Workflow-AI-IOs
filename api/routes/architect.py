from fastapi import APIRouter, HTTPException
import re

from api.models import ArchitectChatRequest, ArchitectChatResponse
from core.architect import AIArchitect

router = APIRouter()
WORKFLOW_ID_RE = re.compile(r"^[a-z0-9_]+$")

_architect = None


def _get_architect() -> AIArchitect:
    global _architect
    if _architect is None:
        _architect = AIArchitect()
    return _architect


@router.post("/architect/chat", response_model=ArchitectChatResponse)
def architect_chat(body: ArchitectChatRequest):
    try:
        architect = _get_architect()
        reply = architect.chat(body.message, body.history)
        yaml_content = architect.extract_yaml(reply)
        return ArchitectChatResponse(
            reply=reply,
            yaml_detected=yaml_content is not None,
            yaml_content=yaml_content,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/architect/deploy")
def architect_deploy(body: dict):
    yaml_content = body.get("yaml", "")
    workflow_id = body.get("workflow_id", "")
    if not yaml_content or not workflow_id:
        raise HTTPException(status_code=400, detail="yaml and workflow_id are required")
    if not WORKFLOW_ID_RE.fullmatch(workflow_id):
        raise HTTPException(status_code=400, detail="workflow_id must be lowercase snake_case")
    try:
        architect = _get_architect()
        success = architect.save_generated_workflow(yaml_content, workflow_id)
        return {"success": success, "workflow_id": workflow_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

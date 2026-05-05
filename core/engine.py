"""
AI-OS Core Engine
-----------------
Powers every workflow. Four primitives:
  load_context   — pull markdown from the knowledge base
  call_claude    — Claude call with retry + exponential backoff
  call_claude_structured — Claude call that enforces a Pydantic schema
  save_output    — write output back into the knowledge base
  run_workflow   — wrap any workflow fn with timing, error handling, DB logging
"""

import json
import os
import random
import time
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic
from anthropic import APIConnectionError, APIStatusError, RateLimitError
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

ROOT   = Path(__file__).parent.parent
KB     = ROOT / "knowledge_base"

# API layer sets this before running a workflow so the correct client KB is used
# without touching any workflow code. run_in_executor copies the context to the thread.
_client_kb_root: ContextVar[Path | None] = ContextVar("_client_kb_root", default=None)

DEFAULT_MODEL   = "claude-sonnet-4-6"
MAX_RETRIES     = 3
RETRY_BASE_DELAY = 1.0   # seconds
RETRY_MAX_DELAY  = 30.0

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _safe_kb_path(kb_root: Path, *parts: str) -> Path:
    root = kb_root.resolve()
    path = root.joinpath(*(part or "" for part in parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("Path escapes knowledge base root")
    return path


# ── Knowledge base loader ──────────────────────────────────────────────────────

def load_context(folder: str = None, filename: str = None, kb_root: Path | None = None) -> str:
    """
    Pull context from the knowledge base.
    folder:   subfolder inside knowledge_base/
    filename: specific file, or None to load all .md files in folder
    kb_root:  override KB root (used by multi-client; also reads from _client_kb_root context var)
    """
    effective_kb = kb_root or _client_kb_root.get() or KB

    if filename:
        path = _safe_kb_path(effective_kb, folder or "", filename)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    if folder:
        path = _safe_kb_path(effective_kb, folder)
        if not path.exists():
            return ""
        texts = [
            f"### {f.stem}\n{f.read_text(encoding='utf-8')}"
            for f in sorted(path.glob("*.md"))
        ]
        return "\n\n".join(texts)

    return ""


# ── Output saver ───────────────────────────────────────────────────────────────

def save_output(content: str, folder: str, filename: str = None, kb_root: Path | None = None) -> Path:
    """Save workflow output back into the knowledge base."""
    effective_kb = kb_root or _client_kb_root.get() or KB
    out_dir = _safe_kb_path(effective_kb, folder)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"output_{timestamp}.md"

    path = _safe_kb_path(out_dir, filename)
    path.write_text(content, encoding="utf-8")
    return path


# ── Claude caller (with retry) ─────────────────────────────────────────────────

def call_claude(
    system: str,
    user: str,
    max_tokens: int = 2000,
    retries: int = MAX_RETRIES,
) -> str:
    """
    Core Claude call with exponential backoff retry.
    Retries on RateLimitError and APIConnectionError.
    Raises immediately on APIStatusError (4xx — retrying is pointless).
    """
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except RateLimitError as e:
            last_error = e
            if attempt == retries:
                raise
            delay = min(RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), RETRY_MAX_DELAY)
            time.sleep(delay)
        except APIConnectionError as e:
            last_error = e
            if attempt == retries:
                raise
            delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
            time.sleep(delay)
        except APIStatusError:
            raise  # 400/401/403 — do not retry
    raise last_error


# ── Structured Claude caller ───────────────────────────────────────────────────

def call_claude_structured(
    system: str,
    user: str,
    schema: type[BaseModel],
    max_tokens: int = 2000,
) -> BaseModel:
    """
    Claude call that enforces a Pydantic schema on the response.
    Instructs Claude to return raw JSON only, validates against schema.
    Retries once on validation failure before raising.
    Returns a validated Pydantic model instance.
    """
    json_instruction = (
        "\n\nIMPORTANT: Your entire response must be valid JSON matching this schema exactly. "
        "No prose, no markdown, no code fences — raw JSON only.\n"
        f"Schema: {json.dumps(schema.model_json_schema(), indent=2)}"
    )
    augmented_system = system + json_instruction

    last_error: Exception | None = None
    current_user = user

    for attempt in range(2):
        raw = call_claude(augmented_system, current_user, max_tokens=max_tokens)
        try:
            cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data    = json.loads(cleaned)
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            if attempt == 0:
                current_user = (
                    user
                    + f"\n\nYour previous response was not valid JSON matching the schema. "
                    f"Error: {e}. Return only raw JSON this time, no other text."
                )

    raise ValueError(
        f"Claude output failed schema validation after 2 attempts. "
        f"Last error: {last_error}"
    )


# ── Workflow runner ────────────────────────────────────────────────────────────

def run_workflow(workflow_fn, workflow_id: str = None, **kwargs) -> dict:
    """
    Wrap any workflow function with timing, error handling, and DB logging.
    workflow_id: if supplied, every run is logged to SQLite automatically.
    """
    from core.db import log_run  # local import — avoids circular dep at module load

    start           = datetime.now()
    inputs_snapshot = {k: str(v)[:500] for k, v in kwargs.items()}

    try:
        result   = workflow_fn(**kwargs)
        duration = round((datetime.now() - start).total_seconds(), 2)
        if workflow_id:
            log_run(
                workflow_id=workflow_id,
                status="success",
                inputs=inputs_snapshot,
                outputs=result,
                error=None,
                duration=duration,
                model=DEFAULT_MODEL,
            )
        return {"status": "success", "result": result, "duration_seconds": duration}

    except Exception as e:
        duration = round((datetime.now() - start).total_seconds(), 2)
        if workflow_id:
            log_run(
                workflow_id=workflow_id,
                status="error",
                inputs=inputs_snapshot,
                outputs=None,
                error=str(e),
                duration=duration,
                model=DEFAULT_MODEL,
            )
        return {"status": "error", "error": str(e), "duration_seconds": duration}

from datetime import datetime
from pathlib import Path

_HEADER = (
    "# AI-OS Runtime Error Log\n"
    "# Auto-captured. Do not edit manually — use error_playbook.md for curated fixes.\n\n"
)


def _truncate_inputs(inputs: dict) -> str:
    parts = []
    for k, v in inputs.items():
        s = str(v)
        if len(s) > 200:
            s = s[:200]
        parts.append(f"{k}={s}")
    return ", ".join(parts)


def append_runtime_error(workflow_id: str, error: str, duration: float, inputs: dict) -> None:
    try:
        project_root = Path(__file__).resolve().parents[2]
        log_path = project_root / "knowledge_base" / "reliability" / "runtime_errors.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        is_new = not log_path.exists() or log_path.stat().st_size == 0

        entry = (
            f"**{timestamp}** | workflow: {workflow_id} | duration: {duration:.1f}s\n"
            f"**Error:** {error}\n"
            f"**Inputs:** {_truncate_inputs(inputs)}\n\n"
        )

        with open(log_path, "a", encoding="utf-8") as f:
            if is_new:
                f.write(_HEADER)
            f.write(entry)
    except Exception:
        pass

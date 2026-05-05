import sys
from datetime import datetime
from pathlib import Path

HEADER = (
    "| Date | Workflow | Project | Score | Verdict | Checks | Mode | Notes |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def _first_sentence(text: str, limit: int = 80) -> str:
    if not text:
        return ""
    cleaned = text.strip().replace("\r", " ").replace("\n", " ")
    for sep in (". ", "! ", "? "):
        idx = cleaned.find(sep)
        if idx != -1:
            cleaned = cleaned[: idx + 1]
            break
    cleaned = cleaned.strip()
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned


def append_eval_history(entry: dict) -> None:
    try:
        log_path = (
            Path(__file__).resolve().parents[2]
            / "knowledge_base"
            / "reliability"
            / "eval_history.md"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)

        write_header = not log_path.exists() or log_path.stat().st_size == 0

        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        workflow = _escape(str(entry.get("workflow_id") or ""))
        project = _escape(str(entry.get("project_name") or ""))
        score = entry.get("score")
        score_str = str(score) if score is not None else ""
        verdict = _escape(str(entry.get("verdict") or ""))
        passed = entry.get("passed", 0)
        total = entry.get("total", 0)
        checks = f"{passed}/{total}"
        mode = _escape(str(entry.get("mode") or ""))
        notes = _escape(_first_sentence(str(entry.get("reasoning") or "")))

        row = f"| {date} | {workflow} | {project} | {score_str} | {verdict} | {checks} | {mode} | {notes} |\n"

        with open(log_path, "a", encoding="utf-8") as f:
            if write_header:
                f.write(HEADER)
            f.write(row)
    except Exception as exc:
        print(f"[eval_logger] failed to append eval history: {exc}", file=sys.stderr)

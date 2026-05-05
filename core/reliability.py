"""
Reliability helpers
-------------------
Small utilities for keeping recurring build/workflow failures visible to agents.
"""

from pathlib import Path

ROOT = Path(__file__).parent.parent
PLAYBOOK_PATH = ROOT / "knowledge_base" / "reliability" / "error_playbook.md"


def load_error_playbook(limit_chars: int = 6000) -> str:
    if not PLAYBOOK_PATH.exists():
        return "- No error playbook found yet."
    text = PLAYBOOK_PATH.read_text(encoding="utf-8").strip()
    if len(text) <= limit_chars:
        return text
    return text[:limit_chars].rstrip() + "\n\n[Truncated in package. Open knowledge_base/reliability/error_playbook.md for full notes.]"

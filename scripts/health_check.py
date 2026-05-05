"""
AI-OS Health Check
------------------
Runs at dashboard startup. Never raises — returns a status dict.
"""

import os
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run_health_check() -> dict:
    warnings = []
    checks   = {}

    # API keys
    checks["anthropic_key"] = bool(os.getenv("ANTHROPIC_API_KEY"))
    checks["exa_key"]       = bool(os.getenv("EXA_API_KEY"))
    if not checks["anthropic_key"]:
        warnings.append("ANTHROPIC_API_KEY not set. Add it to your .env file.")

    # DB writability
    try:
        from core.db import init_db
        init_db()
        checks["db_writable"] = True
    except Exception as e:
        checks["db_writable"] = False
        warnings.append(f"Database error: {e}")

    # Workflow count
    try:
        from core.registry import discover_workflows
        wfs = discover_workflows()
        checks["workflows_found"] = len(wfs)
        if checks["workflows_found"] == 0:
            warnings.append("No workflows found in workflows/ directory.")
    except Exception as e:
        checks["workflows_found"] = 0
        warnings.append(f"Registry error: {e}")

    # Knowledge base populated
    thesis_path = ROOT / "knowledge_base" / "thesis" / "investment_thesis.md"
    try:
        populated = (
            thesis_path.exists()
            and "[Your name" not in thesis_path.read_text(encoding="utf-8")
        )
    except Exception:
        populated = False
    checks["knowledge_base_populated"] = populated
    if not populated:
        warnings.append(
            "knowledge_base/thesis/investment_thesis.md is still a template — "
            "fill it in to get better outputs from every workflow."
        )

    demo_mode = (
        not checks["anthropic_key"]
        or os.getenv("DEMO_MODE", "false").lower() == "true"
    )

    return {
        "ok":        checks.get("db_writable", False) and (checks["anthropic_key"] or demo_mode),
        "demo_mode": demo_mode,
        "warnings":  warnings,
        "checks":    checks,
    }

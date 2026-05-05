"""
AI-OS Trust Layer
-----------------
Builds lightweight, derived trust reports for workflow runs without requiring
existing workflow modules to change.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def build_trust_report(
    workflow_id: str,
    status: str,
    inputs: dict[str, Any] | None,
    outputs: dict[str, Any] | None,
    error: str | None = None,
    duration_seconds: float | None = None,
    model: str | None = None,
    primary_display_field: str | None = None,
    requires_exa: bool = False,
    test_mode: bool = False,
) -> dict[str, Any]:
    outputs = outputs or {}
    inputs = inputs or {}
    sources = _extract_sources(outputs)
    saved_files = _extract_saved_files(outputs)
    validation_checks = _build_validation_checks(
        workflow_id=workflow_id,
        status=status,
        outputs=outputs,
        sources=sources,
        saved_files=saved_files,
        error=error,
        primary_display_field=primary_display_field,
        requires_exa=requires_exa,
        test_mode=test_mode,
    )
    timeline = _build_timeline(
        status=status,
        inputs=inputs,
        outputs=outputs,
        sources=sources,
        saved_files=saved_files,
        validation_checks=validation_checks,
        error=error,
        requires_exa=requires_exa,
        test_mode=test_mode,
    )
    passed = sum(1 for check in validation_checks if check["passed"])
    total = len(validation_checks)
    blocking = [
        check for check in validation_checks
        if not check["passed"] and check.get("severity") == "error"
    ]
    warnings = [
        check for check in validation_checks
        if not check["passed"] and check.get("severity") != "error"
    ]
    if blocking:
        validation_status = "fail"
    elif warnings:
        validation_status = "warn"
    else:
        validation_status = "pass"

    return {
        "timeline": timeline,
        "evidence": {
            "sources": sources,
            "saved_files": saved_files,
            "source_count": len(sources),
            "saved_file_count": len(saved_files),
        },
        "validation": {
            "status": validation_status,
            "passed": passed,
            "total": total,
            "checks": validation_checks,
        },
        "metadata": {
            "workflow_id": workflow_id,
            "model": model,
            "duration_seconds": duration_seconds,
            "test_mode": test_mode,
        },
    }


def _build_timeline(
    status: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    sources: list[dict[str, str]],
    saved_files: list[dict[str, str]],
    validation_checks: list[dict[str, Any]],
    error: str | None,
    requires_exa: bool,
    test_mode: bool,
) -> list[dict[str, str]]:
    timeline = [
        {
            "key": "input",
            "label": "Input captured",
            "status": "success" if inputs else "warning",
            "detail": f"{len(inputs)} input field(s) logged." if inputs else "No input snapshot was available.",
        }
    ]

    if requires_exa:
        timeline.append({
            "key": "evidence",
            "label": "Evidence collected",
            "status": "success" if sources else "warning",
            "detail": f"{len(sources)} source(s) attached." if sources else "No web sources were attached.",
        })
    else:
        timeline.append({
            "key": "context",
            "label": "Knowledge context prepared",
            "status": "success",
            "detail": "Workflow used local inputs and knowledge-base context.",
        })

    timeline.append({
        "key": "process",
        "label": "Workflow executed",
        "status": "success" if status == "success" else "error",
        "detail": "Output returned from workflow." if status == "success" else (error or "Workflow failed."),
    })

    passed = sum(1 for check in validation_checks if check["passed"])
    total = len(validation_checks)
    validation_state = "success" if passed == total else "warning"
    if any(not check["passed"] and check.get("severity") == "error" for check in validation_checks):
        validation_state = "error"
    timeline.append({
        "key": "validation",
        "label": "Validation checks built",
        "status": validation_state,
        "detail": f"{passed}/{total} checks passed.",
    })

    if test_mode:
        save_status = "warning"
        save_detail = "Test mode was on, so saved files may have been removed."
    elif saved_files:
        save_status = "success"
        save_detail = f"{len(saved_files)} artifact(s) saved."
    elif status == "success":
        save_status = "warning"
        save_detail = "No saved artifact path was returned."
    else:
        save_status = "error"
        save_detail = "Nothing was saved because the run failed."
    timeline.append({
        "key": "save",
        "label": "Obsidian artifact handled",
        "status": save_status,
        "detail": save_detail,
    })

    if outputs.get("csv") or outputs.get("csv_file_path"):
        timeline.append({
            "key": "export",
            "label": "Export artifact prepared",
            "status": "success" if outputs.get("csv_file_path") else "warning",
            "detail": "CSV file saved." if outputs.get("csv_file_path") else "CSV text returned without a file path.",
        })

    return timeline


def _build_validation_checks(
    workflow_id: str,
    status: str,
    outputs: dict[str, Any],
    sources: list[dict[str, str]],
    saved_files: list[dict[str, str]],
    error: str | None,
    primary_display_field: str | None,
    requires_exa: bool,
    test_mode: bool,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = [
        {
            "key": "run_completed",
            "label": "Run completed without backend error",
            "passed": status == "success",
            "severity": "error",
            "details": "Workflow returned success." if status == "success" else (error or "Workflow returned an error."),
        }
    ]

    primary_value = outputs.get(primary_display_field or "") if primary_display_field else None
    has_primary = bool(str(primary_value or "").strip())
    checks.append({
        "key": "primary_output_present",
        "label": "Primary output is present",
        "passed": has_primary or status != "success",
        "severity": "error",
        "details": (
            f"Primary field '{primary_display_field}' returned content."
            if has_primary else
            f"Primary field '{primary_display_field or 'unknown'}' was empty."
        ),
    })

    has_artifact = bool(saved_files)
    checks.append({
        "key": "obsidian_artifact",
        "label": "Obsidian artifact path returned",
        "passed": has_artifact or test_mode or status != "success",
        "severity": "warning",
        "details": (
            f"{len(saved_files)} saved file path(s) returned."
            if has_artifact else
            "Test mode can remove saved artifacts." if test_mode else
            "No file path was returned."
        ),
    })

    if requires_exa:
        checks.append({
            "key": "sources_attached",
            "label": "Research sources attached",
            "passed": bool(sources) or status != "success",
            "severity": "warning",
            "details": f"{len(sources)} source URL(s) attached." if sources else "No source URLs were attached.",
        })

    if workflow_id in {"email_drafting", "vc_lead_scraper"}:
        checks.append({
            "key": "human_review_required",
            "label": "Human review required before outreach",
            "passed": True,
            "severity": "info",
            "details": "AI-OS should generate drafts/leads; a human should approve before sending.",
        })

    checks.extend(_extract_validation_notes(outputs))
    return checks


def _extract_sources(outputs: dict[str, Any]) -> list[dict[str, str]]:
    raw_sources = outputs.get("sources") or outputs.get("source_urls") or []
    if isinstance(raw_sources, str):
        raw_sources = [raw_sources]
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_sources if isinstance(raw_sources, list) else []:
        title = ""
        url = ""
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or item.get("url") or "").strip()
            url = str(item.get("url") or item.get("source_url") or "").strip()
        else:
            url = str(item).strip()
            title = url
        if not url:
            continue
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        sources.append({"title": title or url, "url": url, "kind": "web_source"})
    return sources


def _extract_saved_files(outputs: dict[str, Any]) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    for key, value in outputs.items():
        if "file_path" not in key and key not in {"save_path", "path"}:
            continue
        if not value:
            continue
        path = str(value)
        if path in seen:
            continue
        seen.add(path)
        files.append({
            "label": key.replace("_", " "),
            "path": path,
            "filename": Path(path).name,
        })
    return files


def _extract_validation_notes(outputs: dict[str, Any]) -> list[dict[str, Any]]:
    notes: list[str] = []
    raw_notes = outputs.get("validation_notes")
    if isinstance(raw_notes, list):
        notes.extend(str(note) for note in raw_notes)
    for key in ("brief", "output", "full_brief"):
        value = outputs.get(key)
        if isinstance(value, str) and "## Validation Notes" in value:
            notes.extend(_markdown_section_bullets(value, "Validation Notes"))

    checks: list[dict[str, Any]] = []
    for index, note in enumerate(notes[:12]):
        normalized = note.strip().lstrip("- ").strip()
        upper = normalized.upper()
        if upper.startswith("PASS"):
            passed = True
            severity = "info"
        elif upper.startswith("WARN") or upper.startswith("INFO"):
            passed = False
            severity = "warning"
        else:
            passed = True
            severity = "info"
        checks.append({
            "key": f"workflow_note_{index + 1}",
            "label": "Workflow self-check",
            "passed": passed,
            "severity": severity,
            "details": normalized,
        })
    return checks


def _markdown_section_bullets(markdown: str, heading: str) -> list[str]:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)",
        re.MULTILINE,
    )
    match = pattern.search(markdown)
    if not match:
        return []
    section = match.group(1)
    return [
        line.strip()
        for line in section.splitlines()
        if line.strip().startswith("- ")
    ]

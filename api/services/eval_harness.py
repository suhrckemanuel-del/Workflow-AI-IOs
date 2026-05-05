from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from core.client_resolver import get_client_kb_root
from core.db import get_runs
from core.engine import _client_kb_root, run_workflow
from core.registry import get_workflow, load_entry_function

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "knowledge_base"


def infer_project_workflow_id(project: dict[str, Any]) -> str | None:
    text = " ".join(
        str(project.get(key, ""))
        for key in ("name", "goal", "required_tools", "working_definition")
    ).lower()
    if "outreach draft" in text or "draft" in text and "outreach" in text:
        return "vc_outreach_drafts"
    if "vc" in text or "lead" in text or "outreach" in text:
        return "vc_lead_scraper"
    if "company" in text or "research" in text:
        return "company_research"
    if "email" in text:
        return "email_drafting"
    if "meeting" in text:
        return "meeting_prep"
    if "portfolio" in text:
        return "portfolio_monitor"
    return None


def default_project_inputs(project: dict[str, Any], workflow_id: str | None) -> dict[str, Any]:
    if workflow_id == "vc_lead_scraper":
        examples = project.get("input_examples", "")
        must_include = _extract_list(examples, "Must include")
        exclude = _extract_list(examples, "Exclude")
        return {
            "project_context": (
                _extract_value(examples, "Project context")
                or project.get("client_context")
                or project.get("goal")
                or ""
            ),
            "target_profile": (
                _extract_value(examples, "Target profile")
                or "European student-run VC funds and early-stage funds relevant to ASIF benchmarking"
            ),
            "geography": _extract_value(examples, "Geography") or "Europe",
            "lead_count": _extract_value(examples, "Lead count") or "10",
            "must_include": must_include or [
                "student-run VC",
                "early-stage VC",
                "fund performance metrics",
                "portfolio monitoring",
                "public contact route",
                "official website",
            ],
            "exclude": exclude or ["ASIF Ventures", "LinkedIn source URLs", "pure databases"],
        }
    return {}


def default_eval_rules(project: dict[str, Any], workflow_id: str | None) -> dict[str, Any]:
    text = f"{project.get('working_definition', '')}\n{project.get('output_examples', '')}".lower()
    rules: dict[str, Any] = {
        "output_required": True,
    }

    if "csv" in text:
        rules["expected_format"] = "csv"
        columns = _extract_columns(project.get("output_examples", ""))
        if columns:
            rules["required_columns"] = columns
        count = _extract_exact_row_count(project.get("input_examples", ""), project.get("output_examples", ""))
        if count:
            rules["exact_row_count"] = count

    if workflow_id == "vc_lead_scraper":
        rules.update({
            "expected_format": "csv",
            "required_columns": [
                "priority_rank",
                "fund_name",
                "website",
                "geography",
                "fund_type",
                "fit_score",
                "route_quality",
                "contact_name",
                "contact_role",
                "contact_confidence",
                "email",
                "email_status",
                "contact_method",
                "contact_url",
                "evidence_url",
                "evidence_summary",
                "outreach_angle",
                "suggested_subject",
                "validation_status",
                "validation_flags",
            ],
            "exact_row_count": 10,
            "forbidden_terms": {
                "fields": ["fund_name", "website", "evidence_url"],
                "terms": ["asif"],
            },
            "forbidden_url_types": {
                "evidence_url": ["linkedin.com/company", "linkedin.com/in"],
            },
            "allowed_enums": {
                "email_status": ["verified", "unavailable", "provider_unavailable"],
                "route_quality": ["A", "B", "C", "D"],
                "validation_status": ["usable", "needs_review", "blocked"],
            },
            "route_check": {
                "email_field": "email",
                "method_field": "contact_method",
                "url_field": "contact_url",
                "website_field": "website",
                "allowed_methods": ["email_direct", "contact_form", "website", "warm_intro_needed"],
            },
            "no_fake_emails": {
                "email_field": "email",
                "confidence_field": "email_status",
                "verified_confidences": ["verified"],
            },
        })

    if workflow_id == "vc_outreach_drafts":
        rules.update({
            "output_required": True,
            "markdown_sections_required": [
                "Email Channel",
                "LinkedIn Channel",
                "First Touch",
                "Follow-Up",
                "DM (send after connection accepted)",
            ],
            "forbidden_terms": {
                "fields": [],
                "terms": ["ai-os", "claude", "[draft generation failed"],
            },
        })

    return rules


def merge_rules(defaults: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    if not overrides:
        return defaults
    merged = dict(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def execute_workflow_for_project(
    workflow_id: str,
    inputs: dict[str, Any],
    client: str | None = None,
) -> tuple[str, dict[str, Any], int | None]:
    meta = get_workflow(workflow_id)
    if not meta:
        raise ValueError(f"Workflow '{workflow_id}' not found")
    fn = load_entry_function(meta)

    token = _client_kb_root.set(get_client_kb_root(client))
    try:
        result = run_workflow(fn, workflow_id=workflow_id, **inputs)
    finally:
        _client_kb_root.reset(token)

    recent = get_runs(workflow_id=workflow_id, limit=1)
    run_id = recent[0]["id"] if recent else None
    if result.get("status") != "success":
        raise RuntimeError(result.get("error") or "Workflow run failed")

    output = result.get("result") or {}
    output_ref = {
        "source": "workflow_run",
        "workflow_id": workflow_id,
        "run_id": run_id,
        "file_path": output.get("file_path"),
        "csv_file_path": output.get("csv_file_path"),
    }
    output_text = _output_text_from_result(output, output_ref)
    return output_text, output_ref, run_id


def resolve_existing_output(
    workflow_id: str | None,
    observed_output: str | None = None,
    output_path: str | None = None,
    latest_output_ref: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any], int | None]:
    if observed_output and observed_output.strip():
        return observed_output.strip(), {"source": "manual"}, None

    if output_path:
        path = _safe_existing_path(output_path)
        return _read_output_path(path), _path_ref(path, "selected_path"), None

    if latest_output_ref:
        ref_path = latest_output_ref.get("file_path") or latest_output_ref.get("path")
        if ref_path:
            try:
                path = _safe_existing_path(str(ref_path))
                return _read_output_path(path), _path_ref(path, "configured_latest"), latest_output_ref.get("run_id")
            except FileNotFoundError:
                pass

    if workflow_id:
        kb_match = _latest_kb_output(workflow_id)
        if kb_match:
            return _read_output_path(kb_match), _path_ref(kb_match, "knowledge_base_latest"), None

        run_match = _latest_run_output(workflow_id)
        if run_match:
            return run_match

    raise FileNotFoundError("No saved output found. Run the workflow once or choose an output to evaluate.")


def run_deterministic_checks(
    output_text: str,
    output_ref: dict[str, Any],
    rules: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    checks.append(_check(
        "output_exists",
        "Output exists",
        bool(output_text and output_text.strip()),
        "Output text is present." if output_text.strip() else "No output text was available.",
    ))

    needs_csv = bool(
        rules.get("expected_format") == "csv"
        or rules.get("required_columns")
        or rules.get("exact_row_count")
    )
    csv_text = _extract_csv_text(output_text, output_ref)
    csv_state: dict[str, Any] = {
        "csv_text": csv_text,
        "rows": [],
        "columns": [],
    }

    markdown_sections = rules.get("markdown_sections_required")
    if markdown_sections:
        missing_sections = [s for s in markdown_sections if s not in output_text]
        checks.append(_check(
            "markdown_sections_present",
            "Required markdown sections present",
            not missing_sections,
            "All required sections found." if not missing_sections else f"Missing sections: {', '.join(missing_sections)}",
        ))

    forbidden_terms = rules.get("forbidden_terms") or {}
    if forbidden_terms and not rules.get("expected_format") == "csv":
        terms = [str(t).lower() for t in forbidden_terms.get("terms", [])]
        hits = [t for t in terms if t and t in output_text.lower()]
        checks.append(_check(
            "forbidden_terms_absent_in_output",
            "Forbidden terms absent from output",
            not hits,
            "No forbidden terms found." if not hits else f"Found forbidden terms: {', '.join(hits)}",
        ))

    if needs_csv:
        rows, columns, error = _parse_csv(csv_text)
        csv_state.update({"rows": rows, "columns": columns, "error": error})
        checks.append(_check(
            "csv_parses",
            "CSV parses",
            error is None and bool(columns),
            f"Parsed {len(rows)} CSV rows." if error is None and columns else f"CSV parse failed: {error or 'no CSV found'}",
        ))

        if rules.get("required_columns"):
            required = [str(column) for column in rules["required_columns"]]
            missing = [column for column in required if column not in columns]
            checks.append(_check(
                "required_columns",
                "Required columns present",
                not missing,
                "All required columns are present." if not missing else f"Missing columns: {', '.join(missing)}",
            ))

        if rules.get("exact_row_count") is not None:
            expected = int(rules["exact_row_count"])
            checks.append(_check(
                "exact_row_count",
                "Exact row count",
                len(rows) == expected,
                f"Found exactly {expected} rows." if len(rows) == expected else f"Expected {expected} rows, found {len(rows)}.",
            ))

        checks.extend(_row_checks(rows, columns, rules))

    return checks, csv_state


def summarize_check_counts(checks: list[dict[str, Any]]) -> tuple[int, int]:
    total = len(checks)
    passed = sum(1 for check in checks if check.get("passed"))
    return passed, total


def _row_checks(rows: list[dict[str, str]], columns: list[str], rules: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    forbidden_terms = rules.get("forbidden_terms") or {}
    if forbidden_terms:
        fields = forbidden_terms.get("fields") or columns
        terms = [str(term).lower() for term in forbidden_terms.get("terms", [])]
        hits = []
        for idx, row in enumerate(rows, start=1):
            for field in fields:
                value = str(row.get(field, "")).lower()
                for term in terms:
                    if term and term in value:
                        hits.append(f"row {idx} {field} contains '{term}'")
        checks.append(_check(
            "forbidden_terms_absent",
            "Forbidden terms absent",
            not hits,
            "No forbidden terms found in configured fields." if not hits else "; ".join(hits[:6]),
        ))

    forbidden_urls = rules.get("forbidden_url_types") or {}
    if forbidden_urls:
        hits = []
        for field, patterns in forbidden_urls.items():
            lowered_patterns = [str(pattern).lower() for pattern in patterns]
            for idx, row in enumerate(rows, start=1):
                value = str(row.get(field, "")).lower()
                if any(pattern and pattern in value for pattern in lowered_patterns):
                    hits.append(f"row {idx} {field}: {row.get(field, '')}")
        checks.append(_check(
            "forbidden_url_types_absent",
            "Forbidden URL types absent",
            not hits,
            "No forbidden URL types found." if not hits else "; ".join(hits[:6]),
        ))

    allowed_enums = rules.get("allowed_enums") or {}
    for field, allowed in allowed_enums.items():
        allowed_values = {str(value) for value in allowed}
        invalid = [
            f"row {idx}: {row.get(field, '') or '<blank>'}"
            for idx, row in enumerate(rows, start=1)
            if str(row.get(field, "")) not in allowed_values
        ]
        checks.append(_check(
            f"allowed_enum_{field}",
            f"{field} uses allowed values",
            not invalid,
            f"All {field} values are allowed." if not invalid else "; ".join(invalid[:8]),
        ))

    route_rule = rules.get("route_check")
    if route_rule:
        checks.append(_route_check(rows, route_rule))

    prefixes = [str(prefix).lower() for prefix in rules.get("forbidden_empty_column_prefixes", [])]
    if prefixes:
        checks.extend(_empty_column_prefix_checks(rows, columns, prefixes))

    email_rule = rules.get("no_fake_emails")
    if email_rule:
        checks.append(_email_quality_check(rows, email_rule))

    return checks


def _route_check(rows: list[dict[str, str]], rule: dict[str, Any]) -> dict[str, Any]:
    email_field = rule.get("email_field", "email")
    method_field = rule.get("method_field", "contact_method")
    url_field = rule.get("url_field", "contact_url")
    website_field = rule.get("website_field", "website")
    allowed_methods = {str(method).lower() for method in rule.get("allowed_methods", [])}
    failures = []
    for idx, row in enumerate(rows, start=1):
        email = str(row.get(email_field, "")).strip()
        method = str(row.get(method_field, "")).strip().lower()
        route_url = str(row.get(url_field, "")).strip()
        website = str(row.get(website_field, "")).strip()
        has_route = bool(email)
        has_route = has_route or (method in allowed_methods and (method != "email_direct" or bool(email)))
        has_route = has_route or bool(route_url and method in {"contact_form", "website", "warm_intro_needed"})
        has_route = has_route or bool(website and method in {"website", "warm_intro_needed"})
        if not has_route:
            failures.append(f"row {idx} has no email, contact form, website route, or warm_intro_needed")
    return _check(
        "required_route_fields_present",
        "Required route/contact fields present",
        not failures,
        "Every row has an actionable route." if not failures else "; ".join(failures[:8]),
    )


def _empty_column_prefix_checks(rows: list[dict[str, str]], columns: list[str], prefixes: list[str]) -> list[dict[str, Any]]:
    checks = []
    for prefix in prefixes:
        matched = [column for column in columns if column.lower().startswith(prefix)]
        if not matched:
            checks.append(_check(
                f"no_dead_{prefix}_columns",
                f"No dead {prefix} columns",
                True,
                f"No {prefix} columns are present.",
            ))
            continue
        has_data = any(
            _meaningful_provider_value(row.get(column, ""))
            for row in rows
            for column in matched
        )
        checks.append(_check(
            f"no_dead_{prefix}_columns",
            f"No dead {prefix} columns",
            has_data,
            (
                f"{prefix} columns contain provider data."
                if has_data
                else f"{prefix} columns are present but contain no provider data."
            ),
        ))
    return checks


def _email_quality_check(rows: list[dict[str, str]], rule: dict[str, Any]) -> dict[str, Any]:
    email_field = rule.get("email_field", "email")
    confidence_field = rule.get("confidence_field", "email_confidence")
    verified_confidences = {str(value) for value in rule.get("verified_confidences", [])}
    failures = []
    fake_markers = {"example.com", "test.com", "fake", "placeholder", "noreply@", "no-reply@"}
    email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    for idx, row in enumerate(rows, start=1):
        email = str(row.get(email_field, "")).strip()
        confidence = str(row.get(confidence_field, "")).strip()
        if confidence == "not_found" and email:
            failures.append(f"row {idx} has email with not_found confidence")
        if confidence in verified_confidences and not email:
            failures.append(f"row {idx} has {confidence} without an email")
        if not email:
            continue
        lowered = email.lower()
        if not email_pattern.match(email):
            failures.append(f"row {idx} has invalid email syntax: {email}")
        if any(marker in lowered for marker in fake_markers):
            failures.append(f"row {idx} has placeholder-like email: {email}")

    return _check(
        "no_fake_hallucinated_emails",
        "No fake or contradictory emails",
        not failures,
        "Email fields are syntactically plausible and consistent with confidence labels." if not failures else "; ".join(failures[:8]),
    )


def _check(key: str, label: str, passed: bool, details: str, severity: str = "error") -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "passed": passed,
        "details": details,
        "severity": severity,
    }


def _extract_csv_text(output_text: str, output_ref: dict[str, Any]) -> str:
    csv_path = output_ref.get("csv_file_path") or output_ref.get("csv_path")
    if csv_path:
        try:
            return _safe_existing_path(str(csv_path)).read_text(encoding="utf-8")
        except FileNotFoundError:
            pass

    fence = re.search(r"```csv\s*(.*?)```", output_text, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        return fence.group(1).strip()

    lines = [line for line in output_text.splitlines() if line.strip()]
    if lines and "," in lines[0]:
        return "\n".join(lines)
    return ""


def _parse_csv(csv_text: str) -> tuple[list[dict[str, str]], list[str], str | None]:
    if not csv_text.strip():
        return [], [], "no CSV content found"
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = [dict(row) for row in reader]
        columns = list(reader.fieldnames or [])
        if not columns:
            return [], [], "CSV has no header row"
        return rows, columns, None
    except Exception as e:
        return [], [], str(e)


def _output_text_from_result(output: dict[str, Any], output_ref: dict[str, Any]) -> str:
    for key in ("file_path", "path"):
        if output.get(key):
            try:
                return _safe_existing_path(str(output[key])).read_text(encoding="utf-8")
            except FileNotFoundError:
                pass
    for key in ("brief", "markdown", "report", "content", "summary", "body", "email", "csv", "output", "result"):
        value = output.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(output, indent=2, default=str)


def _latest_run_output(workflow_id: str) -> tuple[str, dict[str, Any], int | None] | None:
    for run in get_runs(workflow_id=workflow_id, limit=20):
        if run.get("status") != "success" or not run.get("outputs_json"):
            continue
        try:
            output = json.loads(run["outputs_json"])
        except Exception:
            continue
        output_ref = {
            "source": "run_history",
            "workflow_id": workflow_id,
            "run_id": run["id"],
            "file_path": output.get("file_path"),
            "csv_file_path": output.get("csv_file_path"),
        }
        return _output_text_from_result(output, output_ref), output_ref, run["id"]
    return None


def _latest_kb_output(workflow_id: str) -> Path | None:
    patterns = {
        "vc_lead_scraper": "outreach/vc_leads_*.md",
    }
    pattern = patterns.get(workflow_id)
    if not pattern:
        return None
    matches = [path for path in KB.glob(pattern) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _read_output_path(path: Path) -> str:
    if path.suffix.lower() == ".csv":
        return path.read_text(encoding="utf-8")
    return path.read_text(encoding="utf-8")


def _path_ref(path: Path, source: str) -> dict[str, Any]:
    ref = {
        "source": source,
        "file_path": str(path),
        "path": str(path),
    }
    csv_path = path.with_suffix(".csv")
    if csv_path.exists():
        ref["csv_file_path"] = str(csv_path)
        ref["csv_path"] = str(csv_path)
    return ref


def _safe_existing_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / raw_path
    path = path.resolve()
    allowed_roots = [
        (ROOT / "knowledge_base").resolve(),
        (ROOT / "clients").resolve(),
    ]
    if not any(_is_relative_to(path, root) for root in allowed_roots):
        raise FileNotFoundError(str(path))
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(str(path))
    return path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _extract_value(text: str, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}\s*:\s*(.+)", flags=re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _extract_list(text: str, label: str) -> list[str]:
    value = _extract_value(text, label)
    if not value:
        return []
    return [item.strip(" .") for item in re.split(r",|\n", value) if item.strip()]


def _extract_columns(text: str) -> list[str]:
    match = re.search(r"columns?\s*:\s*([^\n.]+)", text, flags=re.IGNORECASE)
    if not match:
        return []
    return [column.strip().strip("`") for column in match.group(1).split(",") if column.strip()]


def _extract_exact_row_count(*texts: str) -> int | None:
    combined = "\n".join(texts)
    for pattern in (r"lead count\s*:\s*(\d+)", r"exactly\s+(\d+)", r"csv with\s+(\d+)"):
        match = re.search(pattern, combined, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _meaningful_provider_value(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    ignored = {
        "false",
        "none",
        "null",
        "not_found",
        "not_attempted",
        "no_email_returned",
        "http_403",
        "http_429_error",
        "error",
    }
    return text not in ignored

"""
Automation project planner
--------------------------
Builds a deterministic v1 execution package for Claude Code / Codex handoff.
This is intentionally cheap and predictable; an LLM planner can replace or
augment this later without changing the project data model.
"""

from __future__ import annotations

import json
from typing import Any

from core.reliability import load_error_playbook


def readiness_check(project: dict[str, Any], repo_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [
        {
            "key": "outcome_clear",
            "label": "Outcome is clear",
            "passed": bool(project.get("goal", "").strip() and project.get("working_definition", "").strip()),
            "reason": "Goal and working definition are present.",
        },
        {
            "key": "repo_path_chosen",
            "label": "Repo path is chosen",
            "passed": bool(project.get("chosen_repo_url")),
            "reason": "A chosen repo URL is set." if project.get("chosen_repo_url") else "Add candidate repos and choose one, or mark this as from-scratch.",
        },
        {
            "key": "build_plan_actionable",
            "label": "Build plan is actionable",
            "passed": bool(project.get("current_process", "").strip()),
            "reason": "Current process/pain is documented.",
        },
        {
            "key": "basic_test_defined",
            "label": "Basic test is defined",
            "passed": bool(project.get("working_definition", "").strip()),
            "reason": "The working definition can be used as the first acceptance test.",
        },
        {
            "key": "examples_present",
            "label": "Examples are captured",
            "passed": bool(project.get("input_examples", "").strip() and project.get("output_examples", "").strip()),
            "reason": "Sample inputs and expected outputs make the build easier to verify.",
        },
    ]
    score = sum(1 for check in checks if check["passed"])
    return {
        "score": score,
        "checks": checks,
        "repo_candidate_count": len(repo_candidates),
        "risk_label": "Ready" if score >= 4 else "Risky",
    }


def generate_execution_package(
    project: dict[str, Any],
    repo_candidates: list[dict[str, Any]],
    agent_updates: list[dict[str, Any]] | None = None,
    eval_cases: list[dict[str, Any]] | None = None,
    eval_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    agent_updates = agent_updates or []
    eval_cases = eval_cases or []
    eval_runs = eval_runs or []
    readiness = readiness_check(project, repo_candidates)
    chosen_repo = project.get("chosen_repo_url") or "Not chosen yet"
    client_context = project.get("client_context") or "Not captured yet."
    required_tools = project.get("required_tools") or "Not captured yet."
    input_examples = project.get("input_examples") or "Not captured yet."
    output_examples = project.get("output_examples") or "Not captured yet."
    safe_repo_candidates = [repo for repo in repo_candidates if not _repo_intelligence_is_unsafe(repo)]
    package_repo_candidates = safe_repo_candidates or repo_candidates
    candidate_lines = _format_repo_candidate_lines(package_repo_candidates)
    intelligence_lines = _format_repo_intelligence(repo_candidates)
    update_lines = _format_agent_updates(agent_updates)
    eval_lines = _format_eval_cases(eval_cases)
    eval_harness_lines = _format_eval_harness_runs(eval_runs)
    reliability_lines = load_error_playbook()
    latest_eval = _latest_eval_signal(eval_cases)
    latest_output_ref = _latest_output_ref(eval_runs)
    deterministic_failures = _latest_deterministic_failures(eval_runs)
    next_recommended_task = _next_recommended_task(agent_updates, latest_eval, readiness)

    score = readiness["score"]
    total = len(readiness["checks"])
    risk_note = (
        "This package is ready to send to an IDE agent."
        if score >= 4
        else "This package can still be used, but it is risky. Fill the missing readiness checks before expecting reliable implementation."
    )
    repo_direction = (
        f"Inspect first: {project['chosen_repo_url']}"
        if project.get("chosen_repo_url")
        else "No repo chosen yet. First inspect the repo candidates below and recommend the best path (use as-is, fork, use as reference, or build from scratch)."
    )

    content = f"""# Execution Package: {project['name']}

## Continuation Context
- Project ID: {project['id']}
- Owner type: {project['owner_type']}
- Status: {project['status']}
- Goal: {project['goal']}
- Chosen repo: {chosen_repo}
- Current process/pain: {project['current_process']}
- Working definition: {project['working_definition']}
- Client context: {client_context}
- Required tools/APIs/data: {required_tools}
- Latest output reference: {latest_output_ref}
- Latest eval score: {_format_latest_eval_inline(latest_eval)}
- Deterministic check failures: {deterministic_failures}
- Next task: {next_recommended_task}
- Known blockers: unresolved repo fit, failed deterministic checks, missing environment details, and unknown test commands until the repo is inspected.

## Latest Agent Updates
{update_lines}

## Latest Eval Signals
{eval_lines}

## Latest Eval Harness Context
{eval_harness_lines}

## Repo Intelligence Findings
{intelligence_lines}

## Reliability Playbook
{reliability_lines}

## Readiness Check
Score: {score}/{total}

{_format_readiness(readiness)}

{risk_note}

## Implementation Plan
1. Final outcome: {project['goal']}
2. Observable success condition: {project['working_definition']}
3. Current process this replaces: {project['current_process']}
4. Client/business context: {client_context}
5. Required tools/APIs/data: {required_tools}
6. Smallest implementation slice: inspect the chosen repo, identify the core function, implement one working end-to-end path that satisfies the working definition.
7. Verification: confirm the working definition and examples are met before expanding scope.
8. Failure modes: vague outcome, poor repo choice, agent loses context, no test command, automation works once but is not repeatable.
9. Next: use the Claude Code and Codex prompts below.

## Automation Spec
Inputs/examples:
{input_examples}

Expected outputs/examples:
{output_examples}

## Repo Hunt Brief
Look for GitHub repos that already contain the closest working version of this automation or dashboard pattern.

Search for:
- the main workflow described by: {project['goal']}
- dashboards or admin panels for this domain
- integrations for the APIs/tools likely needed by the automation
- template repos with clear setup, tests, and recent maintenance

Good signs:
- clear README and setup commands
- recent commits or active issues
- permissive license
- existing tests or examples
- simple architecture that an IDE agent can modify

Red flags:
- abandoned repo
- unclear license
- heavy infrastructure before the core workflow works
- no local setup instructions
- hard-coded SaaS assumptions that block client/self-hosted use

Paste 1-5 candidate URLs back into this project.

## Repo Candidates
{candidate_lines}

## Repo Choice Notes
Chosen repo: {chosen_repo}

If no repo is chosen yet, ask Claude Code to inspect the candidates and recommend: use repo, fork repo, use as reference only, or build from scratch.

## Claude Code Prompt
You are the primary implementation agent for this automation project.

{repo_direction}

Context:
- Goal: {project['goal']}
- Working definition: {project['working_definition']}
- Current process/pain: {project['current_process']}
- Client context: {client_context}
- Required tools/APIs/data: {required_tools}
- Chosen repo: {chosen_repo}
- Repo candidates:
{candidate_lines}
- Repo Intelligence findings:
{intelligence_lines}
- Input examples:
{input_examples}
- Expected output examples:
{output_examples}
- Latest agent updates:
{update_lines}
- Eval signals:
{eval_lines}
- Eval harness:
{eval_harness_lines}
- Reliability playbook:
{reliability_lines}

Your job:
1. Inspect the repo structure before editing.
2. Identify the smallest implementation slice that proves the automation can work.
3. Produce a concise plan with files likely to change.
4. Implement the slice.
5. Run the relevant checks/tests if available.
6. Report changed files, commands run, failures, and the next recommended step.

Constraints:
- Preserve existing behavior unless the task requires changing it.
- Keep the first version small and verifiable.
- If the repo is a bad fit, stop and explain the better path instead of forcing edits.
- Write your final response so Codex can continue without hidden chat history.

## Codex Prompt
You are the review, continuation, and optimization agent for this automation project.

Context:
- Goal: {project['goal']}
- Working definition: {project['working_definition']}
- Chosen repo: {chosen_repo}
- Repo Intelligence findings:
{intelligence_lines}
- Client context: {client_context}
- Required tools/APIs/data: {required_tools}
- Input examples: {input_examples}
- Expected output examples: {output_examples}
- Latest package readiness: {score}/{total}
- Latest agent updates:
{update_lines}
- Latest eval signals:
{eval_lines}
- Latest eval harness:
{eval_harness_lines}
- Reliability playbook:
{reliability_lines}

Review tasks:
1. Check whether the implementation actually satisfies the working definition.
2. Find missing tests, brittle assumptions, unclear state, and repo-fit problems.
3. Recommend the smallest fixes that increase reliability.
4. If Claude Code ran out of credits, continue from the package context and the latest changed-file summary.
5. Produce a handoff response with exact next steps and verification commands.

## Task Split
- Claude Code: repo inspection, first implementation, local verification, changed-file summary.
- Codex: review, tests/evals, failure-mode analysis, continuation if Claude Code runs out.
- Dashboard/user: paste agent results back into the project and generate the next package version.

## Basic Test Plan
Minimum proof: {project['working_definition']}

Use the captured input/output examples as acceptance fixtures:
- Inputs/examples: {input_examples}
- Expected outputs/examples: {output_examples}

Ask the IDE agent to identify the repo's actual test command. If none exists, create a manual verification checklist and one lightweight automated check where practical.
"""

    return {
        "title": f"{project['name']} execution package",
        "content_md": content,
        "readiness_score": score,
        "readiness": readiness,
    }


def _format_readiness(readiness: dict[str, Any]) -> str:
    lines = []
    for check in readiness["checks"]:
        mark = "PASS" if check["passed"] else "TODO"
        lines.append(f"- [{mark}] {check['label']}: {check['reason']}")
    return "\n".join(lines)


def _format_agent_updates(agent_updates: list[dict[str, Any]]) -> str:
    if not agent_updates:
        return "- No agent updates pasted yet."

    lines = []
    for update in agent_updates[:5]:
        lines.append(f"- {update.get('agent', 'agent')} at {update.get('created_at', 'unknown time')}")
        if update.get("summary"):
            lines.append(f"  Summary: {update['summary']}")
        if update.get("changed_files"):
            lines.append(f"  Changed files: {update['changed_files']}")
        if update.get("commands_run"):
            lines.append(f"  Commands run: {update['commands_run']}")
        if update.get("test_result"):
            lines.append(f"  Test result: {update['test_result']}")
        if update.get("blockers"):
            lines.append(f"  Blockers: {update['blockers']}")
        if update.get("next_step"):
            lines.append(f"  Next step: {update['next_step']}")
    return "\n".join(lines)


def _format_repo_intelligence(repo_candidates: list[dict[str, Any]]) -> str:
    enriched = [
        repo for repo in repo_candidates
        if repo.get("fit_score") is not None or repo.get("recommendation") or repo.get("analysis_json")
    ]
    if not enriched:
        return "- No Repo Intelligence findings yet. Run discovery before build when open-source precedent could improve quality."

    lines = []
    usable = [repo for repo in enriched if not _repo_intelligence_is_unsafe(repo)]
    selected = usable or enriched
    for repo in sorted(selected, key=lambda item: (-(item.get("fit_score") or 0), item.get("rank") or 999))[:3]:
        analysis = _parse_analysis(repo.get("analysis_json"))
        score = repo.get("fit_score")
        rec = repo.get("recommendation") or "inspect"
        meta = []
        if repo.get("language"):
            meta.append(repo["language"])
        if repo.get("stars") is not None:
            meta.append(f"{repo['stars']} stars")
        if repo.get("license"):
            meta.append(f"license {repo['license']}")
        lines.append(f"- {repo['url']} — {score}/100, {rec}" + (f" ({', '.join(meta)})" if meta else ""))
        reusable = analysis.get("reusable_patterns") or []
        useful_files = analysis.get("useful_files") or []
        risks = analysis.get("risks") or []
        if reusable:
            lines.append(f"  Reuse: {'; '.join(reusable[:4])}")
        if useful_files:
            lines.append(f"  Inspect: {'; '.join(useful_files[:4])}")
        if risks:
            lines.append(f"  Risks: {'; '.join(risks[:3])}")
        if analysis.get("notes"):
            lines.append(f"  Note: {analysis['notes']}")
    return "\n".join(lines)


def _format_repo_candidate_lines(repo_candidates: list[dict[str, Any]]) -> str:
    if not repo_candidates:
        return "- No candidate repos pasted yet."
    return "\n".join(
        f"- {repo['url']}" + (f" - {repo.get('notes')}" if repo.get("notes") else "")
        for repo in repo_candidates
    )


def _repo_intelligence_is_unsafe(repo: dict[str, Any]) -> bool:
    analysis = _parse_analysis(repo.get("analysis_json"))
    haystack = " ".join([
        str(repo.get("url", "")),
        str(repo.get("notes", "")),
        str(repo.get("recommendation", "")),
        " ".join(analysis.get("risks") or []),
    ]).lower()
    if repo.get("recommendation") == "avoid":
        return True
    if "linkedin" in haystack and ("scraping" in haystack or "account" in haystack or "cookie" in haystack):
        return True
    return False


def _parse_analysis(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _format_eval_cases(eval_cases: list[dict[str, Any]]) -> str:
    if not eval_cases:
        return "- No eval cases yet. Add golden cases before trusting this automation with a client."

    lines = []
    for case in eval_cases[:5]:
        lines.append(f"- Eval: {case.get('name', 'Untitled eval')}")
        if case.get("criteria"):
            lines.append(f"  Criteria: {case['criteria']}")
        results = case.get("results") or []
        if results:
            latest = results[0]
            lines.append(f"  Latest score: {latest.get('score')}/100 ({latest.get('verdict')})")
            if latest.get("reasoning"):
                lines.append(f"  Reasoning: {latest['reasoning']}")
            if latest.get("improvement_prompt"):
                lines.append(f"  Next improvement: {latest['improvement_prompt']}")
        else:
            lines.append("  Latest score: not run yet")
    return "\n".join(lines)


def _format_eval_harness_runs(eval_runs: list[dict[str, Any]]) -> str:
    if not eval_runs:
        return "- Eval harness has not run yet. Run Project Run + Evaluate before using this as a build handoff."

    latest = eval_runs[0]
    output_ref = _parse_json(latest.get("output_ref_json"), {})
    checks = _parse_json(latest.get("deterministic_checks_json"), [])
    failed = [check for check in checks if not check.get("passed")]
    lines = [
        f"- Latest harness run: {latest.get('created_at', 'unknown time')} ({latest.get('status', 'unknown')})",
        f"- Workflow: {latest.get('workflow_id') or 'not selected'}",
        f"- Output reference: {_format_output_ref(output_ref)}",
        f"- Deterministic checks: {latest.get('deterministic_passed', 0)}/{latest.get('deterministic_total', len(checks))} passed",
    ]
    if latest.get("workflow_run_id"):
        lines.append(f"- Workflow run ID: {latest['workflow_run_id']}")
    if latest.get("eval_result_id"):
        lines.append(f"- Eval result ID: {latest['eval_result_id']}")
    if failed:
        lines.append("- Failed checks:")
        for check in failed[:8]:
            lines.append(f"  - {check.get('label', check.get('key'))}: {check.get('details', '')}")
    else:
        lines.append("- Failed checks: none")
    if latest.get("error"):
        lines.append(f"- Harness error: {latest['error']}")
    return "\n".join(lines)


def _latest_eval_signal(eval_cases: list[dict[str, Any]]) -> dict[str, Any] | None:
    results = []
    for case in eval_cases:
        for result in case.get("results") or []:
            results.append({**result, "case_name": case.get("name", "Untitled eval")})
    if not results:
        return None
    return sorted(results, key=lambda item: item.get("created_at", ""), reverse=True)[0]


def _format_latest_eval_inline(latest_eval: dict[str, Any] | None) -> str:
    if not latest_eval:
        return "not run yet"
    return (
        f"{latest_eval.get('score')}/100 ({latest_eval.get('verdict')}) "
        f"on {latest_eval.get('case_name', 'eval')}"
    )


def _latest_output_ref(eval_runs: list[dict[str, Any]]) -> str:
    if not eval_runs:
        return "not captured yet"
    output_ref = _parse_json(eval_runs[0].get("output_ref_json"), {})
    return _format_output_ref(output_ref)


def _latest_deterministic_failures(eval_runs: list[dict[str, Any]]) -> str:
    if not eval_runs:
        return "not checked yet"
    checks = _parse_json(eval_runs[0].get("deterministic_checks_json"), [])
    failed = [check for check in checks if not check.get("passed")]
    if not failed:
        return "none"
    return "; ".join(f"{check.get('label', check.get('key'))}: {check.get('details', '')}" for check in failed[:5])


def _next_recommended_task(
    agent_updates: list[dict[str, Any]],
    latest_eval: dict[str, Any] | None,
    readiness: dict[str, Any],
) -> str:
    if latest_eval and latest_eval.get("improvement_prompt"):
        return latest_eval["improvement_prompt"]
    for update in agent_updates:
        if update.get("next_step"):
            return update["next_step"]
    for check in readiness.get("checks", []):
        if not check.get("passed"):
            return f"Resolve readiness gap: {check.get('label')} - {check.get('reason')}"
    return "Run the harness again after the next code change, then package the updated score and checks."


def _format_output_ref(output_ref: dict[str, Any]) -> str:
    if not output_ref:
        return "not captured yet"
    path = output_ref.get("file_path") or output_ref.get("path")
    csv_path = output_ref.get("csv_file_path") or output_ref.get("csv_path")
    run_id = output_ref.get("run_id")
    parts = []
    if path:
        parts.append(str(path))
    if csv_path:
        parts.append(f"CSV: {csv_path}")
    if run_id:
        parts.append(f"run #{run_id}")
    if not parts and output_ref.get("source"):
        parts.append(str(output_ref["source"]))
    return " | ".join(parts) if parts else "not captured yet"


def _parse_json(raw: Any, default: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default

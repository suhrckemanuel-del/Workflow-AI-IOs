import json
import re

from fastapi import APIRouter, HTTPException

from api.models import (
    AutomationProject,
    AutomationProjectCreate,
    AutomationProjectUpdate,
    RepoCandidate,
    RepoCandidateCreate,
    ExecutionPackage,
    AgentUpdate,
    AgentUpdateCreate,
    EvalCase,
    EvalCaseCreate,
    EvalResult,
    EvalRunRequest,
    ProjectEvalConfig,
    ProjectEvalConfigUpdate,
    ProjectEvalRun,
    ProjectRunAndEvaluateRequest,
    ProjectRunAndEvaluateResponse,
    GeneratePackageRequest,
    ReliabilityIssue,
    ReliabilityPlaybookResponse,
)
from core.automation_planner import generate_execution_package
from core.evaluator import judge_output
from core.repo_intelligence import discover_repo_candidates
from core.reliability import PLAYBOOK_PATH, load_error_playbook
from api.services.eval_harness import (
    default_eval_rules,
    default_project_inputs,
    execute_workflow_for_project,
    infer_project_workflow_id,
    merge_rules,
    resolve_existing_output,
    run_deterministic_checks,
    summarize_check_counts,
)
from api.services.eval_logger import append_eval_history
from core.db import (
    add_repo_candidate,
    create_automation_project,
    create_execution_package,
    create_agent_update,
    create_eval_case,
    create_project_eval_run,
    create_eval_result,
    delete_repo_candidate,
    delete_eval_case,
    get_eval_case,
    get_automation_project,
    get_project_eval_config,
    list_eval_cases,
    list_eval_results,
    list_project_eval_runs,
    list_agent_updates,
    list_automation_projects,
    list_execution_packages,
    list_repo_candidates,
    update_automation_project,
    upsert_project_eval_config,
)

router = APIRouter()


def _parse_playbook_issues(content: str, project: dict | None = None) -> list[ReliabilityIssue]:
    sections = re.split(r"\n(?=## \d+\.\s+)", content)
    project_text = " ".join(
        str(project.get(key, ""))
        for key in ("name", "goal", "current_process", "working_definition", "required_tools")
    ).lower() if project else ""
    tokens = {token for token in re.findall(r"[a-z0-9]+", project_text) if len(token) > 3}

    parsed: list[tuple[int, int, ReliabilityIssue]] = []
    for index, section in enumerate(sections):
        title_match = re.search(r"^## \d+\.\s+(.+)$", section, re.MULTILINE)
        if not title_match:
            continue
        title = title_match.group(1).strip()
        symptom = _extract_playbook_block(section, "Symptom")
        fast_fix = _extract_playbook_block(section, "Fast Fix")
        haystack = f"{title} {symptom} {fast_fix}".lower()
        score = sum(1 for token in tokens if token in haystack)
        parsed.append((score, -index, ReliabilityIssue(title=title, symptom=symptom, fast_fix=fast_fix)))

    parsed.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [issue for _, _, issue in parsed[:5]]


def _extract_playbook_block(section: str, heading: str) -> str:
    marker = f"**{heading}**"
    start = section.find(marker)
    if start == -1:
        return ""
    rest = section[start + len(marker):].strip()
    next_heading = rest.find("\n**")
    block = rest if next_heading == -1 else rest[:next_heading]
    lines = [
        line.removeprefix("- ").strip()
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("```")
    ]
    return " ".join(lines[:2])


def _package(row: dict) -> ExecutionPackage:
    data = dict(row)
    data["readiness"] = json.loads(data.pop("readiness_json"))
    return ExecutionPackage(**data)


def _eval_result(row: dict) -> EvalResult:
    return EvalResult(**row)


def _json_field(row: dict, key: str, default):
    raw = row.get(key)
    if raw in (None, ""):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def _eval_config(row: dict | None) -> ProjectEvalConfig | None:
    if not row:
        return None
    return ProjectEvalConfig(
        project_id=row["project_id"],
        workflow_id=row.get("workflow_id"),
        eval_case_id=row.get("eval_case_id"),
        input_json=_json_field(row, "input_json", {}),
        deterministic_rules=_json_field(row, "deterministic_rules_json", {}),
        latest_output_ref=_json_field(row, "latest_output_ref_json", {}),
        updated_at=row.get("updated_at", ""),
    )


def _eval_run(row: dict) -> ProjectEvalRun:
    return ProjectEvalRun(
        id=row["id"],
        project_id=row["project_id"],
        workflow_id=row.get("workflow_id"),
        eval_case_id=row.get("eval_case_id"),
        workflow_run_id=row.get("workflow_run_id"),
        eval_result_id=row.get("eval_result_id"),
        output_ref=_json_field(row, "output_ref_json", {}),
        deterministic_checks=_json_field(row, "deterministic_checks_json", []),
        deterministic_passed=row["deterministic_passed"],
        deterministic_total=row["deterministic_total"],
        status=row["status"],
        error=row.get("error"),
        created_at=row["created_at"],
    )


def _eval_case(row: dict) -> EvalCase:
    return EvalCase(
        **row,
        results=[_eval_result(r) for r in list_eval_results(row["project_id"], row["id"])],
    )


def _project(row: dict) -> AutomationProject:
    return AutomationProject(
        **row,
        repo_candidates=[RepoCandidate(**r) for r in list_repo_candidates(row["id"])],
        execution_packages=[_package(p) for p in list_execution_packages(row["id"])],
        agent_updates=[AgentUpdate(**u) for u in list_agent_updates(row["id"])],
        eval_cases=[_eval_case(c) for c in list_eval_cases(row["id"])],
        eval_config=_eval_config(get_project_eval_config(row["id"])),
        eval_runs=[_eval_run(r) for r in list_project_eval_runs(row["id"])],
    )


def _require_project(project_id: int) -> dict:
    project = get_automation_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Automation project '{project_id}' not found")
    return project


@router.get("/automation-projects", response_model=list[AutomationProject])
def get_projects():
    return [_project(p) for p in list_automation_projects()]


@router.post("/automation-projects", response_model=AutomationProject)
def create_project(body: AutomationProjectCreate):
    project = create_automation_project(
        name=body.name,
        goal=body.goal,
        owner_type=body.owner_type,
        current_process=body.current_process,
        working_definition=body.working_definition,
        client_context=body.client_context,
        required_tools=body.required_tools,
        input_examples=body.input_examples,
        output_examples=body.output_examples,
    )
    return _project(project)


@router.get("/automation-projects/{project_id}", response_model=AutomationProject)
def get_project(project_id: int):
    return _project(_require_project(project_id))


@router.get("/automation-projects/{project_id}/reliability-playbook", response_model=ReliabilityPlaybookResponse)
def get_project_reliability_playbook(project_id: int):
    project = _require_project(project_id)
    content = load_error_playbook(limit_chars=20000)
    return ReliabilityPlaybookResponse(
        path=str(PLAYBOOK_PATH),
        content_md=content,
        issues=_parse_playbook_issues(content, project),
    )


@router.patch("/automation-projects/{project_id}", response_model=AutomationProject)
def update_project(project_id: int, body: AutomationProjectUpdate):
    _require_project(project_id)
    updates = body.model_dump(exclude_unset=True)
    project = update_automation_project(project_id, **updates)
    if not project:
        raise HTTPException(status_code=404, detail=f"Automation project '{project_id}' not found")
    return _project(project)


@router.post("/automation-projects/{project_id}/repo-candidates", response_model=AutomationProject)
def create_repo_candidate(project_id: int, body: RepoCandidateCreate):
    _require_project(project_id)
    add_repo_candidate(
        project_id=project_id,
        url=body.url,
        notes=body.notes,
        rank=body.rank,
        fit_score=body.fit_score,
        recommendation=body.recommendation,
        license=body.license,
        stars=body.stars,
        last_updated=body.last_updated,
        language=body.language,
        analysis_json=body.analysis_json,
    )
    return _project(_require_project(project_id))


@router.post("/automation-projects/{project_id}/repo-intelligence/search", response_model=AutomationProject)
def search_repo_intelligence(project_id: int):
    project = _require_project(project_id)
    findings = discover_repo_candidates(project)
    if not findings:
        raise HTTPException(status_code=502, detail="Repo Intelligence could not find usable repositories. Try tightening the goal or adding required tools.")
    existing_urls = {candidate["url"].rstrip("/").lower() for candidate in list_repo_candidates(project_id)}
    for finding in findings:
        if finding["url"].rstrip("/").lower() in existing_urls:
            continue
        add_repo_candidate(
            project_id=project_id,
            url=finding["url"],
            notes=finding["notes"],
            rank=finding["rank"],
            fit_score=finding["fit_score"],
            recommendation=finding["recommendation"],
            license=finding["license"],
            stars=finding["stars"],
            last_updated=finding["last_updated"],
            language=finding["language"],
            analysis_json=json.dumps(finding["analysis_json"], default=str),
        )
    current = _require_project(project_id)
    if current.get("status") in {"idea", "planned"}:
        update_automation_project(project_id, status="planned")
    return _project(_require_project(project_id))


@router.delete("/automation-projects/{project_id}/repo-candidates/{candidate_id}", response_model=AutomationProject)
def remove_repo_candidate(project_id: int, candidate_id: int):
    project = _require_project(project_id)
    candidates = list_repo_candidates(project_id)
    candidate = next((c for c in candidates if c["id"] == candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail="Repo candidate not found")
    delete_repo_candidate(candidate_id, project_id)
    if project.get("chosen_repo_url") == candidate["url"]:
        update_automation_project(project_id, chosen_repo_url=None)
    return _project(_require_project(project_id))


@router.post("/automation-projects/{project_id}/agent-updates", response_model=AutomationProject)
def add_agent_update(project_id: int, body: AgentUpdateCreate):
    _require_project(project_id)
    create_agent_update(
        project_id=project_id,
        agent=body.agent,
        summary=body.summary,
        changed_files=body.changed_files,
        commands_run=body.commands_run,
        test_result=body.test_result,
        blockers=body.blockers,
        next_step=body.next_step,
    )
    return _project(_require_project(project_id))


@router.post("/automation-projects/{project_id}/eval-cases", response_model=AutomationProject)
def add_eval_case(project_id: int, body: EvalCaseCreate):
    _require_project(project_id)
    if not body.name.strip() or not body.criteria.strip():
        raise HTTPException(status_code=400, detail="Eval case name and criteria are required")
    create_eval_case(
        project_id=project_id,
        name=body.name,
        criteria=body.criteria,
        input_text=body.input_text,
        ideal_output=body.ideal_output,
        weight=body.weight,
    )
    return _project(_require_project(project_id))


@router.delete("/automation-projects/{project_id}/eval-cases/{case_id}", response_model=AutomationProject)
def remove_eval_case(project_id: int, case_id: int):
    _require_project(project_id)
    case = get_eval_case(case_id, project_id)
    if not case:
        raise HTTPException(status_code=404, detail="Eval case not found")
    delete_eval_case(case_id, project_id)
    return _project(_require_project(project_id))


@router.patch("/automation-projects/{project_id}/eval-config", response_model=AutomationProject)
def update_project_eval_config(project_id: int, body: ProjectEvalConfigUpdate):
    project = _require_project(project_id)
    if body.eval_case_id is not None and not get_eval_case(body.eval_case_id, project_id):
        raise HTTPException(status_code=404, detail="Eval case not found")
    workflow_id = body.workflow_id or infer_project_workflow_id(project)
    rules = body.deterministic_rules
    if rules is None:
        rules = default_eval_rules(project, workflow_id)
    inputs = body.input_json
    if inputs is None:
        inputs = default_project_inputs(project, workflow_id)
    upsert_project_eval_config(
        project_id=project_id,
        workflow_id=workflow_id,
        eval_case_id=body.eval_case_id,
        input_json=inputs,
        deterministic_rules=rules,
        latest_output_ref=body.latest_output_ref,
    )
    return _project(_require_project(project_id))


@router.post("/automation-projects/{project_id}/eval-cases/{case_id}/run", response_model=AutomationProject)
def run_eval_case(project_id: int, case_id: int, body: EvalRunRequest):
    project = _require_project(project_id)
    case = get_eval_case(case_id, project_id)
    if not case:
        raise HTTPException(status_code=404, detail="Eval case not found")
    if not body.observed_output.strip():
        raise HTTPException(status_code=400, detail="Observed output is required")

    judgement = judge_output(project, case, body.observed_output)
    create_eval_result(
        eval_case_id=case_id,
        project_id=project_id,
        observed_output=body.observed_output,
        score=judgement.score,
        verdict=judgement.verdict,
        reasoning=judgement.reasoning,
        improvement_prompt=judgement.improvement_prompt,
    )
    return _project(_require_project(project_id))


@router.post("/automation-projects/{project_id}/run-and-evaluate", response_model=ProjectRunAndEvaluateResponse)
def run_and_evaluate_project(project_id: int, body: ProjectRunAndEvaluateRequest | None = None):
    body = body or ProjectRunAndEvaluateRequest()
    project = _require_project(project_id)
    config_row = get_project_eval_config(project_id)
    config = _eval_config(config_row)

    workflow_id = body.workflow_id or (config.workflow_id if config else None) or infer_project_workflow_id(project)
    eval_case_id = body.eval_case_id or (config.eval_case_id if config else None)
    if eval_case_id is None:
        cases = list_eval_cases(project_id)
        eval_case_id = cases[0]["id"] if cases else None
    if eval_case_id is None:
        raise HTTPException(status_code=400, detail="Add or select an eval case before running the harness")
    case = get_eval_case(eval_case_id, project_id)
    if not case:
        raise HTTPException(status_code=404, detail="Eval case not found")

    config_inputs = config.input_json if config else {}
    inputs = body.inputs if body.inputs is not None else (config_inputs or default_project_inputs(project, workflow_id))
    config_rules = config.deterministic_rules if config else {}
    rules = merge_rules(default_eval_rules(project, workflow_id), config_rules)
    rules = merge_rules(rules, body.deterministic_rules)
    latest_output_ref = config.latest_output_ref if config else {}

    checks = []
    output_ref: dict = {}
    workflow_run_id = None
    eval_result_row = None
    try:
        if body.mode == "run_workflow":
            if not workflow_id:
                raise HTTPException(status_code=400, detail="Choose a workflow before running the harness")
            output_text, output_ref, workflow_run_id = execute_workflow_for_project(
                workflow_id=workflow_id,
                inputs=inputs,
                client=body.client,
            )
        elif body.mode == "latest_output":
            output_text, output_ref, workflow_run_id = resolve_existing_output(
                workflow_id=workflow_id,
                observed_output=body.observed_output,
                output_path=body.output_path,
                latest_output_ref=latest_output_ref,
            )
        else:
            raise HTTPException(status_code=400, detail="mode must be 'latest_output' or 'run_workflow'")

        checks, _ = run_deterministic_checks(output_text, output_ref, rules)
        passed, total = summarize_check_counts(checks)
        judgement = judge_output(project, case, output_text)
        eval_result_row = create_eval_result(
            eval_case_id=eval_case_id,
            project_id=project_id,
            observed_output=output_text,
            score=judgement.score,
            verdict=judgement.verdict,
            reasoning=judgement.reasoning,
            improvement_prompt=judgement.improvement_prompt,
        )
        append_eval_history({
            "workflow_id": workflow_id,
            "project_name": project.get("name", ""),
            "score": judgement.score,
            "verdict": judgement.verdict,
            "passed": passed,
            "total": total,
            "mode": body.mode,
            "reasoning": judgement.reasoning,
        })
        eval_run_row = create_project_eval_run(
            project_id=project_id,
            workflow_id=workflow_id,
            eval_case_id=eval_case_id,
            workflow_run_id=workflow_run_id,
            eval_result_id=eval_result_row["id"],
            output_ref=output_ref,
            deterministic_checks=checks,
            deterministic_passed=passed,
            deterministic_total=total,
            status="completed",
            error=None,
        )
        upsert_project_eval_config(
            project_id=project_id,
            workflow_id=workflow_id,
            eval_case_id=eval_case_id,
            input_json=inputs,
            deterministic_rules=rules,
            latest_output_ref=output_ref,
        )
    except HTTPException:
        raise
    except Exception as e:
        passed, total = summarize_check_counts(checks)
        eval_run_row = create_project_eval_run(
            project_id=project_id,
            workflow_id=workflow_id,
            eval_case_id=eval_case_id,
            workflow_run_id=workflow_run_id,
            eval_result_id=eval_result_row["id"] if eval_result_row else None,
            output_ref=output_ref,
            deterministic_checks=checks,
            deterministic_passed=passed,
            deterministic_total=total,
            status="error",
            error=str(e),
        )
        upsert_project_eval_config(
            project_id=project_id,
            workflow_id=workflow_id,
            eval_case_id=eval_case_id,
            input_json=inputs,
            deterministic_rules=rules,
            latest_output_ref=output_ref,
        )
        raise HTTPException(status_code=502, detail=f"Run + Evaluate failed: {e}")

    return ProjectRunAndEvaluateResponse(
        project=_project(_require_project(project_id)),
        eval_run=_eval_run(eval_run_row),
        eval_result=_eval_result(eval_result_row) if eval_result_row else None,
    )


@router.post("/automation-projects/{project_id}/packages/generate", response_model=AutomationProject)
def generate_package(project_id: int, body: GeneratePackageRequest = None):
    body = body or GeneratePackageRequest()
    project = _require_project(project_id)
    repos = list_repo_candidates(project_id)
    updates = list_agent_updates(project_id)
    eval_cases = [
        {**case, "results": list_eval_results(project_id, case["id"])}
        for case in list_eval_cases(project_id)
    ]
    eval_runs = list_project_eval_runs(project_id)
    package = generate_execution_package(project, repos, updates, eval_cases, eval_runs)
    create_execution_package(
        project_id=project_id,
        title=package["title"],
        content_md=package["content_md"],
        readiness_score=package["readiness_score"],
        readiness=package["readiness"],
        planning_mode=body.planning_mode,
    )
    return _project(_require_project(project_id))

from typing import Any
from pydantic import BaseModel


class WorkflowInputSpec(BaseModel):
    key: str
    label: str
    type: str
    required: bool = True
    placeholder: str = ""
    choices: list[str] = []


class WorkflowMetaResponse(BaseModel):
    id: str
    name: str
    icon: str
    description: str
    order: int
    inputs: list[WorkflowInputSpec]
    primary_display_field: str
    stats_label: str
    requires_exa: bool
    demo_available: bool
    output_fields: list[str] = []


class RunWorkflowRequest(BaseModel):
    inputs: dict[str, Any]


class RunTimelineStep(BaseModel):
    key: str
    label: str
    status: str
    detail: str = ""


class RunEvidenceSource(BaseModel):
    title: str = ""
    url: str = ""
    kind: str = "web_source"


class RunEvidenceFile(BaseModel):
    label: str = ""
    path: str
    filename: str = ""


class RunEvidence(BaseModel):
    sources: list[RunEvidenceSource] = []
    saved_files: list[RunEvidenceFile] = []
    source_count: int = 0
    saved_file_count: int = 0


class RunValidationCheck(BaseModel):
    key: str
    label: str
    passed: bool
    severity: str = "info"
    details: str = ""


class RunValidationSummary(BaseModel):
    status: str
    passed: int
    total: int
    checks: list[RunValidationCheck] = []


class RunTrustReport(BaseModel):
    timeline: list[RunTimelineStep] = []
    evidence: RunEvidence
    validation: RunValidationSummary
    metadata: dict[str, Any] = {}


class RunResponse(BaseModel):
    status: str
    result: dict[str, Any] | None = None
    duration_seconds: float
    run_id: int | None = None
    error: str | None = None
    trust_report: RunTrustReport | None = None


class WorkflowJobStartResponse(BaseModel):
    job_id: str


class WorkflowJobStatus(BaseModel):
    job_id: str
    workflow_id: str
    status: str
    message: str
    elapsed_seconds: float
    response: RunResponse | None = None
    error: str | None = None


class RunRecord(BaseModel):
    id: int
    workflow_id: str
    status: str
    inputs_json: str
    outputs_json: str | None = None
    error_message: str | None = None
    duration_s: float | None = None
    model_used: str | None = None
    created_at: str
    trust_report: RunTrustReport | None = None


class ArchitectChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []


class ArchitectChatResponse(BaseModel):
    reply: str
    yaml_detected: bool
    yaml_content: str | None = None


class KBDirectory(BaseModel):
    folders: dict[str, list[str]]


class KBFile(BaseModel):
    folder: str
    filename: str
    content: str
    modified_at: str


class AutomationProjectCreate(BaseModel):
    name: str
    goal: str
    owner_type: str
    current_process: str
    working_definition: str
    client_context: str = ""
    required_tools: str = ""
    input_examples: str = ""
    output_examples: str = ""


class AutomationProjectUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    owner_type: str | None = None
    current_process: str | None = None
    working_definition: str | None = None
    client_context: str | None = None
    required_tools: str | None = None
    input_examples: str | None = None
    output_examples: str | None = None
    status: str | None = None
    chosen_repo_url: str | None = None


class RepoCandidateCreate(BaseModel):
    url: str
    notes: str = ""
    rank: int | None = None
    fit_score: int | None = None
    recommendation: str = ""
    license: str = ""
    stars: int | None = None
    last_updated: str = ""
    language: str = ""
    analysis_json: str = "{}"


class RepoCandidate(BaseModel):
    id: int
    project_id: int
    url: str
    notes: str = ""
    rank: int | None = None
    fit_score: int | None = None
    recommendation: str = ""
    license: str = ""
    stars: int | None = None
    last_updated: str = ""
    language: str = ""
    analysis_json: str = "{}"
    created_at: str


class ExecutionPackage(BaseModel):
    id: int
    project_id: int
    version: int
    title: str
    content_md: str
    readiness_score: int
    readiness: dict[str, Any]
    planning_mode: str = "quick"
    created_at: str


class GeneratePackageRequest(BaseModel):
    planning_mode: str = "quick"


class ProjectEvalConfigUpdate(BaseModel):
    workflow_id: str | None = None
    eval_case_id: int | None = None
    input_json: dict[str, Any] | None = None
    deterministic_rules: dict[str, Any] | None = None
    latest_output_ref: dict[str, Any] | None = None


class ProjectEvalConfig(BaseModel):
    project_id: int
    workflow_id: str | None = None
    eval_case_id: int | None = None
    input_json: dict[str, Any] = {}
    deterministic_rules: dict[str, Any] = {}
    latest_output_ref: dict[str, Any] = {}
    updated_at: str = ""


class DeterministicCheckResult(BaseModel):
    key: str
    label: str
    passed: bool
    details: str = ""
    severity: str = "error"


class ProjectEvalRun(BaseModel):
    id: int
    project_id: int
    workflow_id: str | None = None
    eval_case_id: int | None = None
    workflow_run_id: int | None = None
    eval_result_id: int | None = None
    output_ref: dict[str, Any] = {}
    deterministic_checks: list[DeterministicCheckResult] = []
    deterministic_passed: int
    deterministic_total: int
    status: str
    error: str | None = None
    created_at: str


class ProjectRunAndEvaluateRequest(BaseModel):
    mode: str = "latest_output"
    workflow_id: str | None = None
    eval_case_id: int | None = None
    inputs: dict[str, Any] | None = None
    deterministic_rules: dict[str, Any] | None = None
    observed_output: str | None = None
    output_path: str | None = None
    client: str | None = None


class AgentUpdateCreate(BaseModel):
    agent: str
    summary: str
    changed_files: str = ""
    commands_run: str = ""
    test_result: str = ""
    blockers: str = ""
    next_step: str = ""


class AgentUpdate(BaseModel):
    id: int
    project_id: int
    agent: str
    summary: str
    changed_files: str = ""
    commands_run: str = ""
    test_result: str = ""
    blockers: str = ""
    next_step: str = ""
    created_at: str


class EvalCaseCreate(BaseModel):
    name: str
    criteria: str
    input_text: str = ""
    ideal_output: str = ""
    weight: float = 1.0


class EvalRunRequest(BaseModel):
    observed_output: str


class ReliabilityIssue(BaseModel):
    title: str
    symptom: str = ""
    fast_fix: str = ""


class ReliabilityPlaybookResponse(BaseModel):
    path: str
    content_md: str
    issues: list[ReliabilityIssue] = []


class EvalResult(BaseModel):
    id: int
    eval_case_id: int
    project_id: int
    observed_output: str
    score: int
    verdict: str
    reasoning: str
    improvement_prompt: str = ""
    created_at: str


class EvalCase(BaseModel):
    id: int
    project_id: int
    name: str
    input_text: str = ""
    ideal_output: str = ""
    criteria: str
    weight: float = 1.0
    created_at: str
    results: list[EvalResult] = []


class AutomationProject(BaseModel):
    id: int
    name: str
    goal: str
    owner_type: str
    current_process: str
    working_definition: str
    client_context: str = ""
    required_tools: str = ""
    input_examples: str = ""
    output_examples: str = ""
    status: str
    chosen_repo_url: str | None = None
    created_at: str
    updated_at: str
    repo_candidates: list[RepoCandidate] = []
    execution_packages: list[ExecutionPackage] = []
    agent_updates: list[AgentUpdate] = []
    eval_cases: list[EvalCase] = []
    eval_config: ProjectEvalConfig | None = None
    eval_runs: list[ProjectEvalRun] = []


class ProjectRunAndEvaluateResponse(BaseModel):
    project: AutomationProject
    eval_run: ProjectEvalRun
    eval_result: EvalResult | None = None


class AgentJob(BaseModel):
    id: int
    name: str
    workflow_id: str
    cron_expr: str
    inputs_json: str
    client_id: str | None = None
    enabled: bool
    last_run_at: str | None = None
    last_status: str | None = None
    created_at: str


class AgentJobCreate(BaseModel):
    name: str
    workflow_id: str
    cron_expr: str
    inputs: dict[str, Any] = {}
    client_id: str | None = None


class AgentJobUpdate(BaseModel):
    name: str | None = None
    cron_expr: str | None = None
    inputs: dict[str, Any] | None = None
    enabled: bool | None = None

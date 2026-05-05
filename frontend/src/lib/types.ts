export interface WorkflowInputSpec {
  key: string;
  label: string;
  type: "text" | "textarea" | "select" | "multiline";
  required: boolean;
  placeholder: string;
  choices: string[];
}

export interface WorkflowMeta {
  id: string;
  name: string;
  icon: string;
  description: string;
  order: number;
  inputs: WorkflowInputSpec[];
  primary_display_field: string;
  stats_label: string;
  requires_exa: boolean;
  demo_available: boolean;
  output_fields: string[];
}

export interface RunResponse {
  status: "success" | "error";
  result: Record<string, unknown> | null;
  duration_seconds: number;
  run_id: number | null;
  error: string | null;
  trust_report: RunTrustReport | null;
}

export interface RunTimelineStep {
  key: string;
  label: string;
  status: "success" | "warning" | "error" | string;
  detail: string;
}

export interface RunEvidenceSource {
  title: string;
  url: string;
  kind: string;
}

export interface RunEvidenceFile {
  label: string;
  path: string;
  filename: string;
}

export interface RunEvidence {
  sources: RunEvidenceSource[];
  saved_files: RunEvidenceFile[];
  source_count: number;
  saved_file_count: number;
}

export interface RunValidationCheck {
  key: string;
  label: string;
  passed: boolean;
  severity: "info" | "warning" | "error" | string;
  details: string;
}

export interface RunValidationSummary {
  status: "pass" | "warn" | "fail" | string;
  passed: number;
  total: number;
  checks: RunValidationCheck[];
}

export interface RunTrustReport {
  timeline: RunTimelineStep[];
  evidence: RunEvidence;
  validation: RunValidationSummary;
  metadata: Record<string, unknown>;
}

export interface WorkflowJobStartResponse {
  job_id: string;
}

export interface WorkflowJobStatus {
  job_id: string;
  workflow_id: string;
  status: "running" | "success" | "error";
  message: string;
  elapsed_seconds: number;
  response: RunResponse | null;
  error: string | null;
}

export interface RunRecord {
  id: number;
  workflow_id: string;
  status: string;
  inputs_json: string;
  outputs_json: string | null;
  error_message: string | null;
  duration_s: number | null;
  model_used: string | null;
  created_at: string;
  trust_report: RunTrustReport | null;
}

export interface KBDirectory {
  folders: Record<string, string[]>;
}

export interface KBFile {
  folder: string;
  filename: string;
  content: string;
  modified_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ArchitectResponse {
  reply: string;
  yaml_detected: boolean;
  yaml_content: string | null;
}

export interface Settings {
  sender_name: string;
  api_status: Record<string, boolean>;
  credential_health?: CredentialHealth[];
}

export interface CredentialHealth {
  id: string;
  label: string;
  category: string;
  configured: boolean;
  status: "connected" | "partial" | "missing" | string;
  required_for: string[];
  risk: string;
  missing_env: string[];
}

export interface ClientInfo {
  id: string | null;
  display_name: string;
  owner_name: string;
  active_workflows: string[];
}

export interface HealthCheck {
  ok: boolean;
  demo_mode: boolean;
  warnings: string[];
  checks: Record<string, unknown>;
}

export type AutomationOwnerType = "personal" | "your_business" | "client";

export interface RepoCandidate {
  id: number;
  project_id: number;
  url: string;
  notes: string;
  rank: number | null;
  fit_score: number | null;
  recommendation: "use_as_reference" | "adapt_patterns" | "fork_candidate" | "avoid" | string;
  license: string;
  stars: number | null;
  last_updated: string;
  language: string;
  analysis_json: string;
  created_at: string;
}

export type PlanningMode = "quick" | "standard" | "deep";

export interface ExecutionPackage {
  id: number;
  project_id: number;
  version: number;
  title: string;
  content_md: string;
  readiness_score: number;
  readiness: {
    score: number;
    risk_label: string;
    repo_candidate_count: number;
    checks: Array<{
      key: string;
      label: string;
      passed: boolean;
      reason: string;
    }>;
  };
  planning_mode: PlanningMode;
  created_at: string;
}

export interface AgentUpdate {
  id: number;
  project_id: number;
  agent: "Claude Code" | "Codex" | "Manual" | string;
  summary: string;
  changed_files: string;
  commands_run: string;
  test_result: string;
  blockers: string;
  next_step: string;
  created_at: string;
}

export interface AgentUpdateCreate {
  agent: string;
  summary: string;
  changed_files?: string;
  commands_run?: string;
  test_result?: string;
  blockers?: string;
  next_step?: string;
}

export interface EvalResult {
  id: number;
  eval_case_id: number;
  project_id: number;
  observed_output: string;
  score: number;
  verdict: "pass" | "needs_work" | "fail" | string;
  reasoning: string;
  improvement_prompt: string;
  created_at: string;
}

export interface ReliabilityIssue {
  title: string;
  symptom: string;
  fast_fix: string;
}

export interface ReliabilityPlaybook {
  path: string;
  content_md: string;
  issues: ReliabilityIssue[];
}

export interface EvalCase {
  id: number;
  project_id: number;
  name: string;
  input_text: string;
  ideal_output: string;
  criteria: string;
  weight: number;
  created_at: string;
  results: EvalResult[];
}

export interface EvalCaseCreate {
  name: string;
  input_text?: string;
  ideal_output?: string;
  criteria: string;
  weight?: number;
}

export interface ProjectEvalConfig {
  project_id: number;
  workflow_id: string | null;
  eval_case_id: number | null;
  input_json: Record<string, unknown>;
  deterministic_rules: Record<string, unknown>;
  latest_output_ref: Record<string, unknown>;
  updated_at: string;
}

export interface DeterministicCheckResult {
  key: string;
  label: string;
  passed: boolean;
  details: string;
  severity: string;
}

export interface ProjectEvalRun {
  id: number;
  project_id: number;
  workflow_id: string | null;
  eval_case_id: number | null;
  workflow_run_id: number | null;
  eval_result_id: number | null;
  output_ref: Record<string, unknown>;
  deterministic_checks: DeterministicCheckResult[];
  deterministic_passed: number;
  deterministic_total: number;
  status: "completed" | "error" | string;
  error: string | null;
  created_at: string;
}

export interface ProjectRunAndEvaluateRequest {
  mode?: "latest_output" | "run_workflow";
  workflow_id?: string | null;
  eval_case_id?: number | null;
  inputs?: Record<string, unknown> | null;
  deterministic_rules?: Record<string, unknown> | null;
  observed_output?: string | null;
  output_path?: string | null;
  client?: string | null;
}

export interface ProjectRunAndEvaluateResponse {
  project: AutomationProject;
  eval_run: ProjectEvalRun;
  eval_result: EvalResult | null;
}

export interface AutomationProject {
  id: number;
  name: string;
  goal: string;
  owner_type: AutomationOwnerType;
  current_process: string;
  working_definition: string;
  client_context: string;
  required_tools: string;
  input_examples: string;
  output_examples: string;
  status: "idea" | "planned" | "building" | "testing" | "optimized" | "live";
  chosen_repo_url: string | null;
  created_at: string;
  updated_at: string;
  repo_candidates: RepoCandidate[];
  execution_packages: ExecutionPackage[];
  agent_updates: AgentUpdate[];
  eval_cases: EvalCase[];
  eval_config: ProjectEvalConfig | null;
  eval_runs: ProjectEvalRun[];
}

export interface AutomationProjectCreate {
  name: string;
  goal: string;
  owner_type: AutomationOwnerType;
  current_process: string;
  working_definition: string;
  client_context?: string;
  required_tools?: string;
  input_examples?: string;
  output_examples?: string;
}

export interface AutomationProjectUpdate {
  name?: string;
  goal?: string;
  owner_type?: AutomationOwnerType;
  current_process?: string;
  working_definition?: string;
  client_context?: string;
  required_tools?: string;
  input_examples?: string;
  output_examples?: string;
  status?: AutomationProject["status"];
  chosen_repo_url?: string | null;
}

export interface AgentJob {
  id: number;
  name: string;
  workflow_id: string;
  cron_expr: string;
  inputs_json: string;
  client_id: string | null;
  enabled: boolean;
  last_run_at: string | null;
  last_status: "success" | "error" | null;
  created_at: string;
}

export interface AgentJobCreate {
  name: string;
  workflow_id: string;
  cron_expr: string;
  inputs: Record<string, unknown>;
  client_id?: string | null;
}

export interface AgentJobUpdate {
  name?: string;
  cron_expr?: string;
  inputs?: Record<string, unknown>;
  enabled?: boolean;
}

export interface OutputFile {
  path: string;
  name: string;
  folder: string;
  size_kb: number;
  modified_at: string;
  type: "csv" | "md" | "txt" | "json" | string;
}

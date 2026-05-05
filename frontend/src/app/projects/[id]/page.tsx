"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import {
  AlertTriangle, Bot, CheckCircle, Copy, Download, FileCode2, FileSearch, FlaskConical,
  Loader2, PackageCheck, Plus, Save, Search, Sparkles, Star, Trash2, XCircle, Zap,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  addRepoCandidate,
  addAgentUpdate,
  addEvalCase,
  deleteRepoCandidate,
  deleteEvalCase,
  generateExecutionPackage,
  getAutomationProject,
  getProjectReliabilityPlaybook,
  getRuns,
  runAndEvaluateProject,
  runEvalCase,
  searchRepoIntelligence,
  updateAutomationProject,
} from "@/lib/api";
import type { AutomationProject, ExecutionPackage, PlanningMode, ReliabilityPlaybook, RepoCandidate, RunRecord } from "@/lib/types";

const COPY_SECTIONS = [
  "Repo Intelligence Findings",
  "Latest Eval Harness Context",
  "Repo Hunt Brief",
  "Claude Code Prompt",
  "Codex Prompt",
  "Task Split",
  "Basic Test Plan",
] as const;

const STAGES = [
  { key: "idea", status: "idea", label: "Idea" },
  { key: "spec", status: "planned", label: "Spec" },
  { key: "discover", status: "planned", label: "Discover" },
  { key: "build", status: "building", label: "Build" },
  { key: "test", status: "testing", label: "Test" },
  { key: "improve", status: "optimized", label: "Improve" },
  { key: "live", status: "live", label: "Live" },
] as const;

function extractSection(md: string, heading: string): string {
  const marker = `## ${heading}`;
  const start = md.indexOf(marker);
  if (start === -1) return "";
  const next = md.indexOf("\n## ", start + 1);
  return (next === -1 ? md.slice(start) : md.slice(start, next)).trim();
}

function repoAnalysis(repo: RepoCandidate): {
  reusable_patterns?: string[];
  useful_files?: string[];
  risks?: string[];
  setup_clarity?: string;
  notes?: string;
} {
  try {
    return JSON.parse(repo.analysis_json || "{}");
  } catch {
    return {};
  }
}

function recommendationLabel(value: string): string {
  return value ? value.replaceAll("_", " ") : "manual";
}

function repoRiskFlags(repo: RepoCandidate): string[] {
  const analysis = repoAnalysis(repo);
  const text = [
    repo.url,
    repo.notes,
    repo.recommendation,
    ...(analysis.risks ?? []),
  ].join(" ").toLowerCase();
  const flags: string[] = [];
  if (repo.recommendation === "avoid") flags.push("avoid");
  if (text.includes("linkedin") && (text.includes("scraping") || text.includes("cookie") || text.includes("account"))) {
    flags.push("account risk");
  }
  if (text.includes("awesome") || text.includes("curated") || text.includes("collection") || text.includes("reference list")) {
    flags.push("source map");
  }
  return flags;
}

function repoDisplayScore(repo: RepoCandidate): number {
  let score = repo.fit_score ?? 0;
  const flags = repoRiskFlags(repo);
  if (flags.includes("account risk")) score -= 70;
  if (flags.includes("avoid")) score -= 80;
  if (flags.includes("source map")) score -= 25;
  return score;
}

function inferWorkflowId(project: AutomationProject): string | null {
  const text = `${project.name} ${project.goal} ${project.required_tools}`.toLowerCase();
  if (text.includes("vc") || text.includes("lead") || text.includes("outreach")) return "vc_lead_scraper";
  if (text.includes("company") || text.includes("research")) return "company_research";
  if (text.includes("email")) return "email_drafting";
  if (text.includes("meeting")) return "meeting_prep";
  if (text.includes("portfolio")) return "portfolio_monitor";
  return null;
}

function parseRunOutput(run: RunRecord): Record<string, unknown> | null {
  if (!run.outputs_json) return null;
  try {
    const parsed = JSON.parse(run.outputs_json);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : { output: parsed };
  } catch {
    return null;
  }
}

function primaryTextOutput(run: RunRecord): string {
  const output = parseRunOutput(run);
  if (!output) return "";
  const preferredKeys = ["brief", "markdown", "report", "content", "summary", "body", "email", "csv", "output", "result"];
  for (const key of preferredKeys) {
    const value = output[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return JSON.stringify(output, null, 2);
}

function runLabel(run: RunRecord): string {
  const parsed = parseRunOutput(run);
  const count = parsed?.leads_found != null ? ` - ${parsed.leads_found} leads` : "";
  return `#${run.id} ${run.workflow_id}${count} - ${run.created_at.slice(0, 16)}`;
}

function outputRefLabel(ref: Record<string, unknown>): string {
  const value = (ref.file_path ?? ref.path ?? ref.csv_file_path ?? ref.source) as string | undefined;
  if (!value) return "No output reference captured";
  return value.split(/[\\/]/).pop() || value;
}

function scoreToneClass(score: number): string {
  if (score >= 80) return "text-[#7BAE7F]";
  if (score >= 50) return "text-[#BCA06A]";
  return "text-[#D7827E]";
}

function getNextAction(p: AutomationProject): { label: string; hint: string } {
  const specReady = Boolean(p.goal.trim() && p.current_process.trim() && p.working_definition.trim());
  const examplesReady = Boolean(p.input_examples.trim() && p.output_examples.trim());
  const hasIntelligence = p.repo_candidates.some((repo) => repo.fit_score != null || repo.recommendation);
  if (!specReady)
    return { label: "Tighten the automation brief", hint: "Capture the goal, current process, and proof of working before generating a package." };
  if (!examplesReady)
    return { label: "Add sample input and ideal output", hint: "Examples make the automation easier to build and much easier to evaluate." };
  if (p.eval_cases.length === 0)
    return { label: "Seed the first eval", hint: "Create a golden eval from the brief so every build can be judged against the same target." };
  if (!hasIntelligence)
    return { label: "Find proven repos", hint: "Run Repo Intelligence to ground the build in open-source precedent before sending it to an agent." };
  if (p.execution_packages.length === 0)
    return { label: "Generate v1 package", hint: 'Click "Generate package" to produce the first execution package.' };
  if (p.repo_candidates.length === 0)
    return { label: "Paste repo candidates", hint: "Copy the Repo Hunt Brief, search GitHub, then paste 1–5 URLs in the Repo Hunt panel." };
  if (!p.chosen_repo_url)
    return { label: "Choose a repo", hint: "Review the candidates and click Choose on the best fit." };
  if (p.agent_updates.length === 0)
    return { label: "Send to Claude Code or Codex", hint: "Copy the Claude Code Prompt, run it in your IDE, then paste the result in the Agent Build Log." };
  return { label: "Generate next package", hint: "Agent results recorded — generate the next package to include them in the IDE prompts." };
}

// ─── small shared piece ───────────────────────────────────────────────────────

function SectionCard({ title, icon, badge, children }: {
  title: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-[#2A2A30] bg-[#141418] overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-[#2A2A30]">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-semibold text-[#F2EFE8]">{title}</span>
        </div>
        {badge}
      </div>
      <div className="p-4 space-y-3">{children}</div>
    </div>
  );
}

function AmberBtn({
  onClick, disabled, children, className = "",
}: {
  onClick?: () => void;
  disabled?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-md bg-[#EEE8DC] px-3 py-1.5 text-sm font-semibold text-[#171717] hover:bg-[#DED4C3] disabled:opacity-50 transition-colors ${className}`}
    >
      {children}
    </button>
  );
}

function GhostBtn({
  onClick, disabled, children, className = "",
}: {
  onClick?: () => void;
  disabled?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-sm border border-[#2A2A30] px-2 py-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] hover:border-[#BCA06A]/40 disabled:opacity-50 transition-colors ${className}`}
    >
      {children}
    </button>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [project, setProject] = useState<AutomationProject | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [goalDraft, setGoalDraft] = useState("");
  const [currentProcessDraft, setCurrentProcessDraft] = useState("");
  const [workingDefinitionDraft, setWorkingDefinitionDraft] = useState("");
  const [clientContextDraft, setClientContextDraft] = useState("");
  const [requiredToolsDraft, setRequiredToolsDraft] = useState("");
  const [inputExamplesDraft, setInputExamplesDraft] = useState("");
  const [outputExamplesDraft, setOutputExamplesDraft] = useState("");
  const [savingSpec, setSavingSpec] = useState(false);
  const [repoUrl, setRepoUrl] = useState("");
  const [repoNotes, setRepoNotes] = useState("");
  const [savingRepo, setSavingRepo] = useState(false);
  const [searchingRepos, setSearchingRepos] = useState(false);
  const [deletingRepoId, setDeletingRepoId] = useState<number | null>(null);
  const [choosingRepoUrl, setChoosingRepoUrl] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [savingUpdate, setSavingUpdate] = useState(false);
  const [activePackageId, setActivePackageId] = useState<number | null>(null);
  const [rawMode, setRawMode] = useState(false);
  const [agent, setAgent] = useState("Claude Code");
  const [updateSummary, setUpdateSummary] = useState("");
  const [changedFiles, setChangedFiles] = useState("");
  const [commandsRun, setCommandsRun] = useState("");
  const [testResult, setTestResult] = useState("");
  const [blockers, setBlockers] = useState("");
  const [nextStep, setNextStep] = useState("");
  const [planningModeInput, setPlanningModeInput] = useState<PlanningMode>("quick");
  const [evalName, setEvalName] = useState("");
  const [evalInput, setEvalInput] = useState("");
  const [evalIdealOutput, setEvalIdealOutput] = useState("");
  const [evalCriteria, setEvalCriteria] = useState("");
  const [savingEvalCase, setSavingEvalCase] = useState(false);
  const [deletingEvalCaseId, setDeletingEvalCaseId] = useState<number | null>(null);
  const [activeEvalCaseId, setActiveEvalCaseId] = useState<number | null>(null);
  const [observedOutput, setObservedOutput] = useState("");
  const [recentRuns, setRecentRuns] = useState<RunRecord[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [reliabilityPlaybook, setReliabilityPlaybook] = useState<ReliabilityPlaybook | null>(null);
  const [runningEval, setRunningEval] = useState(false);
  const [runningHarness, setRunningHarness] = useState(false);

  function loadDrafts(p: AutomationProject) {
    setGoalDraft(p.goal);
    setCurrentProcessDraft(p.current_process);
    setWorkingDefinitionDraft(p.working_definition);
    setClientContextDraft(p.client_context);
    setRequiredToolsDraft(p.required_tools);
    setInputExamplesDraft(p.input_examples);
    setOutputExamplesDraft(p.output_examples);
  }

  useEffect(() => {
    if (isNaN(projectId)) {
      setError("Invalid project ID.");
      setLoading(false);
      return;
    }
    getAutomationProject(projectId)
      .then((p) => {
        setProject(p);
        loadDrafts(p);
        setActivePackageId(p.execution_packages[0]?.id ?? null);
        setActiveEvalCaseId(p.eval_config?.eval_case_id ?? p.eval_cases[0]?.id ?? null);
        const workflowId = inferWorkflowId(p);
        getRuns({ workflow_id: workflowId ?? undefined, limit: 12 })
          .then((runs) => setRecentRuns(runs.filter((run) => run.status === "success" && Boolean(run.outputs_json))))
          .catch(() => setRecentRuns([]));
        getProjectReliabilityPlaybook(p.id)
          .then(setReliabilityPlaybook)
          .catch(() => setReliabilityPlaybook(null));
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not load project"))
      .finally(() => setLoading(false));
  }, [projectId]);

  const activePackage = useMemo<ExecutionPackage | null>(() => {
    if (!project) return null;
    return project.execution_packages.find((p) => p.id === activePackageId) ?? project.execution_packages[0] ?? null;
  }, [project, activePackageId]);
  const planningMode = activePackage?.planning_mode ?? "quick";
  const hasRepoIntelligence = Boolean(project?.repo_candidates.some((repo) => repo.fit_score != null || repo.recommendation));
  const currentStageIndex = project?.status === "planned" && hasRepoIntelligence
    ? 2
    : Math.max(0, STAGES.findIndex((stage) => stage.status === project?.status));
  const activeEvalCase = useMemo(() => {
    if (!project) return null;
    return project.eval_cases.find((c) => c.id === activeEvalCaseId) ?? project.eval_cases[0] ?? null;
  }, [project, activeEvalCaseId]);
  const allEvalResults = useMemo(() => {
    if (!project) return null;
    return project.eval_cases
      .flatMap((c) => c.results)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [project]);
  const latestEvalResult = allEvalResults?.[0] ?? null;
  const latestEvalRun = project?.eval_runs[0] ?? null;
  const sortedRepoCandidates = useMemo(() => {
    if (!project) return [];
    return [...project.repo_candidates].sort((a, b) => {
      const scoreDelta = repoDisplayScore(b) - repoDisplayScore(a);
      if (scoreDelta !== 0) return scoreDelta;
      return (a.rank ?? 999) - (b.rank ?? 999);
    });
  }, [project]);
  const activeImprovementPrompt = activeEvalCase?.results[0]?.improvement_prompt || latestEvalResult?.improvement_prompt || "";
  const specDirty = Boolean(project && (
    goalDraft !== project.goal ||
    currentProcessDraft !== project.current_process ||
    workingDefinitionDraft !== project.working_definition ||
    clientContextDraft !== project.client_context ||
    requiredToolsDraft !== project.required_tools ||
    inputExamplesDraft !== project.input_examples ||
    outputExamplesDraft !== project.output_examples
  ));
  const briefChecks = [
    { label: "Goal", done: Boolean(goalDraft.trim()) },
    { label: "Manual process", done: Boolean(currentProcessDraft.trim()) },
    { label: "Proof", done: Boolean(workingDefinitionDraft.trim()) },
    { label: "Examples", done: Boolean(inputExamplesDraft.trim() && outputExamplesDraft.trim()) },
    { label: "Eval", done: Boolean(project?.eval_cases.length) },
    { label: "Harness", done: Boolean(project?.eval_runs.length) },
  ];

  function refresh(next: AutomationProject, advancePackage = false) {
    setProject(next);
    if (advancePackage) {
      setActivePackageId(next.execution_packages[0]?.id ?? null);
    }
  }

  async function addRepo() {
    if (!project || !repoUrl.trim()) return;
    setSavingRepo(true);
    try {
      const next = await addRepoCandidate(project.id, { url: repoUrl.trim(), notes: repoNotes.trim() });
      refresh(next);
      setRepoUrl("");
      setRepoNotes("");
      toast.success("Repo candidate added");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not add repo");
    } finally {
      setSavingRepo(false);
    }
  }

  async function runRepoIntelligence() {
    if (!project) return;
    setSearchingRepos(true);
    try {
      const before = new Set(project.repo_candidates.map((repo) => repo.url));
      const next = await searchRepoIntelligence(project.id);
      refresh(next);
      const added = next.repo_candidates.filter((repo) => !before.has(repo.url)).length;
      if (added > 0) {
        toast.success(`Repo Intelligence added ${added} reference${added === 1 ? "" : "s"}`);
      } else {
        toast.message("Repo Intelligence ran, but found no new references beyond the current list.");
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not run Repo Intelligence");
    } finally {
      setSearchingRepos(false);
    }
  }

  async function removeRepo(candidateId: number) {
    if (!project) return;
    setDeletingRepoId(candidateId);
    try {
      const next = await deleteRepoCandidate(project.id, candidateId);
      refresh(next);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not remove repo");
    } finally {
      setDeletingRepoId(null);
    }
  }

  async function chooseRepo(url: string) {
    if (!project) return;
    setChoosingRepoUrl(url);
    try {
      const next = await updateAutomationProject(project.id, { chosen_repo_url: url });
      refresh(next);
      toast.success("Chosen repo updated");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not choose repo");
    } finally {
      setChoosingRepoUrl(null);
    }
  }

  async function updateStatus(status: AutomationProject["status"]) {
    if (!project) return;
    try {
      const next = await updateAutomationProject(project.id, { status });
      refresh(next);
      toast.success("Lifecycle stage updated");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not update status");
    }
  }

  async function saveSpec() {
    if (!project) return;
    if (!goalDraft.trim() || !currentProcessDraft.trim() || !workingDefinitionDraft.trim()) {
      toast.error("Goal, current process, and working proof are required.");
      return;
    }
    setSavingSpec(true);
    try {
      const next = await updateAutomationProject(project.id, {
        goal: goalDraft.trim(),
        current_process: currentProcessDraft.trim(),
        working_definition: workingDefinitionDraft.trim(),
        client_context: clientContextDraft.trim(),
        required_tools: requiredToolsDraft.trim(),
        input_examples: inputExamplesDraft.trim(),
        output_examples: outputExamplesDraft.trim(),
      });
      refresh(next);
      loadDrafts(next);
      toast.success("Automation brief saved");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not save automation brief");
    } finally {
      setSavingSpec(false);
    }
  }

  function downloadPackage() {
    if (!project || !activePackage) return;
    const safeName = project.name.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-");
    const blob = new Blob([activePackage.content_md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${safeName}-v${activePackage.version}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function generatePackage() {
    if (!project) return;
    setGenerating(true);
    try {
      const next = await generateExecutionPackage(project.id, planningModeInput);
      refresh(next, true);
      toast.success("Execution package generated");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not generate package");
    } finally {
      setGenerating(false);
    }
  }

  async function saveAgentUpdate() {
    if (!project || !updateSummary.trim()) {
      toast.error("Add a short summary before saving the agent update.");
      return;
    }
    setSavingUpdate(true);
    try {
      const next = await addAgentUpdate(project.id, {
        agent,
        summary: updateSummary.trim(),
        changed_files: changedFiles.trim(),
        commands_run: commandsRun.trim(),
        test_result: testResult.trim(),
        blockers: blockers.trim(),
        next_step: nextStep.trim(),
      });
      refresh(next);
      setUpdateSummary("");
      setChangedFiles("");
      setCommandsRun("");
      setTestResult("");
      setBlockers("");
      setNextStep("");
      toast.success("Agent update saved");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not save agent update");
    } finally {
      setSavingUpdate(false);
    }
  }

  async function saveEvalCase() {
    if (!project || !evalName.trim() || !evalCriteria.trim()) {
      toast.error("Eval name and criteria are required.");
      return;
    }
    setSavingEvalCase(true);
    try {
      const next = await addEvalCase(project.id, {
        name: evalName.trim(),
        input_text: evalInput.trim(),
        ideal_output: evalIdealOutput.trim(),
        criteria: evalCriteria.trim(),
      });
      refresh(next);
      setActiveEvalCaseId(next.eval_cases[0]?.id ?? null);
      setEvalName("");
      setEvalInput("");
      setEvalIdealOutput("");
      setEvalCriteria("");
      toast.success("Eval case added");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not add eval case");
    } finally {
      setSavingEvalCase(false);
    }
  }

  async function seedEvalFromBrief() {
    if (!project) return;
    if (!inputExamplesDraft.trim() || !outputExamplesDraft.trim() || !workingDefinitionDraft.trim()) {
      toast.error("Add sample input, expected output, and working proof first.");
      return;
    }
    setSavingEvalCase(true);
    try {
      let current = project;
      if (specDirty) {
        current = await updateAutomationProject(project.id, {
          goal: goalDraft.trim(),
          current_process: currentProcessDraft.trim(),
          working_definition: workingDefinitionDraft.trim(),
          client_context: clientContextDraft.trim(),
          required_tools: requiredToolsDraft.trim(),
          input_examples: inputExamplesDraft.trim(),
          output_examples: outputExamplesDraft.trim(),
        });
        loadDrafts(current);
      }
      const next = await addEvalCase(current.id, {
        name: "Golden path",
        input_text: inputExamplesDraft.trim(),
        ideal_output: outputExamplesDraft.trim(),
        criteria: `Judge whether the output satisfies this working definition:\n${workingDefinitionDraft.trim()}\n\nIt should match the expected output shape, handle the sample input, and be useful for the real business process.`,
      });
      refresh(next);
      setActiveEvalCaseId(next.eval_cases[0]?.id ?? null);
      toast.success("Starter eval created from the brief");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not seed eval");
    } finally {
      setSavingEvalCase(false);
    }
  }

  async function removeEvalCase(caseId: number) {
    if (!project) return;
    setDeletingEvalCaseId(caseId);
    try {
      const next = await deleteEvalCase(project.id, caseId);
      refresh(next);
      setActiveEvalCaseId(next.eval_cases[0]?.id ?? null);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not delete eval case");
    } finally {
      setDeletingEvalCaseId(null);
    }
  }

  async function runEval() {
    if (!project || !activeEvalCase || !observedOutput.trim()) {
      toast.error("Choose an eval case and paste the observed output.");
      return;
    }
    setRunningEval(true);
    try {
      const next = await runEvalCase(project.id, activeEvalCase.id, observedOutput.trim());
      refresh(next);
      setObservedOutput("");
      toast.success("Eval completed");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not run eval");
    } finally {
      setRunningEval(false);
    }
  }

  async function runProjectHarness() {
    if (!project || !activeEvalCase) {
      toast.error("Choose an eval case before running the harness.");
      return;
    }
    setRunningHarness(true);
    try {
      const workflowId = project.eval_config?.workflow_id ?? inferWorkflowId(project);
      const response = await runAndEvaluateProject(project.id, {
        mode: "latest_output",
        workflow_id: workflowId,
        eval_case_id: activeEvalCase.id,
      });
      refresh(response.project);
      setActiveEvalCaseId(response.project.eval_config?.eval_case_id ?? activeEvalCase.id);
      const checks = `${response.eval_run.deterministic_passed}/${response.eval_run.deterministic_total}`;
      const score = response.eval_result ? `, score ${response.eval_result.score}/100` : "";
      toast.success(`Run + Evaluate complete: ${checks} checks passed${score}`);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Run + Evaluate failed");
    } finally {
      setRunningHarness(false);
    }
  }

  function selectRunForEval(runId: string) {
    setSelectedRunId(runId);
    const run = recentRuns.find((item) => String(item.id) === runId);
    if (!run) return;
    const output = primaryTextOutput(run);
    if (!output) {
      toast.error("That run has no usable output to evaluate.");
      return;
    }
    setObservedOutput(output);
    toast.success("Run output loaded for eval");
  }

  async function saveImprovementAsUpdate() {
    if (!project || !activeImprovementPrompt.trim()) return;
    setSavingUpdate(true);
    try {
      const next = await addAgentUpdate(project.id, {
        agent: "Codex",
        summary: "Eval improvement prompt saved for the next automation iteration.",
        changed_files: "",
        commands_run: "",
        test_result: latestEvalResult ? `Latest eval: ${latestEvalResult.score}/100 ${latestEvalResult.verdict}` : "",
        blockers: "",
        next_step: activeImprovementPrompt.trim(),
      });
      refresh(next);
      toast.success("Improvement saved to build log");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not save improvement");
    } finally {
      setSavingUpdate(false);
    }
  }

  const inputCls = "border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A] text-xs";
  const selectCls = "h-8 text-xs border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] focus:ring-[#BCA06A]";
  const selectContentCls = "border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]";
  const labelCls = "text-xs font-medium text-[#F2EFE8]";

  if (loading) {
    return (
      <div className="max-w-6xl space-y-5">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error) return <p className="text-[#D7827E] text-sm">{error}</p>;
  if (!project) return <p className="text-[#A8A29A]">Project not found.</p>;

  return (
    <div className="max-w-7xl space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#F2EFE8]">{project.name}</h1>
            <span className="border border-[#2A2A30] rounded-sm px-2 py-0.5 text-[11px] text-[#A8A29A] capitalize">
              {project.status}
            </span>
            <span className="border border-[#2A2A30] rounded-sm px-2 py-0.5 text-[11px] text-[#A8A29A]">
              {project.owner_type.replace("_", " ")}
            </span>
          </div>
          <p className="text-sm text-[#A8A29A] max-w-3xl">{project.goal}</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={project.status} onValueChange={(v) => updateStatus(v as AutomationProject["status"])}>
            <SelectTrigger className="h-9 w-32 text-xs capitalize border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className={selectContentCls}>
              <SelectItem value="idea">Idea</SelectItem>
              <SelectItem value="planned">Spec</SelectItem>
              <SelectItem value="building">Build</SelectItem>
              <SelectItem value="testing">Test</SelectItem>
              <SelectItem value="optimized">Improve</SelectItem>
              <SelectItem value="live">Live</SelectItem>
            </SelectContent>
          </Select>
          <Select value={planningModeInput} onValueChange={(v) => setPlanningModeInput(v as PlanningMode)}>
            <SelectTrigger className="h-9 w-28 text-xs border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className={selectContentCls}>
              <SelectItem value="quick">Quick</SelectItem>
              <SelectItem value="standard">Standard</SelectItem>
              <SelectItem value="deep">Deep</SelectItem>
            </SelectContent>
          </Select>
          <GhostBtn onClick={runProjectHarness} disabled={runningHarness || !activeEvalCase}>
            {runningHarness ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <FlaskConical className="h-4 w-4 mr-1.5" />}
            Run + Evaluate
          </GhostBtn>
          <AmberBtn onClick={generatePackage} disabled={generating || specDirty}>
            {generating ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <PackageCheck className="h-4 w-4 mr-1.5" />}
            Generate
          </AmberBtn>
        </div>
      </div>

      {/* Next action banner */}
      {(() => {
        const next = getNextAction(project);
        return (
          <div className="flex items-start gap-3 rounded-md border border-[#BCA06A]/30 bg-[#BCA06A]/5 px-4 py-3">
            <Zap className="h-4 w-4 text-[#BCA06A] shrink-0 mt-0.5" />
            <div>
              <span className="text-sm font-medium text-[#BCA06A]">{next.label}</span>
              <span className="text-xs text-[#A8A29A] ml-2">{next.hint}</span>
            </div>
          </div>
        );
      })()}

      {/* Build workstream */}
      <div className="rounded-md border border-[#2A2A30] bg-[#141418] px-4 py-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            <p className="text-sm font-semibold text-[#F2EFE8]">Build Workstream</p>
            <p className="text-xs text-[#A8A29A]">Brief, package, build log, eval, improve.</p>
          </div>
          <div className="flex items-center gap-2">
            <GhostBtn onClick={runProjectHarness} disabled={runningHarness || !activeEvalCase}>
              {runningHarness ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <FlaskConical className="h-4 w-4 mr-1" />}
              Run + Evaluate
            </GhostBtn>
            <GhostBtn onClick={seedEvalFromBrief} disabled={savingEvalCase || !inputExamplesDraft.trim() || !outputExamplesDraft.trim()}>
              {savingEvalCase ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Sparkles className="h-4 w-4 mr-1" />}
              Seed eval
            </GhostBtn>
            <AmberBtn onClick={generatePackage} disabled={generating || specDirty}>
              {generating ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <PackageCheck className="h-4 w-4 mr-1" />}
              Package
            </AmberBtn>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-3">
          {briefChecks.map((check) => (
            <div key={check.label} className={`rounded-md border px-2 py-2 text-xs ${check.done ? "border-[#BCA06A]/40 bg-[#BCA06A]/10 text-[#BCA06A]" : "border-[#2A2A30] text-[#A8A29A]"}`}>
              {check.done
                ? <CheckCircle className="h-3.5 w-3.5 inline mr-1.5 text-[#7BAE7F]" />
                : <XCircle className="h-3.5 w-3.5 inline mr-1.5 text-[#A8A29A]" />}
              {check.label}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-7 gap-2">
          {STAGES.map((stage, index) => {
            const active = index <= currentStageIndex;
            return (
              <button
                key={stage.key}
                onClick={() => updateStatus(stage.status)}
                className={`min-h-11 rounded-md border px-2 text-xs transition-colors cursor-pointer ${
                  active
                    ? "border-[#BCA06A]/50 bg-[#BCA06A]/10 text-[#BCA06A]"
                    : "border-[#2A2A30] text-[#A8A29A] hover:text-[#F2EFE8] hover:border-[#BCA06A]/30"
                }`}
              >
                <span className="font-mono mr-1">{index + 1}</span>
                {stage.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-5">
        {/* Left column — cards */}
        <div className="space-y-5">

          {/* Automation Brief */}
          <SectionCard
            title="Automation Brief"
            badge={specDirty ? (
              <span className="border border-[#C8903D]/40 rounded-sm px-2 py-0.5 text-[11px] text-[#E8C982]">Unsaved</span>
            ) : undefined}
          >
            <div className="space-y-1.5">
              <label className={labelCls}>Goal</label>
              <Textarea value={goalDraft} onChange={(e) => setGoalDraft(e.target.value)} rows={3} className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Current manual process</label>
              <Textarea value={currentProcessDraft} onChange={(e) => setCurrentProcessDraft(e.target.value)} rows={3} className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Proof that it works</label>
              <Textarea value={workingDefinitionDraft} onChange={(e) => setWorkingDefinitionDraft(e.target.value)} rows={3} className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Client context</label>
              <Textarea value={clientContextDraft} onChange={(e) => setClientContextDraft(e.target.value)} rows={2} placeholder="Client, business context, tone, constraints..." className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Tools, APIs, or data</label>
              <Textarea value={requiredToolsDraft} onChange={(e) => setRequiredToolsDraft(e.target.value)} rows={2} placeholder="CRM, Gmail, Exa, sheets, private docs..." className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Sample input</label>
              <Textarea value={inputExamplesDraft} onChange={(e) => setInputExamplesDraft(e.target.value)} rows={3} className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Expected output</label>
              <Textarea value={outputExamplesDraft} onChange={(e) => setOutputExamplesDraft(e.target.value)} rows={3} className={inputCls} />
            </div>
            <AmberBtn onClick={saveSpec} disabled={savingSpec || !specDirty} className="w-full">
              {savingSpec ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
              Save brief
            </AmberBtn>
          </SectionCard>

          {/* Repo Intelligence */}
          <SectionCard
            title="Repo Intelligence"
            icon={<FileSearch className="h-4 w-4 text-[#BCA06A]" />}
            badge={hasRepoIntelligence ? (
              <span className="border border-[#2A2A30] rounded-sm px-2 py-0.5 text-[11px] text-[#A8A29A]">
                {project.repo_candidates.length} found
              </span>
            ) : undefined}
          >
            <AmberBtn
              onClick={runRepoIntelligence}
              disabled={searchingRepos || specDirty || !goalDraft.trim()}
              className="w-full"
            >
              {searchingRepos ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Search className="h-4 w-4 mr-1.5" />}
              Find proven repos
            </AmberBtn>
            {specDirty && (
              <p className="text-xs text-[#A8A29A]">Save the brief first so discovery searches the latest context.</p>
            )}

            <div className="space-y-1.5">
              <label className={labelCls}>Manual GitHub URL</label>
              <Input value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} placeholder="https://github.com/..." className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Notes</label>
              <Textarea value={repoNotes} onChange={(e) => setRepoNotes(e.target.value)} rows={2} placeholder="Why it might fit, concerns, source..." className={inputCls} />
            </div>
            <GhostBtn onClick={addRepo} disabled={savingRepo || !repoUrl.trim()} className="w-full">
              {savingRepo ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Plus className="h-3 w-3 mr-1" />}
              Add candidate
            </GhostBtn>

            <div className="space-y-2 pt-2">
              {project.repo_candidates.length === 0 ? (
                <p className="text-xs text-[#A8A29A]">
                  Run discovery to find working open-source precedent, or paste a known repo manually.
                </p>
              ) : sortedRepoCandidates.map((repo) => {
                const analysis = repoAnalysis(repo);
                const patterns = analysis.reusable_patterns ?? [];
                const risks = analysis.risks ?? [];
                const riskFlags = repoRiskFlags(repo);
                return (
                  <div key={repo.id} className="rounded-md border border-[#2A2A30] p-3 space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs font-mono break-all text-[#F2EFE8]">{repo.url}</p>
                      {repo.fit_score != null && (
                        <span className="border border-[#2A2A30] rounded-sm px-2 py-0.5 text-[11px] text-[#A8A29A] shrink-0">
                          {repo.fit_score}/100
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1.5 text-[11px] text-[#A8A29A]">
                      {repo.recommendation && (
                        <span className="rounded border border-[#2A2A30] px-1.5 py-0.5 capitalize">{recommendationLabel(repo.recommendation)}</span>
                      )}
                      {riskFlags.map((flag) => (
                        <span key={flag} className="rounded border border-[#BCA06A]/30 bg-[#BCA06A]/10 px-1.5 py-0.5 text-[#BCA06A]">
                          {flag}
                        </span>
                      ))}
                      {repo.language && <span className="rounded border border-[#2A2A30] px-1.5 py-0.5">{repo.language}</span>}
                      {repo.stars != null && (
                        <span className="inline-flex items-center gap-1 rounded border border-[#2A2A30] px-1.5 py-0.5">
                          <Star className="h-2.5 w-2.5" />{repo.stars}
                        </span>
                      )}
                      {repo.license && <span className="rounded border border-[#2A2A30] px-1.5 py-0.5">{repo.license}</span>}
                    </div>
                    {patterns.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-[#F2EFE8]">What to reuse</p>
                        <p className="text-xs text-[#A8A29A]">{patterns.slice(0, 3).join("; ")}</p>
                      </div>
                    )}
                    {risks.length > 0 && (
                      <div className="flex gap-2 text-xs text-[#A8A29A]">
                        <AlertTriangle className="h-3.5 w-3.5 text-[#C8903D] shrink-0 mt-0.5" />
                        <span>{risks.slice(0, 2).join("; ")}</span>
                      </div>
                    )}
                    {!patterns.length && repo.notes && <p className="text-xs text-[#A8A29A] whitespace-pre-wrap">{repo.notes}</p>}
                    <div className="flex items-center gap-2">
                      <button
                        className={`flex-1 h-7 rounded-sm border text-xs transition-colors disabled:opacity-50 ${
                          project.chosen_repo_url === repo.url
                            ? "border-[#BCA06A]/40 bg-[#BCA06A]/10 text-[#BCA06A]"
                            : "border-[#2A2A30] text-[#A8A29A] hover:text-[#F2EFE8] hover:border-[#BCA06A]/30"
                        }`}
                        onClick={() => chooseRepo(repo.url)}
                        disabled={choosingRepoUrl !== null}
                      >
                        {choosingRepoUrl === repo.url ? (
                          <Loader2 className="h-3 w-3 animate-spin mx-auto" />
                        ) : project.chosen_repo_url === repo.url ? "Chosen reference" : "Choose reference"}
                      </button>
                      <button
                        className="h-7 w-7 flex items-center justify-center rounded-sm border border-[#2A2A30] text-[#A8A29A] hover:text-[#D7827E] hover:border-[#6E2B2B]/50 disabled:opacity-50 transition-colors"
                        onClick={() => removeRepo(repo.id)}
                        disabled={deletingRepoId === repo.id}
                        aria-label="Delete repo candidate"
                      >
                        {deletingRepoId === repo.id
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : <Trash2 className="h-3 w-3" />}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </SectionCard>

          {/* Readiness */}
          <SectionCard title="Readiness">
            {activePackage ? (
              <div className="space-y-3">
                <div className="text-2xl font-bold text-[#F2EFE8]">
                  {activePackage.readiness_score}/{activePackage.readiness.checks.length}
                </div>
                <div className="space-y-2">
                  {activePackage.readiness.checks.map((check) => (
                    <div key={check.key} className="flex gap-2 text-xs">
                      {check.passed
                        ? <CheckCircle className="h-3.5 w-3.5 text-[#7BAE7F] shrink-0 mt-0.5" />
                        : <XCircle className="h-3.5 w-3.5 text-[#A8A29A] shrink-0 mt-0.5" />}
                      <div>
                        <p className="font-medium text-[#F2EFE8]">{check.label}</p>
                        <p className="text-[#A8A29A]">{check.reason}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-[#A8A29A]">Generate the first execution package to see readiness.</p>
            )}
          </SectionCard>

          {/* Known Issues */}
          <SectionCard
            title="Known Issues"
            icon={<AlertTriangle className="h-4 w-4 text-[#C8903D]" />}
            badge={reliabilityPlaybook ? (
              <button
                className="inline-flex items-center gap-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
                onClick={() => {
                  navigator.clipboard.writeText(reliabilityPlaybook.content_md);
                  toast.success("Reliability playbook copied");
                }}
              >
                <Copy className="h-3 w-3" /> Full
              </button>
            ) : undefined}
          >
            {!reliabilityPlaybook ? (
              <p className="text-xs text-[#A8A29A]">Reliability playbook is not available yet.</p>
            ) : (
              <>
                <div className="space-y-2">
                  {reliabilityPlaybook.issues.slice(0, 5).map((issue) => (
                    <div key={issue.title} className="rounded-md border border-[#2A2A30] px-3 py-2">
                      <p className="text-xs font-medium text-[#F2EFE8]">{issue.title}</p>
                      <p className="text-xs text-[#A8A29A] mt-1 line-clamp-2">
                        {issue.fast_fix || issue.symptom || "Open the full playbook for the fix."}
                      </p>
                    </div>
                  ))}
                </div>
                <button
                  className="text-left text-[11px] font-mono text-[#A8A29A] hover:text-[#F2EFE8] transition-colors cursor-pointer"
                  onClick={() => {
                    navigator.clipboard.writeText(reliabilityPlaybook.path);
                    toast.success("Playbook path copied");
                  }}
                >
                  {reliabilityPlaybook.path}
                </button>
              </>
            )}
          </SectionCard>

          {/* Eval Lab */}
          <SectionCard
            title="Eval Lab"
            icon={<FlaskConical className="h-4 w-4 text-[#BCA06A]" />}
          >
            {latestEvalResult && (
              <div className="rounded-md border border-[#2A2A30] px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-[#F2EFE8]">Latest score</span>
                  <span className="border border-[#2A2A30] rounded-sm px-2 py-0.5 text-[11px] text-[#A8A29A]">
                    {latestEvalResult.score}/100 {latestEvalResult.verdict}
                  </span>
                </div>
                <div className={`mt-2 text-3xl font-bold ${scoreToneClass(latestEvalResult.score)}`}>
                  {latestEvalResult.score}/100
                </div>
                <p className="text-xs text-[#A8A29A] mt-2 whitespace-pre-wrap">
                  {latestEvalResult.reasoning}
                </p>
              </div>
            )}

            {latestEvalRun && (
              <div className="rounded-md border border-[#2A2A30] px-3 py-2 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-[#F2EFE8]">Latest deterministic checks</span>
                  <span className="border border-[#2A2A30] rounded-sm px-2 py-0.5 text-[11px] text-[#A8A29A]">
                    {latestEvalRun.deterministic_passed}/{latestEvalRun.deterministic_total}
                  </span>
                </div>
                <p className="text-[11px] font-mono text-[#A8A29A] truncate">
                  {outputRefLabel(latestEvalRun.output_ref)}
                </p>
                {latestEvalRun.deterministic_checks.filter((check) => !check.passed).length === 0 ? (
                  <div className="flex gap-2 text-xs text-[#A8A29A]">
                    <CheckCircle className="h-3.5 w-3.5 text-[#7BAE7F] shrink-0 mt-0.5" />
                    <span>All configured checks passed.</span>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {latestEvalRun.deterministic_checks.filter((check) => !check.passed).slice(0, 5).map((check) => (
                      <div key={check.key} className="flex gap-2 text-xs">
                        <XCircle className="h-3.5 w-3.5 text-[#D7827E] shrink-0 mt-0.5" />
                        <div>
                          <p className="font-medium text-[#F2EFE8]">{check.label}</p>
                          <p className="text-[#A8A29A]">{check.details}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <GhostBtn onClick={generatePackage} disabled={generating || specDirty} className="w-full">
                  {generating ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <PackageCheck className="h-4 w-4 mr-1" />}
                  Package eval context
                </GhostBtn>
              </div>
            )}

            {allEvalResults && allEvalResults.length > 1 && (
              <div className="rounded-md border border-[#2A2A30] px-3 py-2">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-xs font-medium text-[#F2EFE8]">Score history</span>
                  <span className="text-[11px] text-[#A8A29A]">{allEvalResults.length} runs</span>
                </div>
                <div className="space-y-1.5">
                  {allEvalResults.slice(0, 8).map((result, index) => {
                    const previous = allEvalResults[index + 1];
                    const delta = previous ? result.score - previous.score : 0;
                    return (
                      <div key={result.id} className="flex items-center justify-between gap-2 text-xs">
                        <span className="font-mono text-[#A8A29A]">{result.created_at.slice(0, 16)}</span>
                        <div className="flex items-center gap-2">
                          {previous && (
                            <span className={delta >= 0 ? "text-[#7BAE7F]" : "text-[#D7827E]"}>
                              {delta >= 0 ? "+" : ""}{delta}
                            </span>
                          )}
                          <span className={scoreToneClass(result.score)}>{result.score}/100</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              <label className={labelCls}>New eval case</label>
              <Input value={evalName} onChange={(e) => setEvalName(e.target.value)} placeholder="e.g. CSV lead quality check" className={inputCls} />
              <Textarea value={evalInput} onChange={(e) => setEvalInput(e.target.value)} rows={2} placeholder="Input or scenario this automation should handle." className={inputCls} />
              <Textarea value={evalIdealOutput} onChange={(e) => setEvalIdealOutput(e.target.value)} rows={2} placeholder="Ideal output shape, fields, tone, or decision." className={inputCls} />
              <Textarea value={evalCriteria} onChange={(e) => setEvalCriteria(e.target.value)} rows={3} placeholder="Judging criteria. What would make this client-ready or embarrassing?" className={inputCls} />
            </div>
            <AmberBtn onClick={saveEvalCase} disabled={savingEvalCase || !evalName.trim() || !evalCriteria.trim()} className="w-full">
              {savingEvalCase ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Plus className="h-4 w-4 mr-1.5" />}
              Add eval case
            </AmberBtn>

            <div className="space-y-2">
              {project.eval_cases.length === 0 ? (
                <p className="text-xs text-[#A8A29A]">
                  Add golden cases that prove the automation is good enough for the real workflow.
                </p>
              ) : project.eval_cases.map((evalCase) => {
                const latest = evalCase.results[0];
                return (
                  <div key={evalCase.id} className="rounded-md border border-[#2A2A30] p-3 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <button
                        onClick={() => setActiveEvalCaseId(evalCase.id)}
                        className={`text-left text-xs font-medium cursor-pointer transition-colors ${activeEvalCase?.id === evalCase.id ? "text-[#BCA06A]" : "text-[#F2EFE8] hover:text-[#BCA06A]"}`}
                      >
                        {evalCase.name}
                      </button>
                      <button
                        onClick={() => removeEvalCase(evalCase.id)}
                        disabled={deletingEvalCaseId === evalCase.id}
                        className="text-[#A8A29A] hover:text-[#D7827E] transition-colors"
                        aria-label="Delete eval case"
                      >
                        {deletingEvalCaseId === evalCase.id
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : <Trash2 className="h-3 w-3" />}
                      </button>
                    </div>
                    <p className="text-xs text-[#A8A29A] line-clamp-3">{evalCase.criteria}</p>
                    {latest && (
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono text-[#A8A29A]">{latest.created_at.slice(0, 16)}</span>
                        <span className={scoreToneClass(latest.score)}>{latest.score}/100</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {activeEvalCase && (
              <div className="space-y-2 border-t border-[#2A2A30] pt-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium text-[#F2EFE8]">Run judge on: {activeEvalCase.name}</p>
                  <GhostBtn onClick={runProjectHarness} disabled={runningHarness}>
                    {runningHarness ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <FlaskConical className="h-3 w-3 mr-1" />}
                    Run + Evaluate
                  </GhostBtn>
                </div>
                <p className="text-[11px] text-[#A8A29A]">
                  Uses the latest saved workflow output, then records deterministic checks and an eval score.
                </p>
                <div className="space-y-1.5">
                  <label className={labelCls}>Evaluate latest output</label>
                  <Select value={selectedRunId} onValueChange={selectRunForEval}>
                    <SelectTrigger className={selectCls}>
                      <SelectValue placeholder={recentRuns.length ? "Choose a recent run" : "No recent successful runs"} />
                    </SelectTrigger>
                    <SelectContent className={selectContentCls}>
                      {recentRuns.map((run) => (
                        <SelectItem key={run.id} value={String(run.id)}>
                          {runLabel(run)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Textarea
                  value={observedOutput}
                  onChange={(e) => setObservedOutput(e.target.value)}
                  rows={5}
                  placeholder="Choose a recent workflow output above, or paste an observed output manually."
                  className={inputCls}
                />
                <AmberBtn onClick={runEval} disabled={runningEval || !observedOutput.trim()} className="w-full">
                  {runningEval ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <FlaskConical className="h-4 w-4 mr-1.5" />}
                  Run pasted eval only
                </AmberBtn>
                {activeImprovementPrompt && (
                  <div className="rounded-md border border-[#2A2A30] px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs font-medium text-[#F2EFE8]">Next improvement prompt</p>
                      <div className="flex items-center gap-1">
                        <button
                          className="inline-flex items-center gap-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
                          onClick={() => {
                            navigator.clipboard.writeText(activeImprovementPrompt);
                            toast.success("Improvement prompt copied");
                          }}
                        >
                          <Copy className="h-3 w-3" /> Copy
                        </button>
                        <GhostBtn onClick={saveImprovementAsUpdate} disabled={savingUpdate}>
                          {savingUpdate ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Save className="h-3 w-3 mr-1" />}
                          Save
                        </GhostBtn>
                      </div>
                    </div>
                    <p className="text-xs text-[#A8A29A] mt-1.5 whitespace-pre-wrap">
                      {activeImprovementPrompt}
                    </p>
                    <AmberBtn onClick={generatePackage} disabled={generating || specDirty} className="w-full mt-2">
                      {generating ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <PackageCheck className="h-4 w-4 mr-1.5" />}
                      Generate package with eval context
                    </AmberBtn>
                  </div>
                )}
              </div>
            )}
          </SectionCard>

          {/* Agent Build Log */}
          <SectionCard
            title="Agent Build Log"
            icon={<Bot className="h-4 w-4 text-[#BCA06A]" />}
          >
            <div className="space-y-1.5">
              <label className={labelCls}>Agent</label>
              <Select value={agent} onValueChange={setAgent}>
                <SelectTrigger className={selectCls}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className={selectContentCls}>
                  <SelectItem value="Claude Code">Claude Code</SelectItem>
                  <SelectItem value="Codex">Codex</SelectItem>
                  <SelectItem value="Manual">Manual</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Summary</label>
              <Textarea value={updateSummary} onChange={(e) => setUpdateSummary(e.target.value)} rows={3} placeholder="What did the agent do or decide?" className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Changed files</label>
              <Textarea value={changedFiles} onChange={(e) => setChangedFiles(e.target.value)} rows={2} placeholder="One per line, or paste the agent summary." className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Commands / tests</label>
              <Textarea value={commandsRun} onChange={(e) => setCommandsRun(e.target.value)} rows={2} placeholder="npm run build, pytest, manual check..." className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Result / blockers / next step</label>
              <Textarea value={testResult} onChange={(e) => setTestResult(e.target.value)} rows={2} placeholder="What passed or failed?" className={inputCls} />
              <Textarea value={blockers} onChange={(e) => setBlockers(e.target.value)} rows={2} placeholder="Blockers or uncertainty." className={inputCls} />
              <Textarea value={nextStep} onChange={(e) => setNextStep(e.target.value)} rows={2} placeholder="What should the next agent do?" className={inputCls} />
            </div>
            <AmberBtn onClick={saveAgentUpdate} disabled={savingUpdate || !updateSummary.trim()} className="w-full">
              {savingUpdate ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Plus className="h-4 w-4 mr-1.5" />}
              Save update
            </AmberBtn>

            <div className="space-y-2 pt-2">
              {project.agent_updates.length === 0 ? (
                <p className="text-xs text-[#A8A29A]">
                  Paste Claude/Codex results here, then generate the next package version.
                </p>
              ) : project.agent_updates.slice(0, 5).map((update) => (
                <div key={update.id} className="rounded-md border border-[#2A2A30] p-3 text-xs space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-[#F2EFE8]">{update.agent}</span>
                    <span className="text-[#A8A29A] font-mono">{update.created_at.slice(0, 16)}</span>
                  </div>
                  <p className="text-[#A8A29A] whitespace-pre-wrap">{update.summary}</p>
                  {update.next_step && (
                    <p className="text-[#BCA06A] whitespace-pre-wrap">Next: {update.next_step}</p>
                  )}
                </div>
              ))}
            </div>
          </SectionCard>
        </div>

        {/* Right column — Execution Package */}
        <div className="rounded-md border border-[#2A2A30] bg-[#141418] overflow-hidden min-w-0">
          <div className="border-b border-[#2A2A30]">
            <div className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-[#F2EFE8]">Execution Package</span>
                {activePackage && (
                  <span className="inline-flex items-center gap-1 text-xs text-[#A8A29A] border border-[#2A2A30] rounded-sm px-1.5 py-0.5 font-mono">
                    <Zap className="h-2.5 w-2.5" />
                    {planningMode.charAt(0).toUpperCase() + planningMode.slice(1)}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {project.execution_packages.length > 0 && (
                  <Select value={String(activePackage?.id ?? "")} onValueChange={(v) => setActivePackageId(Number(v))}>
                    <SelectTrigger className="h-8 w-36 text-xs border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className={selectContentCls}>
                      {project.execution_packages.map((pkg) => (
                        <SelectItem key={pkg.id} value={String(pkg.id)}>
                          v{pkg.version} - {pkg.readiness_score}/{pkg.readiness.checks.length}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                {activePackage && (
                  <>
                    <div className="flex items-center border border-[#2A2A30] rounded-sm overflow-hidden">
                      <button
                        onClick={() => setRawMode(false)}
                        className={`px-2 py-1 text-xs transition-colors ${!rawMode ? "bg-[#1B1C20] text-[#F2EFE8]" : "text-[#A8A29A] hover:text-[#F2EFE8]"}`}
                      >
                        Rendered
                      </button>
                      <button
                        onClick={() => setRawMode(true)}
                        className={`px-2 py-1 text-xs transition-colors ${rawMode ? "bg-[#1B1C20] text-[#F2EFE8]" : "text-[#A8A29A] hover:text-[#F2EFE8]"}`}
                      >
                        <FileCode2 className="h-3 w-3" />
                      </button>
                    </div>
                    <button
                      className="inline-flex items-center gap-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
                      onClick={() => { navigator.clipboard.writeText(activePackage.content_md); toast.success("Package copied"); }}
                    >
                      <Copy className="h-4 w-4" /> All
                    </button>
                    <button
                      className="inline-flex items-center gap-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
                      onClick={downloadPackage}
                    >
                      <Download className="h-4 w-4" /> .md
                    </button>
                  </>
                )}
              </div>
            </div>
            {activePackage && (
              <div className="flex flex-wrap gap-1 px-4 pb-3">
                {COPY_SECTIONS.map((section) => {
                  const content = extractSection(activePackage.content_md, section);
                  if (!content) return null;
                  return (
                    <button
                      key={section}
                      onClick={() => { navigator.clipboard.writeText(content); toast.success(`${section} copied`); }}
                      className="flex items-center gap-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] px-2 py-1 rounded border border-[#2A2A30] hover:border-[#BCA06A]/30 transition-colors"
                    >
                      <Copy className="h-2.5 w-2.5" />
                      {section}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {!activePackage ? (
            <div className="h-[520px] flex items-center justify-center text-center p-8">
              <div>
                <PackageCheck className="h-8 w-8 text-[#BCA06A] mx-auto mb-3" />
                <p className="text-sm font-medium text-[#F2EFE8]">No package yet</p>
                <p className="text-xs text-[#A8A29A] mt-1">
                  Generate v1 to get repo hunt instructions and Claude Code / Codex prompts.
                </p>
              </div>
            </div>
          ) : rawMode ? (
            <ScrollArea className="h-[calc(100vh-280px)]">
              <pre className="p-6 text-xs font-mono text-[#A8A29A] whitespace-pre-wrap break-words leading-relaxed">
                {activePackage.content_md}
              </pre>
            </ScrollArea>
          ) : (
            <ScrollArea className="h-[calc(100vh-280px)]">
              <div className="p-6 prose prose-invert prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{activePackage.content_md}</ReactMarkdown>
              </div>
            </ScrollArea>
          )}
        </div>
      </div>
    </div>
  );
}

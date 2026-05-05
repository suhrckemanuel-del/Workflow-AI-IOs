import type {
  WorkflowMeta,
  RunResponse,
  WorkflowJobStartResponse,
  WorkflowJobStatus,
  RunRecord,
  KBDirectory,
  KBFile,
  ChatMessage,
  ArchitectResponse,
  Settings,
  HealthCheck,
  AutomationProject,
  AutomationProjectCreate,
  AutomationProjectUpdate,
  AgentUpdateCreate,
  EvalCaseCreate,
  PlanningMode,
  ProjectRunAndEvaluateRequest,
  ProjectRunAndEvaluateResponse,
  ReliabilityPlaybook,
  AgentJob,
  AgentJobCreate,
  AgentJobUpdate,
} from "./types";
import type { ClientInfo } from "./client";

const BASE = "/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "API error");
  }
  return res.json() as Promise<T>;
}

export async function getWorkflows(): Promise<WorkflowMeta[]> {
  return apiFetch("/workflows");
}

export async function getWorkflow(id: string): Promise<WorkflowMeta> {
  return apiFetch(`/workflows/${id}`);
}

export async function runWorkflow(
  id: string,
  inputs: Record<string, unknown>,
  test = false,
  client: string | null = null,
): Promise<RunResponse> {
  const qs = new URLSearchParams();
  if (test) qs.set("test", "true");
  if (client) qs.set("client", client);
  const query = qs.toString() ? `?${qs}` : "";
  return apiFetch(`/workflows/${id}/run${query}`, {
    method: "POST",
    body: JSON.stringify({ inputs }),
  });
}

export async function startWorkflowJob(
  id: string,
  inputs: Record<string, unknown>,
  test = false,
  client: string | null = null,
): Promise<WorkflowJobStartResponse> {
  const qs = new URLSearchParams();
  if (test) qs.set("test", "true");
  if (client) qs.set("client", client);
  const query = qs.toString() ? `?${qs}` : "";
  return apiFetch(`/workflows/${id}/run/job${query}`, {
    method: "POST",
    body: JSON.stringify({ inputs }),
  });
}

export async function getWorkflowJob(jobId: string): Promise<WorkflowJobStatus> {
  return apiFetch(`/workflow-jobs/${jobId}`);
}

export async function runWorkflowStream(
  id: string,
  inputs: Record<string, unknown>,
  test: boolean,
  onStatus: (message: string, elapsed: number) => void,
  onResult: (result: RunResponse) => void,
  onError: (err: string) => void,
  client: string | null = null,
): Promise<void> {
  const qs = new URLSearchParams();
  if (test) qs.set("test", "true");
  if (client) qs.set("client", client);
  const query = qs.toString() ? `?${qs}` : "";
  const res = await fetch(`${BASE}/workflows/${id}/run/stream${query}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    onError(err.detail ?? "API error");
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    let eventType = "";
    let eventData = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        eventData = line.slice(6).trim();
      } else if (line === "" && eventType && eventData) {
        try {
          const parsed = JSON.parse(eventData);
          if (eventType === "status") onStatus(parsed.message, parsed.elapsed);
          else if (eventType === "result") onResult(parsed as RunResponse);
          else if (eventType === "error") onError(parsed.message);
        } catch { /* ignore parse errors */ }
        eventType = "";
        eventData = "";
      }
    }
  }
}

export async function getRuns(params?: {
  workflow_id?: string;
  limit?: number;
  offset?: number;
}): Promise<RunRecord[]> {
  const qs = new URLSearchParams();
  if (params?.workflow_id) qs.set("workflow_id", params.workflow_id);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs}` : "";
  return apiFetch(`/runs${query}`);
}

export async function getRun(id: number): Promise<RunRecord> {
  return apiFetch(`/runs/${id}`);
}

export async function getKBFolders(client: string | null = null): Promise<KBDirectory> {
  const q = client ? `?client=${client}` : "";
  return apiFetch(`/kb${q}`);
}

export async function getKBFile(folder: string, filename: string, client: string | null = null): Promise<KBFile> {
  const q = client ? `?client=${client}` : "";
  return apiFetch(`/kb/${folder}/${filename}${q}`);
}

export async function getClients(): Promise<ClientInfo[]> {
  return apiFetch("/clients");
}

export async function architectChat(
  message: string,
  history: ChatMessage[]
): Promise<ArchitectResponse> {
  return apiFetch("/architect/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

export async function deployWorkflow(
  yaml: string,
  workflow_id: string
): Promise<{ success: boolean }> {
  return apiFetch("/architect/deploy", {
    method: "POST",
    body: JSON.stringify({ yaml, workflow_id }),
  });
}

export async function getSettings(): Promise<Settings> {
  return apiFetch("/settings");
}

export async function updateSetting(key: string, value: unknown): Promise<void> {
  await apiFetch("/settings", {
    method: "PUT",
    body: JSON.stringify({ key, value }),
  });
}

export async function getHealth(): Promise<HealthCheck> {
  return apiFetch("/health");
}

export async function getAutomationProjects(): Promise<AutomationProject[]> {
  return apiFetch("/automation-projects");
}

export async function createAutomationProject(
  project: AutomationProjectCreate
): Promise<AutomationProject> {
  return apiFetch("/automation-projects", {
    method: "POST",
    body: JSON.stringify(project),
  });
}

export async function getAutomationProject(id: number): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${id}`);
}

export async function getProjectReliabilityPlaybook(id: number): Promise<ReliabilityPlaybook> {
  return apiFetch(`/automation-projects/${id}/reliability-playbook`);
}

export async function updateAutomationProject(
  id: number,
  updates: AutomationProjectUpdate
): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function addRepoCandidate(
  projectId: number,
  body: { url: string; notes?: string; rank?: number | null }
): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${projectId}/repo-candidates`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function searchRepoIntelligence(projectId: number): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${projectId}/repo-intelligence/search`, {
    method: "POST",
  });
}

export async function deleteRepoCandidate(
  projectId: number,
  candidateId: number,
): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${projectId}/repo-candidates/${candidateId}`, {
    method: "DELETE",
  });
}

export async function addAgentUpdate(
  projectId: number,
  body: AgentUpdateCreate
): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${projectId}/agent-updates`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function addEvalCase(
  projectId: number,
  body: EvalCaseCreate
): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${projectId}/eval-cases`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteEvalCase(
  projectId: number,
  caseId: number,
): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${projectId}/eval-cases/${caseId}`, {
    method: "DELETE",
  });
}

export async function runEvalCase(
  projectId: number,
  caseId: number,
  observedOutput: string,
): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${projectId}/eval-cases/${caseId}/run`, {
    method: "POST",
    body: JSON.stringify({ observed_output: observedOutput }),
  });
}

export async function runAndEvaluateProject(
  projectId: number,
  body: ProjectRunAndEvaluateRequest = {},
): Promise<ProjectRunAndEvaluateResponse> {
  return apiFetch(`/automation-projects/${projectId}/run-and-evaluate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function generateExecutionPackage(projectId: number, planningMode: PlanningMode = "quick"): Promise<AutomationProject> {
  return apiFetch(`/automation-projects/${projectId}/packages/generate`, {
    method: "POST",
    body: JSON.stringify({ planning_mode: planningMode }),
  });
}

export async function getAgents(): Promise<AgentJob[]> {
  return apiFetch("/agents");
}

export async function createAgentJob(body: AgentJobCreate): Promise<AgentJob> {
  return apiFetch("/agents", { method: "POST", body: JSON.stringify(body) });
}

export async function updateAgentJob(id: number, body: AgentJobUpdate): Promise<AgentJob> {
  return apiFetch(`/agents/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function deleteAgentJob(id: number): Promise<void> {
  await apiFetch(`/agents/${id}`, { method: "DELETE" });
}

export async function triggerAgentNow(id: number): Promise<{ success: boolean; last_status: string | null }> {
  return apiFetch(`/agents/${id}/run`, { method: "POST" });
}

export async function listOutputFiles(client: string | null = null): Promise<import("./types").OutputFile[]> {
  const q = client ? `?client=${client}` : "";
  return apiFetch(`/files/list${q}`);
}

export function getFileDownloadUrl(path: string, client: string | null = null): string {
  const qs = new URLSearchParams({ path });
  if (client) qs.set("client", client);
  return `/api/files/download?${qs}`;
}

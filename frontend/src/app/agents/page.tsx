"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Timer, Plus, Trash2, Play, X } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getAgents,
  createAgentJob,
  updateAgentJob,
  deleteAgentJob,
  triggerAgentNow,
  getWorkflows,
  getClients,
} from "@/lib/api";
import type { AgentJob, WorkflowMeta } from "@/lib/types";
import type { ClientInfo } from "@/lib/client";

// ─── cron helpers ─────────────────────────────────────────────────────────────

const CRON_PRESETS = [
  { label: "Every Monday 8am",   value: "0 8 * * 1" },
  { label: "Every day 8am",      value: "0 8 * * *" },
  { label: "Every hour",         value: "0 * * * *" },
  { label: "Custom",             value: "custom" },
];

function humanCron(expr: string): string {
  const preset = CRON_PRESETS.find((p) => p.value === expr && p.value !== "custom");
  if (preset) return preset.label;
  return expr;
}

function relativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ─── status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-[10px] text-[#A8A29A]">—</span>;
  const ok = status === "success";
  return (
    <span
      className={`inline-flex items-center rounded-sm px-2 py-0.5 text-[10px] font-semibold ${
        ok
          ? "border border-[#7BAE7F]/30 bg-[#7BAE7F]/10 text-[#BFE5C2]"
          : "border border-[#6E2B2B]/50 bg-[#6E2B2B]/20 text-[#E2B5AE]"
      }`}
    >
      {ok ? "success" : "error"}
    </span>
  );
}

// ─── toggle ───────────────────────────────────────────────────────────────────

function Toggle({
  enabled,
  onChange,
  disabled,
}: {
  enabled: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors disabled:opacity-40 ${
        enabled ? "bg-[#7C3AED]" : "bg-[#3A3A40]"
      }`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${
          enabled ? "translate-x-4" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

// ─── new agent form ───────────────────────────────────────────────────────────

function NewAgentForm({
  workflows,
  clients,
  onCreated,
  onClose,
}: {
  workflows: WorkflowMeta[];
  clients: ClientInfo[];
  onCreated: (job: AgentJob) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [workflowId, setWorkflowId] = useState("");
  const [preset, setPreset] = useState("0 8 * * 1");
  const [customCron, setCustomCron] = useState("");
  const [inputsText, setInputsText] = useState("{}");
  const [clientId, setClientId] = useState<string>("");
  const [saving, setSaving] = useState(false);

  const selectedWorkflow = workflows.find((w) => w.id === workflowId);

  function buildDefaultInputs(wf: WorkflowMeta): string {
    const obj: Record<string, string> = {};
    for (const inp of wf.inputs) obj[inp.key] = inp.placeholder || "";
    return JSON.stringify(obj, null, 2);
  }

  function handleWorkflowChange(id: string) {
    setWorkflowId(id);
    const wf = workflows.find((w) => w.id === id);
    if (wf) setInputsText(buildDefaultInputs(wf));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const cron = preset === "custom" ? customCron.trim() : preset;
    if (!name.trim() || !workflowId || !cron) {
      toast.error("Name, workflow, and schedule are required.");
      return;
    }
    let inputs: Record<string, unknown> = {};
    try {
      inputs = JSON.parse(inputsText);
    } catch {
      toast.error("Inputs must be valid JSON.");
      return;
    }
    setSaving(true);
    try {
      const job = await createAgentJob({
        name: name.trim(),
        workflow_id: workflowId,
        cron_expr: cron,
        inputs,
        client_id: (clientId && clientId !== "default") ? clientId : null,
      });
      toast.success(`Agent "${job.name}" created.`);
      onCreated(job);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to create agent");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-md border border-[#7C3AED]/40 bg-[#141418] p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-[#F2EFE8]">New Agent</h2>
        <button type="button" onClick={onClose} className="text-[#A8A29A] hover:text-[#F2EFE8] transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="space-y-1">
          <label className="text-[11px] text-[#A8A29A] uppercase tracking-wide">Name</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Weekly Portfolio Monitor"
            className="bg-[#0E0E10] border-[#2A2A30] text-[#F2EFE8] text-sm"
          />
        </div>

        <div className="space-y-1">
          <label className="text-[11px] text-[#A8A29A] uppercase tracking-wide">Workflow</label>
          <Select value={workflowId} onValueChange={handleWorkflowChange}>
            <SelectTrigger className="bg-[#0E0E10] border-[#2A2A30] text-[#F2EFE8] text-sm">
              <SelectValue placeholder="Select workflow…" />
            </SelectTrigger>
            <SelectContent className="bg-[#1B1C20] border-[#2A2A30] text-[#F2EFE8]">
              {workflows.map((wf) => (
                <SelectItem key={wf.id} value={wf.id}>{wf.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-[11px] text-[#A8A29A] uppercase tracking-wide">Schedule</label>
          <Select value={preset} onValueChange={setPreset}>
            <SelectTrigger className="bg-[#0E0E10] border-[#2A2A30] text-[#F2EFE8] text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#1B1C20] border-[#2A2A30] text-[#F2EFE8]">
              {CRON_PRESETS.map((p) => (
                <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {preset === "custom" && (
            <Input
              value={customCron}
              onChange={(e) => setCustomCron(e.target.value)}
              placeholder="0 8 * * 1  (minute hour day month weekday)"
              className="mt-1 bg-[#0E0E10] border-[#2A2A30] text-[#F2EFE8] text-sm font-mono"
            />
          )}
        </div>

        {selectedWorkflow && (
          <div className="space-y-1">
            <label className="text-[11px] text-[#A8A29A] uppercase tracking-wide">Default Inputs (JSON)</label>
            <Textarea
              value={inputsText}
              onChange={(e) => setInputsText(e.target.value)}
              rows={4}
              className="bg-[#0E0E10] border-[#2A2A30] text-[#F2EFE8] text-xs font-mono resize-none"
            />
          </div>
        )}

        {clients.length > 0 && (
          <div className="space-y-1">
            <label className="text-[11px] text-[#A8A29A] uppercase tracking-wide">Client (optional)</label>
            <Select value={clientId} onValueChange={setClientId}>
              <SelectTrigger className="bg-[#0E0E10] border-[#2A2A30] text-[#F2EFE8] text-sm">
                <SelectValue placeholder="Default workspace" />
              </SelectTrigger>
              <SelectContent className="bg-[#1B1C20] border-[#2A2A30] text-[#F2EFE8]">
                <SelectItem value="default">Default workspace</SelectItem>
                {clients.filter((c) => !!c.id).map((c) => (
                  <SelectItem key={c.id!} value={c.id!}>{c.display_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-[#2A2A30] px-3 py-1.5 text-xs text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="rounded bg-[#7C3AED] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#6D28D9] disabled:opacity-50 transition-colors"
          >
            {saving ? "Creating…" : "Create Agent"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ─── page ─────────────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentJob[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowMeta[]>([]);
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [toggling, setToggling] = useState<number | null>(null);
  const [triggering, setTriggering] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  useEffect(() => {
    Promise.allSettled([getAgents(), getWorkflows(), getClients()]).then(
      ([agentsRes, wfRes, clientsRes]) => {
        if (agentsRes.status === "fulfilled") setAgents(agentsRes.value);
        if (wfRes.status === "fulfilled") setWorkflows(wfRes.value);
        if (clientsRes.status === "fulfilled") setClients(clientsRes.value);
      }
    ).finally(() => setLoading(false));
  }, []);

  async function handleToggle(agent: AgentJob) {
    setToggling(agent.id);
    try {
      const updated = await updateAgentJob(agent.id, { enabled: !agent.enabled });
      setAgents((prev) => prev.map((a) => (a.id === agent.id ? updated : a)));
      toast.success(`Agent ${updated.enabled ? "enabled" : "disabled"}.`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    } finally {
      setToggling(null);
    }
  }

  async function handleDelete(agent: AgentJob) {
    setDeleting(agent.id);
    try {
      await deleteAgentJob(agent.id);
      setAgents((prev) => prev.filter((a) => a.id !== agent.id));
      toast.success(`Agent "${agent.name}" deleted.`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(null);
    }
  }

  async function handleTrigger(agent: AgentJob) {
    setTriggering(agent.id);
    try {
      const res = await triggerAgentNow(agent.id);
      toast.success(`Run complete — status: ${res.last_status ?? "unknown"}`);
      const fresh = await getAgents();
      setAgents(fresh);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Trigger failed");
    } finally {
      setTriggering(null);
    }
  }

  function handleCreated(job: AgentJob) {
    setAgents((prev) => [job, ...prev]);
    setShowForm(false);
  }

  const wfName = (id: string) =>
    workflows.find((w) => w.id === id)?.name ?? id.replace(/_/g, " ");

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#F2EFE8]">Agents</h1>
          <p className="text-sm text-[#A8A29A] mt-1">
            Workflows that run automatically on a schedule
          </p>
        </div>
        {!showForm && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-1.5 rounded bg-[#7C3AED] px-3 py-1.5 text-sm font-semibold text-white hover:bg-[#6D28D9] transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            New Agent
          </button>
        )}
      </div>

      {/* New agent form */}
      {showForm && (
        <NewAgentForm
          workflows={workflows}
          clients={clients}
          onCreated={handleCreated}
          onClose={() => setShowForm(false)}
        />
      )}

      {/* Agent list */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-14 rounded-md" />
          ))}
        </div>
      ) : agents.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-[#2A2A30] py-16 text-center">
          <Timer className="h-8 w-8 text-[#3A3A40] mb-3" />
          <p className="text-sm font-medium text-[#F2EFE8]">No agents yet</p>
          <p className="text-xs text-[#A8A29A] mt-1">
            Create one to run workflows automatically.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="flex items-center gap-3 rounded-md border border-[#2A2A30] bg-[#141418] px-4 py-3 hover:bg-[#1B1C20] transition-colors"
            >
              {/* Enable toggle */}
              <Toggle
                enabled={agent.enabled}
                onChange={() => handleToggle(agent)}
                disabled={toggling === agent.id}
              />

              {/* Info */}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[#F2EFE8] truncate">{agent.name}</p>
                <p className="text-[10px] text-[#A8A29A] truncate">
                  {wfName(agent.workflow_id)} · {humanCron(agent.cron_expr)}
                </p>
              </div>

              {/* Last run */}
              <div className="hidden sm:flex flex-col items-end shrink-0 gap-0.5">
                <StatusBadge status={agent.last_status} />
                <span className="text-[10px] text-[#A8A29A] font-mono">
                  {relativeTime(agent.last_run_at)}
                </span>
              </div>

              {/* Run now */}
              <button
                type="button"
                disabled={triggering === agent.id}
                onClick={() => handleTrigger(agent)}
                title="Run now"
                className="inline-flex shrink-0 items-center gap-1 rounded border border-[#2A2A30] px-2 py-1 text-[10px] text-[#A8A29A] hover:border-[#7C3AED]/40 hover:text-[#F2EFE8] disabled:opacity-40 transition-colors"
              >
                <Play className="h-2.5 w-2.5" />
                {triggering === agent.id ? "Running…" : "Run now"}
              </button>

              {/* Delete */}
              <button
                type="button"
                disabled={deleting === agent.id}
                onClick={() => handleDelete(agent)}
                title="Delete agent"
                className="shrink-0 text-[#A8A29A] hover:text-[#D7827E] disabled:opacity-40 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

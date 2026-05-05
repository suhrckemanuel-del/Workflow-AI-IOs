"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle, XCircle, ChevronDown, ChevronRight, RotateCcw } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { RunTrustPanel } from "@/components/RunTrustPanel";
import { getRuns, getWorkflows, runWorkflow } from "@/lib/api";
import type { RunRecord, WorkflowMeta } from "@/lib/types";

export default function HistoryPage() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowMeta[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [rerunning, setRerunning] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getRuns({ limit: 100 }),
      getWorkflows(),
    ]).then(([r, wf]) => {
      setRuns(r);
      setWorkflows(wf);
    }).finally(() => setLoading(false));
  }, []);

  const filtered = filter === "all" ? runs : runs.filter((r) => r.workflow_id === filter);

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleRerun(run: RunRecord) {
    const meta = workflows.find((w) => w.id === run.workflow_id);
    if (!meta) return;
    setRerunning(run.id);
    try {
      const inputs = JSON.parse(run.inputs_json ?? "{}");
      const res = await runWorkflow(run.workflow_id, inputs);
      if (res.status === "success") {
        toast.success(`Re-run done in ${res.duration_seconds}s`);
        const fresh = await getRuns({ limit: 100 });
        setRuns(fresh);
      } else {
        toast.error(res.error ?? "Re-run failed");
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setRerunning(null);
    }
  }

  function parseJson(s: string | null) {
    if (!s) return null;
    try { return JSON.parse(s); } catch { return null; }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">History</h1>
          <p className="text-[#A8A29A] text-sm mt-1">{runs.length} total runs</p>
        </div>
        <Select value={filter} onValueChange={setFilter}>
          <SelectTrigger className="w-48 border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
            <SelectValue placeholder="Filter by workflow" />
          </SelectTrigger>
          <SelectContent className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
            <SelectItem value="all">All workflows</SelectItem>
            {workflows.map((w) => (
              <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14 rounded-md" />)}
        </div>
      ) : filtered.length === 0 ? (
        <p className="text-[#A8A29A] text-sm">No runs found.</p>
      ) : (
        <div className="space-y-2">
          {filtered.map((run) => {
            const open = expanded.has(run.id);
            const outputs = parseJson(run.outputs_json);
            const inputs = parseJson(run.inputs_json);
            const meta = workflows.find((w) => w.id === run.workflow_id);
            const primaryField = meta?.primary_display_field;
            const primaryOutput = outputs && primaryField ? (outputs[primaryField] as string | undefined) : null;

            return (
              <div key={run.id} className="border border-[#2A2A30] rounded-md overflow-hidden bg-[#141418]">
                {/* Row */}
                <div
                  className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[#1B1C20] transition-colors"
                  onClick={() => toggle(run.id)}
                >
                  {run.status === "success"
                    ? <CheckCircle className="h-4 w-4 text-[#7BAE7F] shrink-0" />
                    : <XCircle className="h-4 w-4 text-[#D7827E] shrink-0" />}

                  <span className="font-medium text-sm text-[#F2EFE8]">{run.workflow_id.replace(/_/g, " ")}</span>

                  {(() => {
                    try {
                      const inp = JSON.parse(run.inputs_json ?? "{}");
                      if (inp._scheduled) {
                        return (
                          <span className="inline-flex items-center gap-1 rounded-sm border border-[#7C3AED]/30 bg-[#7C3AED]/10 px-2 py-0.5 text-[10px] font-medium text-[#A78BFA]">
                            scheduled
                          </span>
                        );
                      }
                    } catch { /* ignore */ }
                    return null;
                  })()}

                  {run.status === "success" ? (
                    <span className="border border-[#7BAE7F]/30 bg-[#7BAE7F]/10 text-[#BFE5C2] rounded-sm px-2 py-0.5 text-[11px] font-medium">
                      {run.status}
                    </span>
                  ) : (
                    <span className="border border-[#6E2B2B]/50 bg-[#6E2B2B]/20 text-[#E2B5AE] rounded-sm px-2 py-0.5 text-[11px] font-medium">
                      {run.status}
                    </span>
                  )}

                  <span className="font-mono text-xs text-[#A8A29A] ml-auto">{run.duration_s}s</span>
                  <span className="font-mono text-xs text-[#A8A29A]">{run.created_at.slice(0, 16)}</span>

                  <button
                    disabled={rerunning === run.id}
                    onClick={(e) => { e.stopPropagation(); handleRerun(run); }}
                    className="inline-flex items-center gap-1 border border-[#2A2A30] rounded-md px-2 py-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] hover:border-[#BCA06A]/40 disabled:opacity-50 transition-colors"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Re-run
                  </button>

                  {open
                    ? <ChevronDown className="h-4 w-4 text-[#A8A29A] shrink-0" />
                    : <ChevronRight className="h-4 w-4 text-[#A8A29A] shrink-0" />}
                </div>

                {/* Expanded */}
                {open && (
                  <div className="border-t border-[#2A2A30] px-4 py-4 bg-[#111113] space-y-4 text-sm">
                    {inputs && (
                      <div>
                        <p className="text-[11px] text-[#A8A29A] font-medium mb-2 uppercase tracking-[0.08em]">Inputs</p>
                        <div className="grid grid-cols-2 gap-2">
                          {Object.entries(inputs).map(([k, v]) => (
                            <div key={k} className="space-y-0.5">
                              <p className="text-xs text-[#A8A29A]">{k}</p>
                              <p className="text-xs font-mono truncate text-[#F2EFE8]">{String(v)}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <RunTrustPanel trust={run.trust_report} compact />

                    {run.status === "error" ? (
                      <p className="text-[#D7827E] text-xs">{run.error_message}</p>
                    ) : primaryOutput ? (
                      <div>
                        <p className="text-[11px] text-[#A8A29A] font-medium mb-2 uppercase tracking-[0.08em]">Output preview</p>
                        <p className="text-xs text-[#A8A29A] line-clamp-4 whitespace-pre-wrap">
                          {primaryOutput.slice(0, 600)}{primaryOutput.length > 600 ? "…" : ""}
                        </p>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

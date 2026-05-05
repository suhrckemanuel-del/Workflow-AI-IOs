"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Play, Loader2, Copy, ChevronDown, FlaskConical, ExternalLink,
  Bot, Search, Mail, ClipboardList, BarChart3, MessageSquareReply, Linkedin, Radar,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { RunTrustPanel } from "@/components/RunTrustPanel";
import { DealDeskWorkflowPage } from "@/components/deal-desk/DealDeskWorkflowPage";
import { getWorkflow, startWorkflowJob, getWorkflowJob } from "@/lib/api";
import { getActiveClient } from "@/lib/client";
import type { WorkflowMeta, RunResponse } from "@/lib/types";

const ICONS: Record<string, typeof Bot> = {
  company_research: Search,
  email_drafting: Mail,
  meeting_prep: ClipboardList,
  portfolio_monitor: BarChart3,
  customer_support_reply: MessageSquareReply,
  linkedin_post_gen: Linkedin,
  vc_lead_scraper: Radar,
};

function obsidianLink(filePath: string): string {
  if (!filePath) return "";
  return `obsidian://open?path=${encodeURIComponent(filePath)}`;
}

export default function WorkflowPage() {
  const { id } = useParams<{ id: string }>();
  const [meta, setMeta] = useState<WorkflowMeta | null>(null);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [testMode, setTestMode] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<RunResponse | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const id = window.location.pathname.split("/").pop() ?? "";
      const saved = localStorage.getItem(`aios_workflow_result_${id}`);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [loadError, setLoadError] = useState<string | null>(null);

  const jobStorageKey = `aios_workflow_job_${id}`;
  const resultStorageKey = `aios_workflow_result_${id}`;

  useEffect(() => {
    setLoading(true);
    setLoadError(null);
    getWorkflow(id)
      .then((m) => {
        setMeta(m);
        const defaults: Record<string, string> = {};
        m.inputs.forEach((i) => { defaults[i.key] = ""; });
        setInputs(defaults);
      })
      .catch((e: unknown) => {
        setMeta(null);
        setLoadError(e instanceof Error ? e.message : "Could not load workflow");
      })
      .finally(() => setLoading(false));
  }, [id, resultStorageKey]);

  useEffect(() => {
    const existingJobId = localStorage.getItem(jobStorageKey);
    if (!existingJobId) return;
    setRunning(true);
    setStatusMsg("Resuming workflow run...");
    pollJob(existingJobId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobStorageKey]);

  async function pollJob(jobId: string) {
    try {
      const job = await getWorkflowJob(jobId);
      setElapsed(job.elapsed_seconds);
      setStatusMsg(job.message);

      if (job.status === "running") {
        window.setTimeout(() => pollJob(jobId), 1200);
        return;
      }

      localStorage.removeItem(jobStorageKey);
      setRunning(false);

      if (job.response) {
        setResult(job.response);
        try { localStorage.setItem(resultStorageKey, JSON.stringify(job.response)); } catch { /* ignore */ }
        if (job.response.status === "success") {
          toast.success(`Done in ${job.response.duration_seconds}s`);
        } else {
          toast.error(job.response.error ?? "Workflow failed");
        }
        return;
      }

      const errorResult: RunResponse = {
        status: "error",
        result: null,
        duration_seconds: job.elapsed_seconds,
        run_id: null,
        error: job.error ?? "Workflow job failed",
        trust_report: null,
      };
      setResult(errorResult);
      try { localStorage.setItem(resultStorageKey, JSON.stringify(errorResult)); } catch { /* ignore */ }
      toast.error(job.error ?? "Workflow job failed");
    } catch (e: unknown) {
      localStorage.removeItem(jobStorageKey);
      setRunning(false);
      toast.error(e instanceof Error ? e.message : "Could not resume workflow job");
    }
  }

  async function handleRun() {
    if (!meta) return;
    const missing = meta.inputs.filter((i) => i.required && !inputs[i.key]?.trim());
    if (missing.length > 0) {
      toast.error(`Fill in: ${missing.map((i) => i.label).join(", ")}`);
      return;
    }

    setRunning(true);
    setStatusMsg("Starting...");
    setElapsed(0);

    const payload: Record<string, unknown> = {};
    meta.inputs.forEach((i) => {
      payload[i.key] = i.type === "multiline"
        ? (inputs[i.key] ?? "").split("\n").filter(Boolean)
        : inputs[i.key] ?? "";
    });

    try {
      const job = await startWorkflowJob(id, payload, testMode, getActiveClient());
      localStorage.setItem(jobStorageKey, job.job_id);
      pollJob(job.job_id);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Unexpected error");
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-2xl space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-80" />
        <div className="space-y-3 mt-6">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="max-w-3xl rounded-md border border-[#6E2B2B]/40 bg-[#6E2B2B]/10 p-6">
        <h1 className="text-lg font-semibold text-[#F2EFE8]">Workflow could not load</h1>
        <p className="mt-2 text-sm text-[#A8A29A]">
          The frontend could not reach the AI-OS API for this workflow. Make sure FastAPI is running on{" "}
          <span className="font-mono text-[#F2EFE8]">localhost:8000</span>.
        </p>
        <p className="mt-3 rounded-md border border-[#2A2A30] bg-[#1B1C20] px-3 py-2 font-mono text-xs text-[#A8A29A]">
          {loadError}
        </p>
      </div>
    );
  }

  if (!meta) return <p className="text-[#A8A29A]">Workflow not found.</p>;
  const HeaderIcon = ICONS[meta.id] ?? Bot;

  const output = result?.status === "success" && result.result
    ? (result.result[meta.primary_display_field] as string | undefined)
    : null;

  const filePath = result?.result?.file_path ? String(result.result.file_path) : null;
  const obsidianUrl = filePath ? obsidianLink(filePath) : "";
  const sources = Array.isArray(result?.result?.sources)
    ? (result.result.sources as Array<string | { title?: string; url?: string }>).map((source) => (
      typeof source === "string" ? { title: source, url: source } : source
    ))
    : [];

  if (meta.id === "vc_lead_scraper" || meta.id === "vc_outreach_drafts") {
    return (
      <DealDeskWorkflowPage
        meta={meta}
        inputs={inputs}
        setInputs={setInputs}
        running={running}
        testMode={testMode}
        setTestMode={setTestMode}
        statusMsg={statusMsg}
        elapsed={elapsed}
        result={result}
        output={output ?? null}
        filePath={filePath}
        obsidianUrl={obsidianUrl}
        sources={sources}
        onRun={handleRun}
      />
    );
  }

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <HeaderIcon className="h-6 w-6 text-[#BCA06A]" />
          <h1 className="text-2xl font-bold">{meta.name}</h1>
          {meta.requires_exa && (
            <span className="border border-[#BCA06A]/30 bg-[#BCA06A]/10 text-[#E6D2A4] rounded-sm px-2 py-0.5 text-[11px] font-medium">
              Live search
            </span>
          )}
        </div>
        <p className="text-[#A8A29A] text-sm">{meta.description}</p>
      </div>

      <div className="space-y-5">
        {meta.inputs.map((field) => (
          <div key={field.key} className="space-y-1.5">
            <label className="text-sm font-medium text-[#F2EFE8]">
              {field.label}
              {!field.required && <span className="text-[#A8A29A] font-normal ml-1">(optional)</span>}
            </label>

            {field.type === "select" ? (
              <Select
                value={inputs[field.key] ?? ""}
                onValueChange={(v) => setInputs((p) => ({ ...p, [field.key]: v }))}
              >
                <SelectTrigger className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] focus:ring-[#BCA06A]">
                  <SelectValue placeholder="Select..." />
                </SelectTrigger>
                <SelectContent className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
                  {field.choices.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            ) : field.type === "textarea" || field.type === "multiline" ? (
              <Textarea
                placeholder={field.placeholder}
                value={inputs[field.key] ?? ""}
                onChange={(e) => setInputs((p) => ({ ...p, [field.key]: e.target.value }))}
                rows={field.type === "multiline" ? 4 : 3}
                className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
              />
            ) : (
              <Input
                placeholder={field.placeholder}
                value={inputs[field.key] ?? ""}
                onChange={(e) => setInputs((p) => ({ ...p, [field.key]: e.target.value }))}
                className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
              />
            )}
          </div>
        ))}

        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={handleRun}
            disabled={running}
            className="inline-flex items-center rounded-md bg-[#EEE8DC] px-4 h-10 text-sm font-semibold text-[#171717] hover:bg-[#DED4C3] disabled:opacity-50"
          >
            {running ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> {testMode ? "Testing..." : "Running..."}</>
            ) : (
              <><Play className="mr-2 h-4 w-4" /> {testMode ? "Test run" : "Run"}</>
            )}
          </button>

          <button
            onClick={() => { setTestMode((t) => !t); setResult(null); }}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border transition-colors ${
              testMode
                ? "border-[#C8903D]/40 bg-[#C8903D]/10 text-[#E8C982]"
                : "border-[#2A2A30] text-[#A8A29A] hover:border-[#BCA06A]/40 hover:text-[#F2EFE8]"
            }`}
          >
            <FlaskConical className="h-3.5 w-3.5" />
            Test mode {testMode ? "on" : "off"}
          </button>

          {testMode && (
            <p className="text-xs text-[#A8A29A]">
              Output shown but <span className="font-medium text-[#F2EFE8]">not saved</span> to the knowledge base.
            </p>
          )}
        </div>
      </div>

      {running && (
        <div className="flex items-center gap-3 border border-[#2A2A30] bg-[#141418] rounded-md px-4 py-3">
          <Loader2 className="h-4 w-4 animate-spin text-[#BCA06A] shrink-0" />
          <span className="text-sm text-[#A8A29A]">{statusMsg}</span>
          <span className="ml-auto font-mono text-xs text-[#A8A29A]">{elapsed}s</span>
        </div>
      )}

      {result && !running && (
        <div className="border border-[#2A2A30] rounded-md overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-[#141418] border-b border-[#2A2A30]">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-[#A8A29A]">
                {result.status === "success" ? `OK ${result.duration_seconds}s` : "Error"}
              </span>
              {testMode && (
                <span className="flex items-center gap-1 text-xs text-[#BCA06A] font-medium">
                  <FlaskConical className="h-3 w-3" /> test - not saved
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              {obsidianUrl && !testMode && (
                <a
                  href={obsidianUrl}
                  className="flex items-center gap-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
                  title="Open in Obsidian"
                >
                  <ExternalLink className="h-3 w-3" /> Obsidian
                </a>
              )}
              {output && (
                <button
                  onClick={() => { navigator.clipboard.writeText(output); toast.success("Copied"); }}
                  className="flex items-center gap-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
                >
                  <Copy className="h-3 w-3" /> Copy
                </button>
              )}
            </div>
          </div>

          <div className="p-5">
            <RunTrustPanel trust={result.trust_report} compact />

            {result.status === "error" ? (
              <p className="mt-5 text-[#D7827E] text-sm">{result.error}</p>
            ) : output ? (
              <div className="prose prose-invert prose-sm max-w-none mt-5">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{output}</ReactMarkdown>
              </div>
            ) : (
              <pre className="mt-5 text-xs text-[#A8A29A] whitespace-pre-wrap">
                {JSON.stringify(result.result, null, 2)}
              </pre>
            )}

            {sources.length > 0 && (
              <details className="mt-4 border-t border-[#2A2A30] pt-3">
                <summary className="text-xs text-[#A8A29A] cursor-pointer flex items-center gap-1">
                  <ChevronDown className="h-3 w-3" />
                  {sources.length} sources
                </summary>
                <ul className="mt-2 space-y-1">
                  {sources.map((s, i) => (
                    <li key={i} className="text-xs text-[#A8A29A]">
                      {s.url
                        ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="hover:text-[#F2EFE8] underline">{s.title ?? s.url}</a>
                        : s.title}
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {filePath && !testMode && (
              <p className="mt-3 font-mono text-xs text-[#A8A29A]">
                Saved to {filePath}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  ChevronRight,
  Copy,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  FlaskConical,
  Loader2,
  MoreHorizontal,
  Play,
  Radar,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  normalizeOutreachDrafts,
  parseVcLeadCsv,
  resultNumber,
  resultString,
  type VcLeadRow,
} from "@/lib/deal-desk";
import type { RunResponse, WorkflowMeta } from "@/lib/types";
import { LeadReviewTable } from "./LeadReviewTable";
import { OutreachDraftQueue } from "./OutreachDraftQueue";
import { TrustLayerInspector } from "./TrustLayerInspector";

type SourceLink = {
  title?: string;
  url?: string;
};

type DealDeskWorkflowPageProps = {
  meta: WorkflowMeta;
  inputs: Record<string, string>;
  setInputs: Dispatch<SetStateAction<Record<string, string>>>;
  running: boolean;
  testMode: boolean;
  setTestMode: Dispatch<SetStateAction<boolean>>;
  statusMsg: string;
  elapsed: number;
  result: RunResponse | null;
  output: string | null;
  filePath: string | null;
  obsidianUrl: string;
  sources: SourceLink[];
  onRun: () => void;
};

function makeWorkflowSteps(metaName: string) {
  return [
    { name: "Run",      sub: () => metaName },
    { name: "Research", sub: (r: RunResponse | null) => r?.run_id ? `#${r.run_id} complete` : "Ready" },
    { name: "Validate", sub: (r: RunResponse | null) => r?.trust_report?.evidence.source_count ? `${r.trust_report.evidence.source_count} sources` : "Pending" },
    { name: "Save",     sub: (r: RunResponse | null) => r?.trust_report?.validation.status === "warn" ? "Warnings" : r?.trust_report ? "Passed" : "Pending" },
    { name: "Draft",    sub: (r: RunResponse | null) => r?.trust_report?.evidence.saved_file_count ? "Saved" : "Pending" },
    { name: "Send",     sub: () => "Create drafts" },
  ];
}

function workflowResultKind(meta: WorkflowMeta) {
  if (meta.id === "vc_lead_scraper") return "leads";
  if (meta.id === "vc_outreach_drafts") return "drafts";
  return "generic";
}

function statusChip(result: RunResponse | null, running: boolean, testMode: boolean) {
  if (running) return { text: "Run in progress", className: "border-[#BCA06A]/30 bg-[#BCA06A]/10 text-[#E6D2A4]" };
  if (result?.status === "success") {
    return {
      text: testMode ? `Test complete ${result.duration_seconds}s` : `Run #${result.run_id ?? "local"} complete`,
      className: "border-[#7BAE7F]/30 bg-[#7BAE7F]/10 text-[#BFE5C2]",
    };
  }
  if (result?.status === "error") {
    return { text: "Run failed", className: "border-[#6E2B2B]/50 bg-[#6E2B2B]/20 text-[#E2B5AE]" };
  }
  return { text: "Ready to run", className: "border-[#2A2A30] bg-[#1B1C20] text-[#A8A29A]" };
}

function stepState(index: number, result: RunResponse | null, running: boolean): "done" | "warning" | "current" | "pending" {
  if (running) {
    if (index === 0) return "done";
    if (index === 1) return "current";
    return "pending";
  }
  if (result?.status === "success") {
    const hasWarning = result.trust_report?.validation.status === "warn";
    if (index === 2 && hasWarning) return "warning";
    if (index <= 3) return "done";
    if (index === 4) return "current";
    return "pending";
  }
  if (result?.status === "error") return "pending";
  if (index === 0) return "current";
  return "pending";
}

function metricCards({
  kind,
  result,
  leadRows,
  selectedLead,
  drafts,
  sources,
  csvPath,
}: {
  kind: "leads" | "drafts" | "generic";
  result: RunResponse | null;
  leadRows: VcLeadRow[];
  selectedLead: VcLeadRow | null;
  drafts: ReturnType<typeof normalizeOutreachDrafts>;
  sources: SourceLink[];
  csvPath: string;
}) {
  if (kind === "drafts") {
    const blocked = drafts.filter((draft) => draft.reviewStatus === "blocked").length;
    const needsReview = resultNumber(result?.result, "needs_review_count") ?? drafts.length - blocked;
    return [
      [String(drafts.length), "Drafts processed", "Manual-review drafts only"],
      [String(needsReview), "Need review", "No automatic sending"],
      [String(blocked), "Blocked", "Evidence/contact gaps"],
      [resultString(result?.result, "review_queue_csv_path") ? "1" : "0", "Queue saved", "Review CSV artifact"],
    ];
  }

  return [
    [String(resultNumber(result?.result, "leads_found") ?? leadRows.length), "Leads found", "Ranked against target profile"],
    [selectedLead?.fitScore != null ? String(selectedLead.fitScore) : "-", "Selected score", selectedLead?.fundName ?? "No lead selected"],
    [String(result?.trust_report?.evidence.source_count ?? sources.length), "Web sources", "Evidence attached to run"],
    [csvPath ? "1" : "0", "CSV saved", csvPath ? "Ready for review queue" : "Run to create artifact"],
  ];
}

function DealDeskField({
  field,
  value,
  onChange,
}: {
  field: WorkflowMeta["inputs"][number];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-[#F2EFE8]">
        {field.label}
        {!field.required && <span className="ml-1 font-normal text-[#A8A29A]">(optional)</span>}
      </label>
      {field.type === "select" ? (
        <Select value={value} onValueChange={onChange}>
          <SelectTrigger className="border-[#2A2A30] bg-[#151519] text-[#F2EFE8] focus:ring-[#BCA06A]">
            <SelectValue placeholder="Select..." />
          </SelectTrigger>
          <SelectContent className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
            {field.choices.map((choice) => (
              <SelectItem key={choice} value={choice} className="focus:bg-[#EEE8DC] focus:text-[#171717]">
                {choice}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : field.type === "textarea" || field.type === "multiline" ? (
        <Textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={field.placeholder}
          rows={field.type === "multiline" ? 4 : 3}
          className="border-[#2A2A30] bg-[#151519] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
        />
      ) : (
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={field.placeholder}
          className="border-[#2A2A30] bg-[#151519] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
        />
      )}
    </div>
  );
}

function RunConfigurationPanel({
  meta,
  inputs,
  setInputs,
  running,
  testMode,
  setTestMode,
  onRun,
}: Pick<DealDeskWorkflowPageProps, "meta" | "inputs" | "setInputs" | "running" | "testMode" | "setTestMode" | "onRun">) {
  return (
    <section className="rounded-md border border-[#2A2A30] bg-[#1B1C20] p-4 text-[#F2EFE8]">
      <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-sm font-semibold">Run Configuration</h2>
          <p className="mt-1 text-xs leading-relaxed text-[#A8A29A]">{meta.description}</p>
        </div>
        {meta.requires_exa && (
          <span className="rounded-sm border border-[#BCA06A]/30 bg-[#BCA06A]/10 px-2 py-1 text-[11px] font-medium text-[#E6D2A4]">
            Live research
          </span>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {meta.inputs.map((field) => (
          <DealDeskField
            key={field.key}
            field={field}
            value={inputs[field.key] ?? ""}
            onChange={(value) => setInputs((previous) => ({ ...previous, [field.key]: value }))}
          />
        ))}
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onRun}
          disabled={running}
          className="inline-flex h-10 items-center justify-center rounded-md bg-[#EEE8DC] px-4 text-sm font-semibold text-[#171717] hover:bg-[#DED4C3] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
          {running ? (testMode ? "Testing..." : "Running...") : testMode ? "Test run" : "Run workflow"}
        </button>

        <button
          type="button"
          onClick={() => setTestMode((value) => !value)}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-xs transition-colors",
            testMode
              ? "border-[#C8903D]/40 bg-[#C8903D]/10 text-[#E8C982]"
              : "border-[#2A2A30] text-[#A8A29A] hover:border-[#BCA06A]/40 hover:text-[#F2EFE8]"
          )}
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
    </section>
  );
}

function SelectedLeadDossier({ lead }: { lead: VcLeadRow | null }) {
  if (!lead) {
    return (
      <section className="rounded-md border border-[#2A2A30] bg-[#1B1C20] p-4 text-[#F2EFE8]">
        <p className="text-xs font-medium uppercase tracking-[0.08em] text-[#A8A29A]">Lead review</p>
        <p className="mt-2 text-xs leading-relaxed text-[#A8A29A]">
          Run VC Lead Finder to review fit, evidence, contact route, and validation for each lead.
        </p>
      </section>
    );
  }

  const evidenceCount = lead.evidenceUrl ? 1 : 0;

  return (
    <section className="rounded-md border border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
      <div className="border-b border-[#2A2A30] px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-[0.08em] text-[#A8A29A]">Lead review</p>
        <div className="mt-2 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-2xl font-semibold">{lead.fundName}</h2>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-[#A8A29A]">
              {lead.geography && <span>{lead.geography}</span>}
              {lead.geography && lead.fundType && <span className="text-[#2A2A30]">·</span>}
              {lead.fundType && <span>{lead.fundType}</span>}
            </div>
          </div>
          <div className="shrink-0 rounded-md border border-[#2A2A30] px-3 py-2 text-center">
            <p className="text-[10px] text-[#A8A29A]">Fit score</p>
            <p className="font-mono text-2xl font-semibold text-[#F2EFE8]">{lead.fitScore ?? "-"}</p>
          </div>
        </div>
      </div>

      <div className="space-y-4 p-4">
        {/* Thesis notes */}
        <div>
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-[#A8A29A]">Thesis notes</p>
          <p className="text-sm leading-relaxed text-[#F2EFE8]">
            {lead.outreachAngle || lead.evidenceSummary || "No thesis notes available. Inspect evidence before outreach."}
          </p>
        </div>

        {/* Contact route */}
        <div>
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-[#A8A29A]">Contact route</p>
          <div className="space-y-1">
            {lead.contactUrl ? (
              <a
                href={lead.contactUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="block truncate text-sm text-[#BCA06A] underline-offset-2 hover:underline"
              >
                {lead.contactUrl}
              </a>
            ) : null}
            {lead.evidenceUrl ? (
              <a
                href={lead.evidenceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="block truncate text-sm text-[#BCA06A] underline-offset-2 hover:underline"
              >
                {lead.evidenceUrl}
              </a>
            ) : null}
            {!lead.contactUrl && !lead.evidenceUrl && (
              <p className="text-xs text-[#A8A29A]">{lead.contactMethod || "No contact route found"}</p>
            )}
          </div>
        </div>

        {/* Top evidence */}
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-[#A8A29A]">
              Top evidence ({evidenceCount})
            </p>
            <button type="button" className="text-[11px] text-[#BCA06A] hover:underline underline-offset-2">
              View all
            </button>
          </div>
          <div className="space-y-1.5">
            {lead.evidenceUrl ? (
              <div className="flex items-center gap-2 rounded-md border border-[#2A2A30] bg-[#151519] px-3 py-2">
                <FileText className="h-3.5 w-3.5 shrink-0 text-[#BCA06A]" />
                <span className="flex-1 truncate text-xs text-[#F2EFE8]">
                  {lead.evidenceSummary || lead.evidenceUrl}
                </span>
                <ExternalLink className="h-3 w-3 shrink-0 text-[#A8A29A]" />
              </div>
            ) : (
              <p className="text-xs text-[#A8A29A]">–</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function DealDeskFallbackOutput({
  result,
  output,
}: {
  result: RunResponse | null;
  output: string | null;
}) {
  if (!result) {
    return (
      <section className="rounded-md border border-dashed border-[#2A2A30] bg-[#151519] p-8 text-center text-[#A8A29A]">
        <Radar className="mx-auto mb-3 h-7 w-7 text-[#BCA06A]" />
        <p className="text-sm font-medium text-[#F2EFE8]">Run output will appear here.</p>
        <p className="mt-1 text-xs">The formal review layout activates after a successful VC workflow run.</p>
      </section>
    );
  }

  if (result.status === "error") {
    return (
      <section className="rounded-md border border-[#6E2B2B]/50 bg-[#6E2B2B]/20 p-4 text-[#E2B5AE]">
        <div className="flex gap-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="text-sm font-semibold">Workflow failed</p>
            <p className="mt-1 text-sm">{result.error ?? "Unexpected workflow error"}</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="overflow-hidden rounded-md border border-[#2A2A30] bg-[#151519] text-[#F2EFE8]">
      <div className="border-b border-[#2A2A30] px-4 py-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-[#BCA06A]" />
          <h2 className="text-sm font-semibold">Workflow Output</h2>
        </div>
        <p className="mt-1 text-xs text-[#A8A29A]">
          Structured review data was unavailable, so the original markdown output is shown.
        </p>
      </div>
      <div className="p-5">
        {output ? (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{output}</ReactMarkdown>
          </div>
        ) : (
          <pre className="whitespace-pre-wrap text-xs text-[#A8A29A]">
            {JSON.stringify(result.result, null, 2)}
          </pre>
        )}
      </div>
    </section>
  );
}

const LEAD_CSV_HANDOFF_KEY = "aios_lead_csv_handoff";

export function DealDeskWorkflowPage({
  meta,
  inputs,
  setInputs,
  running,
  testMode,
  setTestMode,
  statusMsg,
  elapsed,
  result,
  output,
  filePath,
  obsidianUrl,
  sources,
  onRun,
}: DealDeskWorkflowPageProps) {
  const kind = workflowResultKind(meta);
  const router = useRouter();
  const workflowSteps = useMemo(() => makeWorkflowSteps(meta.name), [meta.name]);
  const csvText = resultString(result?.result, "csv");
  const csvPath = resultString(result?.result, "csv_file_path");
  const reviewQueuePath = resultString(result?.result, "review_queue_csv_path");
  const leadParse = useMemo(() => (kind === "leads" ? parseVcLeadCsv(csvText) : null), [csvText, kind]);
  const leadRows = leadParse?.rows ?? [];
  const drafts = useMemo(
    () => (kind === "drafts" ? normalizeOutreachDrafts(result?.result?.drafts) : []),
    [kind, result?.result?.drafts],
  );
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [approvedIds, setApprovedIds] = useState<Set<string>>(new Set());
  const rowsKey = leadRows.map((row) => row.id).join("|");

  useEffect(() => {
    setSelectedLeadId(leadRows[0]?.id ?? null);
    setApprovedIds(new Set());
  }, [rowsKey]);

  useEffect(() => {
    if (kind !== "drafts") return;
    const handoff = sessionStorage.getItem(LEAD_CSV_HANDOFF_KEY);
    if (!handoff) return;
    sessionStorage.removeItem(LEAD_CSV_HANDOFF_KEY);
    setInputs((previous) => ({ ...previous, lead_data: handoff }));
  }, [kind, setInputs]);

  const selectedLead = leadRows.find((row) => row.id === selectedLeadId) ?? leadRows[0] ?? null;

  function handleDraftOutreach() {
    if (!csvText) return;
    sessionStorage.setItem(LEAD_CSV_HANDOFF_KEY, csvText);
    router.push("/workflows/vc_outreach_drafts");
  }
  const chip = statusChip(result, running, testMode);
  const cards = metricCards({ kind, result, leadRows, selectedLead, drafts, sources, csvPath });
  const shouldFallback =
    Boolean(result && result.status === "success") &&
    ((kind === "leads" && leadRows.length === 0) || (kind === "drafts" && drafts.length === 0));

  function toggleApproved(id: string) {
    setApprovedIds((previous) => {
      const next = new Set(previous);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function approveSelected() {
    if (!selectedLeadId) return;
    setApprovedIds((previous) => new Set(previous).add(selectedLeadId));
    toast.success("Lead approved locally");
  }

  return (
    <div className="min-h-screen rounded-lg border border-[#2A2A30] bg-[#111113] text-[#F2EFE8] shadow-2xl shadow-black/30">
      <header className="border-b border-[#2A2A30] bg-[#141418] px-5 py-4 lg:px-7">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs text-[#A8A29A]">
              <span>AI-OS</span>
              <ChevronRight className="h-3 w-3" />
              <span>Workflows</span>
              <ChevronRight className="h-3 w-3" />
              <span className="text-[#F2EFE8]">{meta.name}</span>
            </div>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <h1 className="text-[28px] font-semibold leading-none tracking-tight">{meta.name}</h1>
              <span className={`rounded-sm border px-2 py-1 font-mono text-[11px] ${chip.className}`}>
                {chip.text}
              </span>
              <span className="rounded-sm border border-[#6E2B2B]/40 bg-[#6E2B2B]/20 px-2 py-1 font-mono text-[11px] text-[#E2B5AE]">
                0 emails sent
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {kind === "leads" && (
              <button
                type="button"
                onClick={approveSelected}
                disabled={!selectedLeadId}
                className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[#EEE8DC] px-3 text-xs font-semibold text-[#171717] hover:bg-[#DED4C3] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Approve selected
              </button>
            )}
            {kind === "leads" && (
              csvText ? (
                <button
                  type="button"
                  onClick={handleDraftOutreach}
                  className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[#BCA06A] px-3 text-xs font-semibold text-[#111113] hover:bg-[#D4B87A] transition-colors"
                >
                  Draft Outreach
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              ) : (
                <Link
                  href="/workflows/vc_outreach_drafts"
                  className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#BCA06A]/30 px-3 text-xs font-medium text-[#E6D2A4] hover:bg-[#BCA06A]/20"
                >
                  Create drafts
                </Link>
              )
            )}
            {obsidianUrl && !testMode && (
              <a
                href={obsidianUrl}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#2A2A30] bg-[#1B1C20] px-3 text-xs text-[#F2EFE8] hover:border-[#BCA06A]/50"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Open in Obsidian
              </a>
            )}
            {csvPath && !testMode && (
              <a
                href={`/api/files/download-abs?path=${encodeURIComponent(csvPath)}`}
                download
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#2A2A30] bg-[#1B1C20] px-3 text-xs text-[#F2EFE8] hover:border-[#BCA06A]/50"
              >
                <FileSpreadsheet className="h-3.5 w-3.5" />
                Export CSV
              </a>
            )}
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#2A2A30] bg-[#1B1C20] text-[#A8A29A] hover:border-[#BCA06A]/50"
              aria-label="More options"
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="mt-5 flex items-start overflow-x-auto pb-1">
          {workflowSteps.map((step, index) => {
            const state = stepState(index, result, running);
            const sublabel = step.sub(result);
            const isLast = index === workflowSteps.length - 1;
            return (
              <div key={step.name} className={cn("flex flex-col", isLast ? "shrink-0" : "min-w-[80px] flex-1")}>
                <div className="flex items-center">
                  <div
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 font-mono text-xs font-semibold transition-colors",
                      state === "done"    && "border-[#BCA06A] bg-[#BCA06A] text-[#111113]",
                      state === "warning" && "border-[#C8903D] bg-[#C8903D] text-[#111113]",
                      state === "current" && "border-[#EEE8DC] bg-[#EEE8DC] text-[#171717]",
                      state === "pending" && "border-[#2A2A30] bg-transparent text-[#A8A29A]",
                    )}
                  >
                    {index + 1}
                  </div>
                  {!isLast && (
                    <div className={cn("h-px flex-1", state === "done" ? "bg-[#7BAE7F]/30" : "bg-[#2A2A30]")} />
                  )}
                </div>
                <div className="mt-2 pr-4">
                  <p className={cn("text-xs font-medium", state === "pending" ? "text-[#A8A29A]" : "text-[#F2EFE8]")}>
                    {step.name}
                  </p>
                  <p className="mt-0.5 text-[10px] leading-relaxed text-[#6F6A62]">{sublabel}</p>
                </div>
              </div>
            );
          })}
        </div>
      </header>

      <main className="grid gap-5 p-5 lg:p-7 2xl:grid-cols-[minmax(0,1fr)_390px]">
        <div className="min-w-0 space-y-5">
          <RunConfigurationPanel
            meta={meta}
            inputs={inputs}
            setInputs={setInputs}
            running={running}
            testMode={testMode}
            setTestMode={setTestMode}
            onRun={onRun}
          />

          {running && (
            <div className="flex items-center gap-3 rounded-md border border-[#2A2A30] bg-[#1B1C20] px-4 py-3">
              <Loader2 className="h-4 w-4 animate-spin text-[#BCA06A]" />
              <span className="text-sm text-[#A8A29A]">{statusMsg}</span>
              <span className="ml-auto font-mono text-xs text-[#A8A29A]">{elapsed}s</span>
            </div>
          )}

          <section className="grid gap-3 md:grid-cols-4">
            {cards.map(([value, label, detail]) => (
              <div key={label} className="rounded-md border border-[#2A2A30] bg-[#1B1C20] p-4">
                <p className="font-mono text-2xl font-semibold text-[#F2EFE8]">{value}</p>
                <p className="mt-1 text-sm font-medium text-[#F2EFE8]">{label}</p>
                <p className="mt-1 text-xs leading-relaxed text-[#A8A29A]">{detail}</p>
              </div>
            ))}
          </section>

          {shouldFallback || !result || result.status === "error" ? (
            <DealDeskFallbackOutput result={result} output={output} />
          ) : kind === "leads" ? (
            <>
              <LeadReviewTable
                rows={leadRows}
                selectedId={selectedLead?.id ?? null}
                approvedIds={approvedIds}
                onSelect={setSelectedLeadId}
                onToggleApproved={toggleApproved}
                approvedCount={approvedIds.size}
                onApproveSelected={approveSelected}
                csvPath={csvPath}
                obsidianUrl={obsidianUrl}
              />
              <OutreachDraftQueue drafts={[]} compactEmpty />
            </>
          ) : (
            <OutreachDraftQueue drafts={drafts} reviewQueuePath={reviewQueuePath} />
          )}
        </div>

        <aside className="space-y-5">
          {kind === "leads" && <SelectedLeadDossier lead={selectedLead} />}
          <TrustLayerInspector
            trust={result?.trust_report}
            outputPath={filePath}
            csvPath={csvPath || reviewQueuePath}
            obsidianUrl={obsidianUrl}
            output={output}
            testMode={testMode}
          />
        </aside>
      </main>
    </div>
  );
}

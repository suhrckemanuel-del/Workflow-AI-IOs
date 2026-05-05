"use client";

import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Copy,
  Database,
  ExternalLink,
  FileText,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import type { RunTrustReport } from "@/lib/types";

type TrustLayerInspectorProps = {
  trust: RunTrustReport | null | undefined;
  outputPath?: string | null;
  csvPath?: string | null;
  obsidianUrl?: string;
  output?: string | null;
  testMode?: boolean;
};

function validationTone(status: string, passed = true) {
  if (status === "error" || status === "fail" || !passed) {
    return {
      icon: <XCircle className="h-4 w-4 text-[#D7827E]" />,
      badge: "border-[#6E2B2B]/50 bg-[#6E2B2B]/20 text-[#E2B5AE]",
    };
  }
  if (status === "warning" || status === "warn") {
    return {
      icon: <AlertTriangle className="h-4 w-4 text-[#C8903D]" />,
      badge: "border-[#C8903D]/30 bg-[#C8903D]/10 text-[#E8C982]",
    };
  }
  return {
    icon: <CheckCircle2 className="h-4 w-4 text-[#7BAE7F]" />,
    badge: "border-[#7BAE7F]/30 bg-[#7BAE7F]/10 text-[#BFE5C2]",
  };
}

function verdictLabel(status: string | undefined) {
  if (status === "fail") return "Failed validation";
  if (status === "warn") return "Review before outreach";
  if (status === "pass") return "Ready for review";
  return "Trust report pending";
}

export function TrustLayerInspector({
  trust,
  outputPath,
  csvPath,
  obsidianUrl,
  output,
  testMode = false,
}: TrustLayerInspectorProps) {
  const verdictTone = validationTone(trust?.validation.status ?? "warn");
  const sourceCount = trust?.evidence.source_count ?? trust?.evidence.sources.length ?? 0;
  const savedFileCount = trust?.evidence.saved_file_count ?? trust?.evidence.saved_files.length ?? 0;
  const validationChecks = trust?.validation.checks ?? [];
  const timeline = trust?.timeline ?? [];

  function copyOutput() {
    if (!output) return;
    navigator.clipboard.writeText(output);
    toast.success("Copied brief");
  }

  function copyPath(path: string) {
    navigator.clipboard.writeText(path);
    toast.success("Copied path");
  }

  return (
    <section className="rounded-md border border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
      <div className="border-b border-[#2A2A30] px-4 py-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-[#7BAE7F]" />
          <h2 className="text-sm font-semibold">Trust Layer</h2>
        </div>
        <div className={`mt-2 flex items-center gap-2 rounded-md border px-3 py-2 ${verdictTone.badge}`}>
          {verdictTone.icon}
          <span className="text-sm font-medium">{verdictLabel(trust?.validation.status)}</span>
          {trust && (
            <span className="ml-auto font-mono text-[11px] opacity-70">
              {trust.validation.passed}/{trust.validation.total} checks
            </span>
          )}
        </div>
      </div>

      <div className="space-y-5 p-4">
        <div className="grid grid-cols-3 gap-2">
          {[
            [String(sourceCount), "Web sources"],
            [String(savedFileCount), "KB notes"],
            [csvPath ? "1" : "0", "CSV saved"],
          ].map(([value, label]) => (
            <div key={label} className="rounded-md border border-[#2A2A30] bg-[#151519] p-3">
              <p className="font-mono text-lg font-semibold">{value}</p>
              <p className="text-[11px] text-[#A8A29A]">{label}</p>
            </div>
          ))}
        </div>

        <div>
          <p className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.08em] text-[#A8A29A]">
            <Clock3 className="h-3.5 w-3.5" />
            Timeline
          </p>
          {timeline.length > 0 ? (
            <div className="space-y-3">
              {timeline.map((step) => (
                <div key={step.key} className="flex gap-3">
                  <span className="mt-1 h-2 w-2 rounded-full bg-[#BCA06A]" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{step.label}</p>
                    <p className="line-clamp-2 text-xs leading-relaxed text-[#A8A29A]">{step.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="rounded-md border border-[#2A2A30] bg-[#151519] p-3 text-xs text-[#A8A29A]">
              Run a workflow to inspect the execution timeline.
            </p>
          )}
        </div>

        <div>
          <p className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.08em] text-[#A8A29A]">
            <ClipboardCheck className="h-3.5 w-3.5" />
            Validation
          </p>
          {validationChecks.length > 0 ? (
            <div className="space-y-3">
              {validationChecks.map((check) => {
                const tone = validationTone(check.severity, check.passed);
                return (
                  <div key={check.key} className="flex gap-3 rounded-md border border-[#2A2A30] bg-[#151519] p-3">
                    {tone.icon}
                    <div className="min-w-0">
                      <p className="text-sm font-medium">{check.label}</p>
                      <p className="line-clamp-2 text-xs leading-relaxed text-[#A8A29A]">{check.details}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="rounded-md border border-[#2A2A30] bg-[#151519] p-3 text-xs text-[#A8A29A]">
              Validation results appear here after a completed run.
            </p>
          )}
        </div>

        {/* Next action */}
        <div className="rounded-md border border-[#2A2A30] bg-[#151519] p-3">
          <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.08em] text-[#A8A29A]">Next action</p>
          <div className="flex items-start gap-3">
            <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 text-[#BCA06A]" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-[#F2EFE8]">
                {trust?.validation.status === "warn"
                  ? "Review leads before outreach"
                  : trust?.validation.status === "pass"
                  ? "Ready to create drafts"
                  : "Fix validation errors"}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-[#A8A29A]">
                {trust?.validation.status === "warn"
                  ? "Approve quality leads to generate drafts."
                  : trust?.validation.status === "pass"
                  ? "All checks passed. Proceed with draft creation."
                  : "Resolve blocked checks before proceeding."}
              </p>
            </div>
          </div>
        </div>

        {(outputPath || csvPath || output) && (
          <div className="rounded-md border border-[#2A2A30] bg-[#151519] p-3">
            <div className="flex items-center gap-2 text-xs font-medium text-[#F2EFE8]">
              <Archive className="h-4 w-4 text-[#BCA06A]" />
              Saved Output
            </div>

            {testMode && (
              <p className="mt-2 rounded-sm border border-[#C8903D]/30 bg-[#C8903D]/10 px-2 py-1 text-xs text-[#E8C982]">
                Test mode: output shown here but not saved to the knowledge base.
              </p>
            )}

            {outputPath && !testMode && (
              <div className="mt-2 flex items-start gap-1.5">
                <span className="flex-1 break-all font-mono text-[11px] leading-relaxed text-[#A8A29A]">
                  {outputPath}
                </span>
                <button
                  onClick={() => copyPath(outputPath)}
                  className="shrink-0 rounded-sm p-0.5 text-[#A8A29A] hover:text-[#F2EFE8]"
                  aria-label="Copy path"
                >
                  <Copy className="h-3 w-3" />
                </button>
              </div>
            )}

            <div className="mt-3 flex flex-wrap gap-2">
              {obsidianUrl && !testMode && (
                <a
                  href={obsidianUrl}
                  className="inline-flex items-center gap-1.5 rounded-md border border-[#2A2A30] px-2.5 py-1.5 text-xs text-[#F2EFE8] hover:border-[#BCA06A]/40"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  Obsidian
                </a>
              )}
              {output && (
                <button
                  onClick={copyOutput}
                  className="inline-flex items-center gap-1.5 rounded-md border border-[#2A2A30] px-2.5 py-1.5 text-xs text-[#F2EFE8] hover:border-[#BCA06A]/40"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy brief
                </button>
              )}
              {outputPath && !testMode && (
                <button className="inline-flex items-center gap-1.5 rounded-md border border-[#2A2A30] px-2.5 py-1.5 text-xs text-[#F2EFE8]">
                  <FileText className="h-3.5 w-3.5" />
                  Markdown
                </button>
              )}
              {csvPath && !testMode && (
                <a
                  href={`/api/files/download-abs?path=${encodeURIComponent(csvPath)}`}
                  download
                  className="inline-flex items-center gap-1.5 rounded-md border border-[#2A2A30] px-2.5 py-1.5 text-xs text-[#F2EFE8] hover:border-[#BCA06A]/40"
                >
                  <Database className="h-3.5 w-3.5" />
                  Download CSV
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

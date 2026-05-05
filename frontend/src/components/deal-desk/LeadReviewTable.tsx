"use client";

import { ChevronLeft, ChevronRight, ExternalLink, TableProperties } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { cn } from "@/lib/utils";
import type { VcLeadRow } from "@/lib/deal-desk";

type LeadReviewTableProps = {
  rows: VcLeadRow[];
  selectedId: string | null;
  approvedIds: Set<string>;
  onSelect: (id: string) => void;
  onToggleApproved: (id: string) => void;
  approvedCount: number;
  onApproveSelected: () => void;
  csvPath: string | null;
  obsidianUrl: string;
};

function displayStatus(row: VcLeadRow, approved: boolean): string {
  if (approved) return "Approved";
  if (row.validationStatus === "blocked") return "Blocked";
  if (row.validationStatus === "usable") return "Review";
  if (row.validationStatus) return row.validationStatus.replace(/_/g, " ");
  if (row.routeQuality === "D") return "Needs evidence";
  return "Review";
}

function statusClass(status: string, selected = false) {
  const normalized = status.toLowerCase();
  if (selected) {
    if (normalized === "approved") return "border-[#4a7a4e] text-[#4a7a4e]";
    if (normalized.includes("blocked") || normalized.includes("excluded")) return "border-[#b05050] text-[#b05050]";
    if (normalized.includes("evidence") || normalized.includes("warn")) return "border-[#9a6020] text-[#9a6020]";
    return "border-[#9a8060] text-[#9a8060]";
  }
  if (normalized === "approved") return "border-[#7BAE7F]/30 bg-[#7BAE7F]/10 text-[#BFE5C2]";
  if (normalized.includes("blocked") || normalized.includes("excluded")) {
    return "border-[#6E2B2B]/50 bg-[#6E2B2B]/20 text-[#E2B5AE]";
  }
  if (normalized.includes("evidence") || normalized.includes("warn")) {
    return "border-[#C8903D]/40 bg-[#C8903D]/10 text-[#E8C982]";
  }
  return "border-[#BCA06A]/30 bg-[#BCA06A]/10 text-[#E6D2A4]";
}

function scoreBarColor(score: number | null | undefined) {
  if (!score) return "bg-[#A8A29A]";
  if (score >= 80) return "bg-[#7BAE7F]";
  if (score >= 60) return "bg-[#BCA06A]";
  return "bg-[#A8A29A]";
}

export function LeadReviewTable({
  rows,
  selectedId,
  approvedIds,
  onSelect,
  onToggleApproved,
  approvedCount,
  onApproveSelected,
  csvPath,
  obsidianUrl,
}: LeadReviewTableProps) {
  const [currentPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(rows.length / 6));

  return (
    <section className="overflow-hidden rounded-md border border-[#2A2A30] bg-[#151519] text-[#F2EFE8]">
      {/* Header with action row */}
      <div className="flex flex-col gap-3 border-b border-[#2A2A30] px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <TableProperties className="h-4 w-4 text-[#BCA06A]" />
          <div>
            <h2 className="text-sm font-semibold">Lead Review</h2>
            <p className="text-xs text-[#A8A29A]">Approve evidence-backed leads before draft creation.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onApproveSelected}
            className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[#EEE8DC] px-3 text-xs font-semibold text-[#171717] hover:bg-[#DED4C3]"
          >
            Approve selected ({approvedCount})
          </button>
          <Link
            href="/workflows/vc_outreach_drafts"
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#BCA06A]/30 px-3 text-xs font-medium text-[#E6D2A4] hover:bg-[#BCA06A]/10"
          >
            Create drafts
          </Link>
          {obsidianUrl && (
            <a
              href={obsidianUrl}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#2A2A30] px-3 text-xs text-[#A8A29A] hover:text-[#F2EFE8]"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Open in Obsidian
            </a>
          )}
          {csvPath && (
            <button
              type="button"
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#2A2A30] px-3 text-xs text-[#A8A29A] hover:text-[#F2EFE8]"
            >
              Export CSV
            </button>
          )}
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#2A2A30] text-[#A8A29A] hover:text-[#F2EFE8]"
            aria-label="More options"
          >
            ···
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[940px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[#2A2A30] bg-[#1B1C20] text-xs text-[#A8A29A]">
              <th className="w-11 px-4 py-3 font-medium">Use</th>
              <th className="px-4 py-3 font-medium">Score</th>
              <th className="px-4 py-3 font-medium">Fund</th>
              <th className="px-4 py-3 font-medium">Fit</th>
              <th className="px-4 py-3 font-medium">Geography</th>
              <th className="px-4 py-3 font-medium">Contact Route</th>
              <th className="px-4 py-3 font-medium">Evidence</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const selected = row.id === selectedId;
              const approved = approvedIds.has(row.id);
              const status = displayStatus(row, approved);
              const evidenceCount = row.evidenceUrl ? 1 : 0;
              return (
                <tr
                  key={row.id}
                  onClick={() => onSelect(row.id)}
                  className={cn(
                    "cursor-pointer border-b border-[#2A2A30] last:border-0",
                    selected ? "bg-[#EEE8DC] text-[#171717]" : "text-[#F2EFE8] hover:bg-[#1B1C20]"
                  )}
                >
                  <td className="px-4 py-4">
                    <input
                      type="checkbox"
                      checked={approved}
                      onChange={(event) => {
                        event.stopPropagation();
                        onToggleApproved(row.id);
                      }}
                      onClick={(event) => event.stopPropagation()}
                      aria-label={`Approve ${row.fundName}`}
                      className="h-4 w-4 rounded border-[#2A2A30] accent-[#BCA06A]"
                    />
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <div className="h-1 w-11 overflow-hidden rounded-full bg-[#2A2A30]">
                        <div
                          className={cn("h-full rounded-full transition-all", scoreBarColor(row.fitScore))}
                          style={{ width: row.fitScore != null ? `${Math.min(100, row.fitScore)}%` : "0%" }}
                        />
                      </div>
                      <span className="font-mono text-sm font-semibold">{row.fitScore ?? "-"}</span>
                    </div>
                  </td>
                  <td className="px-4 py-4 font-medium">{row.fundName}</td>
                  <td className={cn("px-4 py-4", selected ? "text-[#323232]" : "text-[#CFC7BC]")}>
                    <span className="line-clamp-2">{row.fundType || row.outreachAngle || "Fit pending"}</span>
                  </td>
                  <td className={cn("px-4 py-4", selected ? "text-[#323232]" : "text-[#A8A29A]")}>
                    {row.geography || "-"}
                  </td>
                  <td className={cn("px-4 py-4", selected ? "text-[#323232]" : "text-[#A8A29A]")}>
                    {row.contactMethod || row.routeQuality || "-"}
                  </td>
                  {/* Evidence count — plain number, no link */}
                  <td className="px-4 py-4">
                    <span className={cn("font-mono text-sm", selected ? "text-[#171717]" : "text-[#F2EFE8]")}>
                      {evidenceCount}
                    </span>
                  </td>
                  {/* Status — button for Review, badge for everything else */}
                  <td className="px-4 py-4">
                    {status === "Review" ? (
                      <button
                        type="button"
                        onClick={(e) => e.stopPropagation()}
                        className={cn(
                          "rounded-sm border border-[#2A2A30] px-2 py-1 text-[11px]",
                          selected ? "text-[#323232]" : "text-[#A8A29A]"
                        )}
                      >
                        Review
                      </button>
                    ) : (
                      <span className={cn("inline-flex capitalize rounded-sm border px-2 py-1 text-[11px] font-medium", statusClass(status, selected))}>
                        {status}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-[#2A2A30]">
              <td colSpan={8} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[#A8A29A]">
                    Showing 1 to {Math.min(6, rows.length)} of {rows.length} leads
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      className="rounded-sm border border-[#2A2A30] p-1 text-[#A8A29A] hover:text-[#F2EFE8]"
                      aria-label="Previous page"
                    >
                      <ChevronLeft className="h-3 w-3" />
                    </button>
                    {Array.from({ length: Math.min(4, totalPages) }, (_, i) => i + 1).map((page) => (
                      <button
                        key={page}
                        type="button"
                        className={cn(
                          "min-w-[24px] rounded-sm border px-2 py-0.5 text-xs",
                          page === currentPage
                            ? "border-[#EEE8DC] bg-[#EEE8DC] text-[#171717]"
                            : "border-[#2A2A30] text-[#A8A29A] hover:text-[#F2EFE8]"
                        )}
                      >
                        {page}
                      </button>
                    ))}
                    <button
                      type="button"
                      className="rounded-sm border border-[#2A2A30] p-1 text-[#A8A29A] hover:text-[#F2EFE8]"
                      aria-label="Next page"
                    >
                      <ChevronRight className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

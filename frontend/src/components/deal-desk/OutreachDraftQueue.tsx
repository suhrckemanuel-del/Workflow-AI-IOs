"use client";

import Link from "next/link";
import { Copy, MailCheck, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import type { OutreachDraftPreview } from "@/lib/deal-desk";

type OutreachDraftQueueProps = {
  drafts: OutreachDraftPreview[];
  reviewQueuePath?: string;
  compactEmpty?: boolean;
};

function statusLabel(status: string) {
  return status.replace(/_/g, " ");
}

function copyText(label: string, text: string) {
  navigator.clipboard.writeText(text);
  toast.success(`${label} copied`);
}

export function OutreachDraftQueue({ drafts, reviewQueuePath, compactEmpty = false }: OutreachDraftQueueProps) {
  const blocked = drafts.filter((draft) => draft.reviewStatus === "blocked").length;
  const needsReview = drafts.filter((draft) => draft.reviewStatus !== "blocked").length;

  return (
    <section className="rounded-md border border-[#2A2A30] bg-[#151519] text-[#F2EFE8]">
      <div className="flex flex-col gap-2 border-b border-[#2A2A30] px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <MailCheck className="h-4 w-4 text-[#BCA06A]" />
          <h2 className="text-sm font-semibold">Outreach Draft Queue</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {drafts.length > 0 && (
            <>
              <span className="rounded-sm border border-[#BCA06A]/30 bg-[#BCA06A]/10 px-2 py-1 font-mono text-[11px] text-[#E6D2A4]">
                {needsReview} need review
              </span>
              {blocked > 0 && (
                <span className="rounded-sm border border-[#6E2B2B]/50 bg-[#6E2B2B]/20 px-2 py-1 font-mono text-[11px] text-[#E2B5AE]">
                  {blocked} blocked
                </span>
              )}
            </>
          )}
          {reviewQueuePath && (
            <button
              type="button"
              onClick={() => copyText("Review queue path", reviewQueuePath)}
              className="rounded-md border border-[#2A2A30] px-2.5 py-1.5 text-xs text-[#F2EFE8] hover:border-[#BCA06A]/40"
            >
              Copy queue path
            </button>
          )}
        </div>
      </div>

      {drafts.length === 0 ? (
        <div className={compactEmpty ? "p-4" : "p-5"}>
          <div className="rounded-md border border-[#2A2A30] bg-[#1B1C20] p-4">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 h-4 w-4 text-[#C8903D]" />
              <div>
                <p className="text-sm font-medium">No drafts generated on this run.</p>
                <p className="mt-1 text-xs leading-relaxed text-[#A8A29A]">
                  Lead approval is local in this UI pass. Use the existing outreach workflow to paste reviewed CSV rows and generate manual-review drafts.
                </p>
                <Link
                  href="/workflows/vc_outreach_drafts"
                  className="mt-3 inline-flex rounded-md border border-[#BCA06A]/30 bg-[#BCA06A]/10 px-3 py-2 text-xs font-medium text-[#E6D2A4] hover:bg-[#BCA06A]/20"
                >
                  Open Outreach Drafts
                </Link>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid gap-3 p-4 lg:grid-cols-3">
          {drafts.map((draft) => {
            const primarySubject = draft.subjectLines[0] || "Subject pending review";
            const draftText = draft.firstTouchEmail || "Blocked until evidence/contact issues are fixed.";
            const isBlocked = draft.reviewStatus === "blocked";
            const contactEmail = `contact@${draft.fundName.toLowerCase().replace(/[^a-z0-9]/g, "")}.com`;
            return (
              <article key={draft.id} className="rounded-md border border-[#2A2A30] bg-[#1B1C20] p-3">
                <div className="mb-3 flex items-start justify-between gap-2">
                  <p className="truncate text-sm font-semibold">{draft.fundName}</p>
                  <button
                    type="button"
                    onClick={() => copyText("Draft", draftText)}
                    className="shrink-0 rounded-sm border border-[#2A2A30] p-1.5 text-[#A8A29A] hover:border-[#BCA06A]/40 hover:text-[#F2EFE8]"
                    aria-label={`Copy draft for ${draft.fundName}`}
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                </div>
                <div className="space-y-1.5">
                  <div>
                    <span className="text-[11px] text-[#A8A29A]">To </span>
                    <span className="text-[11px] text-[#F2EFE8]">{contactEmail}</span>
                  </div>
                  <div>
                    <span className="text-[11px] text-[#A8A29A]">Subject </span>
                    <span className="text-[11px] text-[#F2EFE8]">{primarySubject}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-[#A8A29A]">Status </span>
                    <span
                      className={`rounded-sm border px-1.5 py-0.5 text-[10px] font-medium capitalize ${
                        isBlocked
                          ? "border-[#6E2B2B]/50 bg-[#6E2B2B]/20 text-[#E2B5AE]"
                          : "border-[#BCA06A]/30 bg-[#BCA06A]/10 text-[#E6D2A4]"
                      }`}
                    >
                      {statusLabel(draft.reviewStatus)}
                    </span>
                  </div>
                </div>
                {draft.missingEvidence.length > 0 && (
                  <p className="mt-2 text-[11px] leading-relaxed text-[#E8C982]">
                    Missing: {draft.missingEvidence.join(", ")}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

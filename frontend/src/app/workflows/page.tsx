"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Bot, Search, Mail, ClipboardList, BarChart3, MessageSquareReply, Linkedin, Radar } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { getWorkflows } from "@/lib/api";
import type { WorkflowMeta } from "@/lib/types";

const ICONS: Record<string, typeof Bot> = {
  company_research: Search,
  email_drafting: Mail,
  meeting_prep: ClipboardList,
  portfolio_monitor: BarChart3,
  customer_support_reply: MessageSquareReply,
  linkedin_post_gen: Linkedin,
  vc_lead_scraper: Radar,
};

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowMeta[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getWorkflows()
      .then(setWorkflows)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-5xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Runnable Automations</h1>
        <p className="text-[#A8A29A] text-sm mt-1">
          Live automations you can run, test, and assign to client knowledge bases.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-36 rounded-lg" />
            ))
          : workflows.map((wf) => {
              const Icon = ICONS[wf.id] ?? Bot;
              return (
                <Link key={wf.id} href={`/workflows/${wf.id}`}>
                  <div className="rounded-md border border-[#2A2A30] bg-[#141418] p-4 cursor-pointer hover:border-[#BCA06A]/40 transition-colors group h-full">
                    <div className="flex items-center justify-between">
                      <Icon className="h-5 w-5 text-[#BCA06A]" />
                      <ArrowRight className="h-4 w-4 text-[#A8A29A] group-hover:text-[#BCA06A] transition-colors" />
                    </div>
                    <p className="text-sm font-semibold text-[#F2EFE8] mt-2">{wf.name}</p>
                    <p className="text-xs text-[#A8A29A] leading-relaxed line-clamp-2 mt-1">{wf.description}</p>
                    {wf.requires_exa && (
                      <span className="border border-[#BCA06A]/30 bg-[#BCA06A]/10 text-[#E6D2A4] rounded-sm px-2 py-0.5 text-[11px] font-medium mt-3 inline-flex">
                        Live search
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
      </div>
    </div>
  );
}

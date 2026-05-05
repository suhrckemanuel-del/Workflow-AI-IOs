"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle2,
  ClipboardList,
  FileText,
  Linkedin,
  Mail,
  MessageSquareReply,
  Radar,
  RotateCcw,
  Search,
  XCircle,
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getRuns,
  getWorkflows,
  getKBFolders,
  getSettings,
  runWorkflow,
} from "@/lib/api";
import { getActiveClient } from "@/lib/client";
import type { RunRecord, WorkflowMeta, Settings } from "@/lib/types";

// ─── helpers ──────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  if (hrs < 48) return "Yesterday";
  return `${Math.floor(hrs / 24)}d ago`;
}

function parseJson(s: string | null): Record<string, unknown> | null {
  if (!s) return null;
  try { return JSON.parse(s); } catch { return null; }
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function todayLabel(): string {
  return new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

const WORKFLOW_ICONS: Record<string, typeof Bot> = {
  company_research: Search,
  email_drafting: Mail,
  meeting_prep: ClipboardList,
  portfolio_monitor: BarChart3,
  customer_support_reply: MessageSquareReply,
  linkedin_post_gen: Linkedin,
  vc_lead_scraper: Radar,
};

// ─── panel shell ──────────────────────────────────────────────────────────────

function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-[#2A2A30] bg-[#141418] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#2A2A30]">
        <span className="text-sm font-semibold text-[#F2EFE8]">{title}</span>
        {action}
      </div>
      {children}
    </div>
  );
}

function PanelLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="text-xs text-[#A8A29A] hover:text-[#BCA06A] transition-colors"
    >
      {children}
    </Link>
  );
}

// ─── API health pill (page header) ────────────────────────────────────────────

function ApiHealthPill({ settings }: { settings: Settings | null }) {
  if (!settings) return null;

  let connected = 0;
  let total = 0;

  if (settings.credential_health?.length) {
    total = settings.credential_health.length;
    connected = settings.credential_health.filter((c) => c.status === "connected").length;
  } else {
    const entries = Object.values(settings.api_status);
    total = entries.length;
    connected = entries.filter(Boolean).length;
  }

  const allGood = connected === total;

  return (
    <span className="inline-flex items-center gap-1.5 rounded border border-[#2A2A30] px-2.5 py-1 text-xs text-[#A8A29A]">
      <span
        className={`h-1.5 w-1.5 rounded-full shrink-0 ${allGood ? "bg-[#7BAE7F]" : "bg-[#C8903D]"}`}
      />
      {connected} / {total} APIs connected
    </span>
  );
}

// ─── Col 1: Recent Runs ────────────────────────────────────────────────────────

function RecentRunsPanel({
  runs,
  workflows,
  loading,
  rerunning,
  onRerun,
}: {
  runs: RunRecord[];
  workflows: WorkflowMeta[];
  loading: boolean;
  rerunning: number | null;
  onRerun: (run: RunRecord) => void;
}) {
  return (
    <Panel
      title="Recent Runs"
      action={<PanelLink href="/history">All history →</PanelLink>}
    >
      {loading ? (
        <div className="divide-y divide-[#2A2A30]">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-3">
              <Skeleton className="h-4 w-14 rounded-sm" />
              <Skeleton className="h-4 flex-1 rounded" />
              <Skeleton className="h-3 w-8 rounded" />
              <Skeleton className="h-3 w-12 rounded" />
            </div>
          ))}
        </div>
      ) : runs.length === 0 ? (
        <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
          <p className="text-sm text-[#A8A29A]">No runs yet.</p>
          <Link
            href="/workflows"
            className="mt-2 text-xs text-[#BCA06A] hover:underline underline-offset-2"
          >
            Run your first workflow →
          </Link>
        </div>
      ) : (
        <div className="divide-y divide-[#2A2A30]">
          {runs.map((run) => {
            const meta = workflows.find((w) => w.id === run.workflow_id);
            const outputs = parseJson(run.outputs_json);
            const primaryField = meta?.primary_display_field;
            const detail =
              outputs && primaryField
                ? String(outputs[primaryField] ?? "").slice(0, 60)
                : null;
            const name = capitalise(run.workflow_id.replace(/_/g, " "));
            const isOk = run.status === "success";

            return (
              <div
                key={run.id}
                className="group flex items-center gap-3 px-4 py-3 hover:bg-[#1B1C20] transition-colors"
              >
                {/* Status badge */}
                <span
                  className={`inline-flex shrink-0 items-center rounded-sm px-2 py-0.5 text-[10px] font-semibold ${
                    isOk
                      ? "border border-[#7BAE7F]/30 bg-[#7BAE7F]/10 text-[#BFE5C2]"
                      : "border border-[#6E2B2B]/50 bg-[#6E2B2B]/20 text-[#E2B5AE]"
                  }`}
                >
                  {isOk ? "OK" : "ERR"}
                </span>

                {/* Name + detail */}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[#F2EFE8]">{name}</p>
                  {detail && (
                    <p className="truncate text-[10px] text-[#A8A29A]">{detail}</p>
                  )}
                </div>

                {/* Duration */}
                <span className="shrink-0 font-mono text-[10px] text-[#A8A29A]">
                  {run.duration_s != null ? `${run.duration_s}s` : "—"}
                </span>

                {/* Relative time */}
                <span className="shrink-0 font-mono text-[10px] text-[#A8A29A]">
                  {relativeTime(run.created_at)}
                </span>

                {/* Re-run button */}
                <button
                  type="button"
                  disabled={rerunning === run.id}
                  onClick={() => onRerun(run)}
                  className="inline-flex shrink-0 items-center gap-1 rounded border border-[#2A2A30] px-2 py-1 text-[10px] text-[#A8A29A] opacity-0 transition-all group-hover:opacity-100 hover:border-[#BCA06A]/40 hover:text-[#F2EFE8] disabled:opacity-40"
                  aria-label={`Re-run ${name}`}
                >
                  <RotateCcw className="h-2.5 w-2.5" />
                  Re-run
                </button>
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

// ─── Col 2: Launch Workflow ────────────────────────────────────────────────────

function LaunchWorkflowPanel({
  workflows,
  runs,
  loading,
}: {
  workflows: WorkflowMeta[];
  runs: RunRecord[];
  loading: boolean;
}) {
  const router = useRouter();

  return (
    <Panel
      title="Launch Workflow"
      action={<PanelLink href="/workflows">All →</PanelLink>}
    >
      {loading ? (
        <div className="divide-y divide-[#2A2A30]">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-3">
              <Skeleton className="h-3 w-3 rounded-full" />
              <Skeleton className="h-4 flex-1 rounded" />
              <Skeleton className="h-6 w-10 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="divide-y divide-[#2A2A30]">
          {workflows.map((wf) => {
            const wfRuns = runs.filter((r) => r.workflow_id === wf.id);
            const lastRun = wfRuns[0];
            const usageCount = wfRuns.length;
            const lastFailed = lastRun?.status === "error";

            return (
              <div
                key={wf.id}
                className="flex items-center gap-3 px-4 py-3 hover:bg-[#1B1C20] transition-colors"
              >
                {/* Amber bullet */}
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#BCA06A]" />

                {/* Name + usage */}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[#F2EFE8]">{wf.name}</p>
                  {lastFailed ? (
                    <p className="text-[10px] text-[#D7827E]">Last run failed</p>
                  ) : usageCount > 0 ? (
                    <p className="text-[10px] text-[#A8A29A]">
                      Used {usageCount}× this week
                    </p>
                  ) : null}
                </div>

                {/* Run button */}
                <button
                  type="button"
                  onClick={() => router.push(`/workflows/${wf.id}`)}
                  className="shrink-0 rounded bg-[#BCA06A] px-2.5 py-1 text-xs font-semibold text-[#111113] hover:bg-[#D4B67A] transition-colors"
                >
                  Run
                </button>
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

// ─── Col 2: Notifications (static placeholder) ────────────────────────────────

function NotificationsPanel() {
  return (
    <Panel
      title="Notifications"
      action={
        <a href="#" className="text-xs text-[#A8A29A] hover:text-[#BCA06A] transition-colors">
          Configure →
        </a>
      }
    >
      {/* Placeholder state */}
      <div className="px-4 py-4">
        <div className="rounded-md border border-dashed border-[#2A2A30] px-4 py-3 text-center">
          <p className="text-xs font-medium text-[#F2EFE8]">Slack alerts coming soon</p>
          <p className="mt-0.5 text-[10px] text-[#A8A29A]">
            Run errors, API failures, and completions will appear here.
          </p>
        </div>

        {/* Ghost rows — presentational only */}
        <div className="mt-3 divide-y divide-[#2A2A30] opacity-40 pointer-events-none select-none">
          {[
            { dot: "bg-[#D7827E]", title: "Portfolio Monitor failed", sub: "Exa timeout", time: "3h ago" },
            { dot: "bg-[#7BAE7F]", title: "Company Research complete", sub: "Saved to outputs/", time: "12m ago" },
            { dot: "bg-[#C8903D]", title: "Hunter.io not configured", sub: "Required for leads", time: "Today" },
          ].map((n) => (
            <div key={n.title} className="flex items-start gap-2 py-2.5">
              <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${n.dot}`} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-[#F2EFE8]">{n.title}</p>
                <p className="text-[10px] text-[#A8A29A]">{n.sub}</p>
              </div>
              <span className="shrink-0 text-[10px] text-[#A8A29A]">{n.time}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center gap-1.5 border-t border-[#2A2A30] px-4 py-2">
        <span className="h-1.5 w-1.5 rounded-full bg-[#A8A29A]" />
        <span className="text-[10px] text-[#A8A29A]">Slack webhook · not connected</span>
      </div>
    </Panel>
  );
}

// ─── Col 3: Knowledge Base ─────────────────────────────────────────────────────

function KnowledgeBasePanel({
  folders,
  loading,
}: {
  folders: Record<string, string[]>;
  loading: boolean;
}) {
  const files = Object.entries(folders)
    .flatMap(([folder, fileList]) => fileList.map((f) => ({ folder, file: f })))
    .slice(0, 5);

  return (
    <Panel
      title="Knowledge Base"
      action={<PanelLink href="/knowledge-base">Open →</PanelLink>}
    >
      {loading ? (
        <div className="divide-y divide-[#2A2A30]">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-2 px-4 py-3">
              <Skeleton className="h-3 w-3 rounded" />
              <Skeleton className="h-3 flex-1 rounded" />
            </div>
          ))}
        </div>
      ) : files.length === 0 ? (
        <div className="px-4 py-6 text-center">
          <p className="text-sm text-[#A8A29A]">No files yet</p>
        </div>
      ) : (
        <div className="divide-y divide-[#2A2A30]">
          {files.map(({ folder, file }) => {
            const name = file.replace(/\.md$/i, "");
            return (
              <Link
                key={`${folder}/${file}`}
                href="/knowledge-base"
                className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-[#1B1C20] transition-colors group"
              >
                <FileText className="h-3.5 w-3.5 shrink-0 text-[#A8A29A] group-hover:text-[#BCA06A]" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-[#F2EFE8]">{name}</p>
                  <span className="inline-flex rounded-sm border border-[#BCA06A]/20 bg-[#BCA06A]/8 px-1.5 py-0.5 text-[9px] text-[#BCA06A]">
                    {folder}
                  </span>
                </div>
                <ArrowRight className="h-3 w-3 shrink-0 text-[#2A2A30] group-hover:text-[#A8A29A] transition-colors" />
              </Link>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

// ─── Col 3: API Health ─────────────────────────────────────────────────────────

function ApiHealthPanel({
  settings,
  loading,
}: {
  settings: Settings | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Panel title="API Health">
        <div className="divide-y divide-[#2A2A30]">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-2 px-4 py-2.5">
              <Skeleton className="h-3 flex-1 rounded" />
              <Skeleton className="h-3 w-16 rounded" />
            </div>
          ))}
        </div>
      </Panel>
    );
  }

  if (!settings) {
    return (
      <Panel title="API Health">
        <p className="px-4 py-4 text-xs text-[#A8A29A]">Unavailable</p>
      </Panel>
    );
  }

  // Build row list from credential_health if present, else api_status
  type HealthRow = { label: string; status: "connected" | "partial" | "missing" };
  let rows: HealthRow[];

  if (settings.credential_health?.length) {
    rows = settings.credential_health.map((c) => ({
      label: c.label,
      status: (c.status === "connected" || c.status === "partial" || c.status === "missing"
        ? c.status
        : "missing") as HealthRow["status"],
    }));
  } else {
    rows = Object.entries(settings.api_status).map(([key, active]) => ({
      label: capitalise(key.replace(/_/g, " ")),
      status: active ? "connected" : ("missing" as HealthRow["status"]),
    }));
  }

  const connectedCount = rows.filter((r) => r.status === "connected").length;

  function statusPip(status: HealthRow["status"]) {
    if (status === "connected")
      return <span className="text-[10px] font-semibold text-[#7BAE7F]">● connected</span>;
    if (status === "partial")
      return <span className="text-[10px] font-semibold text-[#C8903D]">◑ partial</span>;
    return <span className="text-[10px] font-semibold text-[#6E4040]">○ not set</span>;
  }

  return (
    <Panel title="API Health">
      <div className="divide-y divide-[#2A2A30]">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center gap-2 px-4 py-2.5 hover:bg-[#1B1C20] transition-colors">
            <span className="flex-1 truncate text-xs text-[#F2EFE8]">{row.label}</span>
            {statusPip(row.status)}
          </div>
        ))}
      </div>
      <div className="border-t border-[#2A2A30] px-4 py-2">
        <span className="text-[10px] text-[#A8A29A]">
          {connectedCount} / {rows.length} connected
        </span>
      </div>
    </Panel>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function CommandCenter() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowMeta[]>([]);
  const [folders, setFolders] = useState<Record<string, string[]>>({});
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState<number | null>(null);

  useEffect(() => {
    const client = getActiveClient();
    Promise.allSettled([
      getRuns({ limit: 8 }),
      getWorkflows(),
      getKBFolders(client),
      getSettings(),
    ]).then(([runsRes, wfRes, kbRes, settingsRes]) => {
      if (runsRes.status === "fulfilled") setRuns(runsRes.value);
      if (wfRes.status === "fulfilled") setWorkflows(wfRes.value);
      if (kbRes.status === "fulfilled") setFolders(kbRes.value.folders);
      if (settingsRes.status === "fulfilled") setSettings(settingsRes.value);
    }).finally(() => setLoading(false));
  }, []);

  async function handleRerun(run: RunRecord) {
    setRerunning(run.id);
    try {
      const inputs = parseJson(run.inputs_json) ?? {};
      const res = await runWorkflow(run.workflow_id, inputs);
      if (res.status === "success") {
        toast.success(`Re-run done in ${res.duration_seconds}s`);
        const fresh = await getRuns({ limit: 8 });
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

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-[#F2EFE8]">Command Center</h1>
          <p className="text-xs text-[#A8A29A]">{todayLabel()}</p>
        </div>
        <ApiHealthPill settings={settings} />
      </div>

      {/* 3-column grid */}
      <div className="grid grid-cols-1 xl:grid-cols-[2.2fr_1.3fr_1fr] gap-4 items-start">
        {/* Col 1 — Recent Runs */}
        <RecentRunsPanel
          runs={runs}
          workflows={workflows}
          loading={loading}
          rerunning={rerunning}
          onRerun={handleRerun}
        />

        {/* Col 2 — Launch + Notifications */}
        <div className="flex flex-col gap-4">
          <LaunchWorkflowPanel
            workflows={workflows}
            runs={runs}
            loading={loading}
          />
          <NotificationsPanel />
        </div>

        {/* Col 3 — KB + API Health */}
        <div className="flex flex-col gap-4">
          <KnowledgeBasePanel folders={folders} loading={loading} />
          <ApiHealthPanel settings={settings} loading={loading} />
        </div>
      </div>
    </div>
  );
}

import {
  AlertTriangle,
  Archive,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  Copy,
  Database,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  History,
  Layers3,
  MailCheck,
  MapPin,
  MoreHorizontal,
  PanelLeft,
  Phone,
  Settings,
  ShieldCheck,
  Sparkles,
  TableProperties,
  Tag,
} from "lucide-react";

const navItems = [
  { label: "Command", icon: PanelLeft, active: true },
  { label: "Workflows", icon: Layers3 },
  { label: "Runs", icon: History },
  { label: "Knowledge Base", icon: FolderOpen },
  { label: "Architect", icon: Sparkles },
  { label: "Settings", icon: Settings },
];

const workflowSteps: Array<{ name: string; sub: string; state: "done" | "warning" | "current" | "pending" }> = [
  { name: "Run",      sub: "#184 complete",     state: "done" },
  { name: "Research", sub: "18 sources",         state: "done" },
  { name: "Validate", sub: "Warnings",           state: "warning" },
  { name: "Save",     sub: "Saved",              state: "done" },
  { name: "Draft",    sub: "Create drafts",      state: "current" },
  { name: "Send",     sub: "Pending",            state: "pending" },
];

const leads = [
  {
    score: 92,
    fund: "Atomico",
    fit: "European early-stage SaaS",
    geography: "Europe",
    route: "Partner page",
    evidence: 11,
    status: "Approved",
  },
  {
    score: 86,
    fund: "Seedcamp",
    fit: "Seed, operator network",
    geography: "UK / EU",
    route: "Public contact",
    evidence: 8,
    status: "Review",
    selected: true,
  },
  {
    score: 81,
    fund: "Notion Capital",
    fit: "B2B SaaS specialist",
    geography: "Europe",
    route: "Contact form",
    evidence: 7,
    status: "Review",
  },
  {
    score: 76,
    fund: "Project A",
    fit: "Operational VC",
    geography: "DACH",
    route: "Team page",
    evidence: 6,
    status: "Needs evidence",
  },
  {
    score: 73,
    fund: "Earlybird",
    fit: "European seed fund",
    geography: "EU",
    route: "Public email",
    evidence: 5,
    status: "Review",
  },
  {
    score: 68,
    fund: "LocalGlobe",
    fit: "UK seed ecosystem",
    geography: "UK",
    route: "No direct route",
    evidence: 4,
    status: "Excluded",
  },
];

const timeline = [
  ["Inputs received", "Project context and target profile captured"],
  ["KB context loaded", "2 knowledge base notes referenced"],
  ["Sources collected", "18 public web sources attached"],
  ["Leads ranked", "20 funds scored against target profile"],
  ["Obsidian note saved", "Markdown brief and CSV artifact stored"],
];

const validationChecks = [
  { label: "Source freshness", detail: "All primary pages checked today", status: "pass" },
  { label: "Fund-stage fit", detail: "18 of 20 match seed or early-stage thesis", status: "pass" },
  { label: "Contact route", detail: "4 leads need manual contact review", status: "warn" },
  { label: "No sending performed", detail: "Drafting queue created only after approval", status: "pass" },
];

const evidenceLinks = [
  "Seedcamp portfolio",
  "Seedcamp team page",
  "European VC landscape note",
  "AI-OS positioning memo",
];

const drafts = [
  {
    fund: "Atomico",
    subject: "AI-OS and operator-grade workflow automation",
    status: "Needs review",
  },
  {
    fund: "Seedcamp",
    subject: "Feedback request on an Obsidian-native AI workflow system",
    status: "Needs review",
  },
  {
    fund: "Notion Capital",
    subject: "Question on B2B AI workflow infrastructure",
    status: "Needs review",
  },
];

function StatusBadge({ status }: { status: string }) {
  const style =
    status === "Approved"
      ? "border-[#7BAE7F]/30 bg-[#7BAE7F]/10 text-[#BFE5C2]"
      : status === "Excluded"
        ? "border-[#6E2B2B]/50 bg-[#6E2B2B]/20 text-[#E2B5AE]"
        : status === "Needs evidence"
          ? "border-[#C8903D]/40 bg-[#C8903D]/10 text-[#E8C982]"
          : "border-[#BCA06A]/35 bg-[#BCA06A]/10 text-[#E6D2A4]";

  return (
    <span className={`inline-flex rounded-sm border px-2 py-1 text-[11px] font-medium ${style}`}>
      {status}
    </span>
  );
}

function ValidationIcon({ status }: { status: string }) {
  if (status === "warn") {
    return <AlertTriangle className="h-4 w-4 text-[#C8903D]" />;
  }
  return <CheckCircle2 className="h-4 w-4 text-[#7BAE7F]" />;
}

export default function DealDeskDesignPage() {
  return (
    <div className="min-h-screen rounded-lg border border-[#2A2A30] bg-[#111113] text-[#F2EFE8] shadow-2xl shadow-black/30">
      <div className="flex min-h-screen overflow-hidden rounded-lg">
        <aside className="hidden w-60 shrink-0 border-r border-[#2A2A30] bg-[#141418] xl:block">
          <div className="border-b border-[#2A2A30] px-5 py-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-lg font-semibold tracking-tight">AI-OS</p>
                <p className="mt-1 font-mono text-[11px] text-[#A8A29A]">local workflow console</p>
              </div>
              <span className="h-2 w-2 rounded-full bg-[#7BAE7F]" />
            </div>
          </div>

          <nav className="space-y-1 px-3 py-4">
            {navItems.map(({ label, icon: Icon, active }) => (
              <button
                key={label}
                className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors ${
                  active
                    ? "bg-[#EEE8DC] text-[#171717]"
                    : "text-[#A8A29A] hover:bg-[#1B1C20] hover:text-[#F2EFE8]"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{label}</span>
              </button>
            ))}
          </nav>

          <div className="mx-3 mt-4 rounded-md border border-[#2A2A30] bg-[#1B1C20] p-3">
            <p className="text-xs font-medium text-[#F2EFE8]">Default workspace</p>
            <p className="mt-1 font-mono text-[11px] text-[#A8A29A]">client scope active</p>
          </div>
        </aside>

        <section className="min-w-0 flex-1 bg-[#111113]">
          <header className="border-b border-[#2A2A30] bg-[#141418] px-5 py-4 lg:px-7">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <div className="flex items-center gap-2 text-xs text-[#A8A29A]">
                  <span>AI-OS</span>
                  <ChevronRight className="h-3 w-3" />
                  <span>Workflows</span>
                  <ChevronRight className="h-3 w-3" />
                  <span className="text-[#F2EFE8]">VC Lead Finder</span>
                </div>
                <div className="mt-3 flex flex-wrap items-end gap-3">
                  <h1 className="text-[28px] font-semibold leading-none tracking-tight">VC Lead Finder</h1>
                  <span className="rounded-sm border border-[#7BAE7F]/30 bg-[#7BAE7F]/10 px-2 py-1 font-mono text-[11px] text-[#BFE5C2]">
                    Run #184 complete
                  </span>
                  <span className="rounded-sm border border-[#6E2B2B]/40 bg-[#6E2B2B]/15 px-2 py-1 font-mono text-[11px] text-[#E2B5AE]">
                    0 emails sent
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[#EEE8DC] px-3 text-xs font-semibold text-[#171717] hover:bg-[#DED4C3]">
                  Approve selected
                </button>
                <button className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#BCA06A]/30 px-3 text-xs font-medium text-[#E6D2A4] hover:bg-[#BCA06A]/20">
                  Create drafts
                </button>
                <button className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#2A2A30] bg-[#1B1C20] px-3 text-xs text-[#F2EFE8] hover:border-[#BCA06A]/50">
                  <ExternalLink className="h-3.5 w-3.5" />
                  Open in Obsidian
                </button>
                <button className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#2A2A30] bg-[#1B1C20] px-3 text-xs text-[#F2EFE8] hover:border-[#BCA06A]/50">
                  <FileSpreadsheet className="h-3.5 w-3.5" />
                  Export CSV
                </button>
                <button className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#2A2A30] bg-[#1B1C20] text-[#A8A29A]">
                  <MoreHorizontal className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="mt-5 flex items-start overflow-x-auto pb-1">
              {workflowSteps.map((step, index) => {
                const isLast = index === workflowSteps.length - 1;
                return (
                  <div key={step.name} className={isLast ? "flex flex-col shrink-0" : "flex flex-1 min-w-[80px] flex-col"}>
                    <div className="flex items-center">
                      <div
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
                          step.state === "done"    ? "border-[#7BAE7F] bg-[#7BAE7F]" :
                          step.state === "warning" ? "border-[#C8903D] bg-[#C8903D]" :
                          step.state === "current" ? "border-[#BCA06A] bg-[#BCA06A]" :
                                                     "border-[#2A2A30] bg-[#151519]"
                        }`}
                      >
                        {step.state === "done"    && <Check className="h-3.5 w-3.5 text-[#111113]" />}
                        {step.state === "warning" && <AlertTriangle className="h-3.5 w-3.5 text-[#111113]" />}
                        {step.state === "current" && <span className="h-2 w-2 animate-pulse rounded-full bg-[#111113]" />}
                        {step.state === "pending" && <span className="h-2 w-2 rounded-full bg-[#2A2A30]" />}
                      </div>
                      {!isLast && (
                        <div className={`h-px flex-1 ${step.state === "done" ? "bg-[#7BAE7F]/30" : "bg-[#2A2A30]"}`} />
                      )}
                    </div>
                    <div className="mt-2 pr-4">
                      <p className={`text-xs font-medium ${step.state === "pending" ? "text-[#A8A29A]" : "text-[#F2EFE8]"}`}>
                        {step.name}
                      </p>
                      <p className="mt-0.5 text-[10px] leading-relaxed text-[#6F6A62]">{step.sub}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </header>

          <main className="grid gap-5 p-5 lg:p-7 2xl:grid-cols-[minmax(0,1fr)_390px]">
            <div className="min-w-0 space-y-5">
              <section className="grid gap-3 md:grid-cols-4">
                {[
                  ["20", "Leads found", "Ranked against target profile"],
                  ["86", "Selected score", "Seedcamp review dossier"],
                  ["18", "Web sources", "Evidence attached to run"],
                  ["1", "CSV saved", "Ready for review queue"],
                ].map(([value, label, detail]) => (
                  <div key={label} className="rounded-md border border-[#2A2A30] bg-[#1B1C20] p-4">
                    <p className="font-mono text-2xl font-semibold text-[#F2EFE8]">{value}</p>
                    <p className="mt-1 text-sm font-medium text-[#F2EFE8]">{label}</p>
                    <p className="mt-1 text-xs leading-relaxed text-[#A8A29A]">{detail}</p>
                  </div>
                ))}
              </section>

              <section className="overflow-hidden rounded-md border border-[#2A2A30] bg-[#151519]">
                <div className="flex flex-col gap-3 border-b border-[#2A2A30] px-4 py-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <TableProperties className="h-4 w-4 text-[#BCA06A]" />
                      <h2 className="text-sm font-semibold">Lead Review</h2>
                    </div>
                    <p className="mt-1 text-xs text-[#A8A29A]">Approve only evidence-backed leads before draft creation.</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button className="rounded-md border border-[#2A2A30] px-3 py-2 text-xs text-[#F2EFE8] hover:border-[#BCA06A]/50">
                      Export CSV
                    </button>
                    <button className="rounded-md bg-[#EEE8DC] px-3 py-2 text-xs font-semibold text-[#171717] hover:bg-[#DED4C3]">
                      Approve selected
                    </button>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[820px] border-collapse text-left text-sm">
                    <thead>
                      <tr className="border-b border-[#2A2A30] bg-[#1B1C20] text-xs text-[#A8A29A]">
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
                      {leads.map((lead) => (
                        <tr
                          key={lead.fund}
                          className={`border-b border-[#2A2A30] last:border-0 ${
                            lead.selected ? "bg-[#EEE8DC] text-[#171717]" : "text-[#F2EFE8] hover:bg-[#1B1C20]"
                          }`}
                        >
                          <td className="px-4 py-4 font-mono text-sm font-semibold">{lead.score}</td>
                          <td className="px-4 py-4 font-medium">{lead.fund}</td>
                          <td className={`px-4 py-4 ${lead.selected ? "text-[#323232]" : "text-[#CFC7BC]"}`}>{lead.fit}</td>
                          <td className={`px-4 py-4 ${lead.selected ? "text-[#323232]" : "text-[#A8A29A]"}`}>{lead.geography}</td>
                          <td className={`px-4 py-4 ${lead.selected ? "text-[#323232]" : "text-[#A8A29A]"}`}>{lead.route}</td>
                          <td className="px-4 py-4 font-mono">{lead.evidence}</td>
                          <td className="px-4 py-4">
                            {lead.selected ? (
                              <span className="inline-flex rounded-sm border border-[#171717]/15 bg-[#171717]/10 px-2 py-1 text-[11px] font-medium text-[#171717]">
                                Review
                              </span>
                            ) : (
                              <StatusBadge status={lead.status} />
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="rounded-md border border-[#2A2A30] bg-[#151519]">
                <div className="flex items-center justify-between border-b border-[#2A2A30] px-4 py-3">
                  <div className="flex items-center gap-2">
                    <MailCheck className="h-4 w-4 text-[#BCA06A]" />
                    <h2 className="text-sm font-semibold">Outreach Draft Queue</h2>
                  </div>
                  <span className="rounded-sm border border-[#BCA06A]/35 bg-[#BCA06A]/10 px-2 py-1 font-mono text-[11px] text-[#E6D2A4]">
                    5 need human review
                  </span>
                </div>
                <div className="grid gap-3 p-4 lg:grid-cols-3">
                  {drafts.map((draft) => (
                    <article key={draft.fund} className="rounded-md border border-[#2A2A30] bg-[#1B1C20] p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold">{draft.fund}</p>
                          <p className="mt-0.5 truncate text-[11px] text-[#A8A29A]">{draft.subject}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-1.5">
                          <span className="rounded-sm border border-[#BCA06A]/30 bg-[#BCA06A]/10 px-1.5 py-0.5 text-[10px] font-medium text-[#E6D2A4]">
                            {draft.status}
                          </span>
                          <button className="rounded-sm border border-[#2A2A30] p-1.5 text-[#A8A29A] hover:border-[#BCA06A]/40 hover:text-[#F2EFE8]">
                            <Copy className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-[#CFC7BC]">
                        Hi there, I wanted to reach out about AI-OS and how it could fit your portfolio thesis. The system runs locally and produces structured outputs directly to your knowledge base.
                      </p>
                    </article>
                  ))}
                </div>
              </section>
            </div>

            <aside className="space-y-5">
              <section className="rounded-md border border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
                <div className="border-b border-[#2A2A30] px-4 py-3">
                  <p className="text-xs font-medium uppercase tracking-[0.08em] text-[#A8A29A]">Selected Lead</p>
                  <div className="mt-2 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="truncate text-xl font-semibold">Seedcamp</h2>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <span className="inline-flex items-center gap-1 rounded-sm border border-[#2A2A30] bg-[#151519] px-2 py-0.5 text-[11px] text-[#A8A29A]">
                          <MapPin className="h-2.5 w-2.5" />
                          UK / Europe
                        </span>
                        <span className="inline-flex items-center gap-1 rounded-sm border border-[#2A2A30] bg-[#151519] px-2 py-0.5 text-[11px] text-[#A8A29A]">
                          <Tag className="h-2.5 w-2.5" />
                          Seed / Early-stage
                        </span>
                      </div>
                    </div>
                    <div className="shrink-0 rounded-md border border-[#BCA06A]/30 px-3 py-2 text-center">
                      <p className="font-mono text-3xl font-semibold text-[#F2EFE8]">86</p>
                      <p className="font-mono text-[10px] uppercase tracking-wide text-[#A8A29A]">fit score</p>
                    </div>
                  </div>
                </div>

                <div className="space-y-4 p-4">
                  <div className="rounded-md bg-[#EEE8DC] p-4 text-[#171717]">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-[#323232]">
                      <BookOpen className="h-3.5 w-3.5" />
                      Thesis notes
                    </div>
                    <p className="mt-2 text-sm leading-relaxed">
                      Strong fit for AI-OS positioning because Seedcamp backs early-stage software teams and publishes operator-focused resources. Contact route exists, but should be checked manually before outreach.
                    </p>
                  </div>

                  <div>
                    <p className="mb-2 text-xs font-medium uppercase tracking-[0.08em] text-[#A8A29A]">Contact</p>
                    <a
                      href="#"
                      className="flex items-center justify-between rounded-md border border-[#2A2A30] bg-[#151519] px-3 py-2 text-sm text-[#F2EFE8] hover:border-[#BCA06A]/40"
                    >
                      <div className="flex items-center gap-2">
                        <Phone className="h-3.5 w-3.5 shrink-0 text-[#BCA06A]" />
                        <span>Partner application page</span>
                      </div>
                      <ExternalLink className="h-3.5 w-3.5 shrink-0 text-[#A8A29A]" />
                    </a>
                  </div>

                  <div>
                    <p className="mb-2 text-xs font-medium uppercase tracking-[0.08em] text-[#A8A29A]">Evidence</p>
                    <div className="space-y-1.5">
                      {evidenceLinks.map((link) => (
                        <a
                          key={link}
                          href="#"
                          className="flex items-center justify-between rounded-md border border-[#2A2A30] bg-[#151519] px-3 py-2 text-sm text-[#F2EFE8] hover:border-[#BCA06A]/40"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <ExternalLink className="h-3.5 w-3.5 shrink-0 text-[#BCA06A]" />
                            <span className="truncate">{link}</span>
                          </div>
                          <ExternalLink className="h-3.5 w-3.5 shrink-0 text-[#A8A29A]" />
                        </a>
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              <section className="rounded-md border border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
                <div className="border-b border-[#2A2A30] px-4 py-3">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-[#7BAE7F]" />
                    <h2 className="text-sm font-semibold">Trust Layer</h2>
                  </div>
                  <div className="mt-2 flex items-center gap-2 rounded-md border border-[#C8903D]/30 bg-[#C8903D]/10 px-3 py-2 text-[#E8C982]">
                    <AlertTriangle className="h-4 w-4 text-[#C8903D]" />
                    <span className="text-sm font-medium">Review before outreach</span>
                    <span className="ml-auto font-mono text-[11px] opacity-70">3/4 checks</span>
                  </div>
                </div>

                <div className="space-y-5 p-4">
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      ["18", "Web sources"],
                      ["2", "KB notes"],
                      ["1", "CSV saved"],
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
                    <div className="space-y-3">
                      {timeline.map(([label, detail]) => (
                        <div key={label} className="flex gap-3">
                          <span className="mt-1 h-2 w-2 rounded-full bg-[#BCA06A]" />
                          <div>
                            <p className="text-sm font-medium">{label}</p>
                            <p className="text-xs leading-relaxed text-[#A8A29A]">{detail}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.08em] text-[#A8A29A]">
                      <ClipboardCheck className="h-3.5 w-3.5" />
                      Validation
                    </p>
                    <div className="space-y-3">
                      {validationChecks.map((check) => (
                        <div key={check.label} className="flex gap-3 rounded-md border border-[#2A2A30] bg-[#151519] p-3">
                          <ValidationIcon status={check.status} />
                          <div>
                            <p className="text-sm font-medium">{check.label}</p>
                            <p className="text-xs leading-relaxed text-[#A8A29A]">{check.detail}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-md border border-[#2A2A30] bg-[#151519] p-3">
                    <div className="flex items-center gap-2 text-xs font-medium text-[#F2EFE8]">
                      <Archive className="h-4 w-4 text-[#BCA06A]" />
                      Saved Output
                    </div>
                    <div className="mt-2 flex items-start gap-1.5">
                      <span className="flex-1 break-all font-mono text-[11px] leading-relaxed text-[#A8A29A]">
                        knowledge_base/outputs/vc_leads_2026-04-29.md
                      </span>
                      <button className="shrink-0 rounded-sm p-0.5 text-[#A8A29A] hover:text-[#F2EFE8]">
                        <Copy className="h-3 w-3" />
                      </button>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button className="inline-flex items-center gap-1.5 rounded-md border border-[#2A2A30] px-2.5 py-1.5 text-xs text-[#F2EFE8]">
                        <FileText className="h-3.5 w-3.5" />
                        Markdown
                      </button>
                      <button className="inline-flex items-center gap-1.5 rounded-md border border-[#2A2A30] px-2.5 py-1.5 text-xs text-[#F2EFE8]">
                        <Database className="h-3.5 w-3.5" />
                        CSV
                      </button>
                    </div>
                  </div>
                </div>
              </section>
            </aside>
          </main>
        </section>
      </div>
    </div>
  );
}

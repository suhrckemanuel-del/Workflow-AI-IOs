"use client";

import { useEffect, useState, useMemo } from "react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Folder,
  FileText,
  X,
  Copy,
  ChevronDown,
  ChevronRight,
  Download,
  Search,
  FileSpreadsheet,
  ExternalLink,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { getKBFolders, getKBFile, listOutputFiles, getFileDownloadUrl } from "@/lib/api";
import { getActiveClient } from "@/lib/client";
import type { KBDirectory, KBFile, OutputFile } from "@/lib/types";

// ─── Vault viewer (unchanged) ────────────────────────────────────────────────

function VaultViewer() {
  const [kb, setKb] = useState<KBDirectory | null>(null);
  const [openFolders, setOpenFolders] = useState<Set<string>>(new Set());
  const [activeFile, setActiveFile] = useState<KBFile | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getKBFolders(getActiveClient()).then((d) => {
      setKb(d);
      const first = Object.keys(d.folders)[0];
      if (first) setOpenFolders(new Set([first]));
    }).finally(() => setLoading(false));
  }, []);

  function toggleFolder(folder: string) {
    setOpenFolders((prev) => {
      const next = new Set(prev);
      next.has(folder) ? next.delete(folder) : next.add(folder);
      return next;
    });
  }

  async function openFile(folder: string, filename: string) {
    setFileLoading(true);
    try {
      const file = await getKBFile(folder, filename, getActiveClient());
      setActiveFile(file);
    } catch {
      toast.error("Could not load file");
    } finally {
      setFileLoading(false);
    }
  }

  return (
    <div className="flex gap-6">
      {/* Folder tree */}
      <div className="w-64 shrink-0">
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-8 rounded" />)}
          </div>
        ) : !kb || Object.keys(kb.folders).length === 0 ? (
          <p className="text-[#A8A29A] text-sm">No files found.</p>
        ) : (
          <div className="space-y-1">
            {Object.entries(kb.folders).map(([folder, files]) => {
              const isOpen = openFolders.has(folder);
              return (
                <div key={folder}>
                  <button
                    onClick={() => toggleFolder(folder)}
                    className="flex items-center gap-2 w-full rounded-md px-2 py-1.5 text-sm hover:bg-[#1B1C20] transition-colors text-left text-[#F2EFE8]"
                  >
                    {isOpen
                      ? <ChevronDown className="h-3.5 w-3.5 text-[#A8A29A] shrink-0" />
                      : <ChevronRight className="h-3.5 w-3.5 text-[#A8A29A] shrink-0" />}
                    <Folder className="h-3.5 w-3.5 text-[#BCA06A] shrink-0" />
                    <span className="truncate font-medium">{folder}</span>
                    <span className="text-xs text-[#A8A29A] ml-auto">{files.length}</span>
                  </button>

                  {isOpen && (
                    <div className="ml-6 mt-0.5 space-y-0.5">
                      {files.map((file) => {
                        const active = activeFile?.folder === folder && activeFile?.filename === file;
                        return (
                          <button
                            key={file}
                            onClick={() => openFile(folder, file)}
                            className={`flex items-center gap-2 w-full rounded-md px-2 py-1.5 text-xs text-left transition-colors ${
                              active
                                ? "bg-[#BCA06A]/10 text-[#E6D2A4]"
                                : "text-[#A8A29A] hover:bg-[#1B1C20] hover:text-[#F2EFE8]"
                            }`}
                          >
                            <FileText className="h-3 w-3 shrink-0" />
                            <span className="truncate">{file}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* File viewer */}
      <div className="flex-1 min-w-0">
        {fileLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        ) : activeFile ? (
          <div className="border border-[#2A2A30] rounded-md overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 bg-[#141418] border-b border-[#2A2A30]">
              <span className="font-mono text-xs text-[#A8A29A]">
                {activeFile.folder}/{activeFile.filename}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => { navigator.clipboard.writeText(activeFile.content); toast.success("Copied"); }}
                  className="flex items-center gap-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
                >
                  <Copy className="h-3 w-3" /> Copy
                </button>
                <button
                  onClick={() => setActiveFile(null)}
                  className="text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
            <ScrollArea className="h-[calc(100vh-280px)]">
              <div className="p-5 prose prose-invert prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {activeFile.content}
                </ReactMarkdown>
              </div>
            </ScrollArea>
            <div className="px-4 py-2 border-t border-[#2A2A30] bg-[#141418]">
              <p className="font-mono text-[11px] text-[#A8A29A]">
                Modified {new Date(activeFile.modified_at).toLocaleString()}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 border border-dashed border-[#2A2A30] rounded-md">
            <p className="text-[#A8A29A] text-sm">Select a file to view</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Type badge ───────────────────────────────────────────────────────────────

function TypeBadge({ type }: { type: string }) {
  const cfg =
    type === "csv"
      ? { label: "CSV", cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" }
      : type === "md"
      ? { label: "MD", cls: "bg-[#BCA06A]/10 text-[#BCA06A] border-[#BCA06A]/20" }
      : { label: type.toUpperCase(), cls: "bg-[#2A2A30] text-[#A8A29A] border-[#2A2A30]" };

  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium border ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

// ─── Outputs browser ──────────────────────────────────────────────────────────

function OutputsBrowser() {
  const [files, setFiles] = useState<OutputFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const client = getActiveClient();

  useEffect(() => {
    listOutputFiles(client)
      .then(setFiles)
      .catch(() => toast.error("Could not load output files"))
      .finally(() => setLoading(false));
  }, [client]);

  const grouped = useMemo(() => {
    const q = query.toLowerCase();
    const filtered = files.filter(
      (f) =>
        !q ||
        f.name.toLowerCase().includes(q) ||
        f.folder.toLowerCase().includes(q)
    );
    const map: Record<string, OutputFile[]> = {};
    for (const f of filtered) {
      const key = f.folder || "(root)";
      (map[key] ??= []).push(f);
    }
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
  }, [files, query]);

  function copyPath(f: OutputFile) {
    navigator.clipboard.writeText(f.path);
    toast.success("Path copied");
  }

  function openInObsidian(f: OutputFile) {
    // Build absolute path from the relative path in knowledge_base
    const abs = encodeURIComponent(f.path);
    window.open(`obsidian://open?path=${abs}`, "_blank");
  }

  function downloadCsv(f: OutputFile) {
    const url = getFileDownloadUrl(f.path, client);
    const a = document.createElement("a");
    a.href = url;
    a.download = f.name;
    a.click();
  }

  return (
    <div className="mt-10">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-[#F2EFE8]">Output Files</h2>
          <p className="text-[#A8A29A] text-xs mt-0.5">
            Files saved by workflow runs — CSV outputs and markdown reports
          </p>
        </div>
        {!loading && (
          <span className="text-xs text-[#A8A29A]">{files.length} file{files.length !== 1 ? "s" : ""}</span>
        )}
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#A8A29A]" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by filename or folder…"
          className="pl-8 h-8 text-sm bg-[#141418] border-[#2A2A30] text-[#F2EFE8] placeholder:text-[#A8A29A] focus-visible:ring-[#BCA06A]/30"
        />
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10 rounded" />)}
        </div>
      ) : grouped.length === 0 ? (
        <div className="flex items-center justify-center h-24 border border-dashed border-[#2A2A30] rounded-md">
          <p className="text-[#A8A29A] text-sm">{query ? "No files match your filter." : "No output files found."}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {grouped.map(([folder, folderFiles]) => (
            <div key={folder}>
              <div className="flex items-center gap-2 mb-1.5">
                <Folder className="h-3.5 w-3.5 text-[#BCA06A]" />
                <span className="text-xs font-medium text-[#A8A29A] uppercase tracking-wider">{folder}</span>
                <span className="text-[10px] text-[#A8A29A]/60">{folderFiles.length}</span>
              </div>

              <div className="border border-[#2A2A30] rounded-md overflow-hidden divide-y divide-[#2A2A30]">
                {folderFiles.map((f) => (
                  <div
                    key={f.path}
                    className="flex items-center gap-3 px-3 py-2.5 bg-[#141418] hover:bg-[#1B1C20] transition-colors"
                  >
                    {f.type === "csv" ? (
                      <FileSpreadsheet className="h-4 w-4 text-emerald-400 shrink-0" />
                    ) : (
                      <FileText className="h-4 w-4 text-[#BCA06A] shrink-0" />
                    )}

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-[#F2EFE8] truncate font-mono">{f.name}</span>
                        <TypeBadge type={f.type} />
                      </div>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-[11px] text-[#A8A29A]">
                          {new Date(f.modified_at).toLocaleDateString("en-GB", {
                            day: "2-digit", month: "short", year: "numeric",
                          })}{" "}
                          {new Date(f.modified_at).toLocaleTimeString("en-GB", {
                            hour: "2-digit", minute: "2-digit",
                          })}
                        </span>
                        <span className="text-[11px] text-[#A8A29A]">{f.size_kb} KB</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      {f.type === "csv" && (
                        <button
                          onClick={() => downloadCsv(f)}
                          title="Open in Excel"
                          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-[#A8A29A] hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                        >
                          <Download className="h-3 w-3" />
                          Excel
                        </button>
                      )}
                      {f.type === "md" && (
                        <button
                          onClick={() => openInObsidian(f)}
                          title="Open in Obsidian"
                          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-[#A8A29A] hover:text-[#BCA06A] hover:bg-[#BCA06A]/10 transition-colors"
                        >
                          <ExternalLink className="h-3 w-3" />
                          Obsidian
                        </button>
                      )}
                      <button
                        onClick={() => copyPath(f)}
                        title="Copy path"
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] hover:bg-[#2A2A30] transition-colors"
                      >
                        <Copy className="h-3 w-3" />
                        Path
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function KnowledgeBasePage() {
  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Knowledge Base</h1>
        <p className="text-[#A8A29A] text-sm mt-1">
          Obsidian vault at <span className="font-mono">ai-os/knowledge_base/</span>
        </p>
      </div>

      <VaultViewer />
      <OutputsBrowser />
    </div>
  );
}

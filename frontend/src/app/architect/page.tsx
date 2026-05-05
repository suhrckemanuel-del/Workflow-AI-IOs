"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Send, Loader2, RotateCcw, Copy, Check, ChevronDown, ChevronRight, BookOpen } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { architectChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

interface QAPair {
  question: string;
  answer: string;
}

interface Brief {
  goal: string;
  trigger: string;
  inputs: string;
  output: string;
  tools: string;
}

function PastRow({ pair, index }: { pair: QAPair; index: number }) {
  const [open, setOpen] = useState(false);
  return (
    <button
      onClick={() => setOpen((v) => !v)}
      className="w-full text-left border border-[#2A2A30] rounded-md overflow-hidden bg-[#141418] transition-colors hover:border-[#3A3A40]"
    >
      <div className="flex items-center gap-2 px-3 py-2">
        {open ? (
          <ChevronDown className="h-3 w-3 text-[#A8A29A] shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 text-[#A8A29A] shrink-0" />
        )}
        <span className="text-xs text-[#A8A29A] truncate flex-1">
          Q{index + 1}: {pair.question.length > 60 ? pair.question.slice(0, 60) + "…" : pair.question}
        </span>
        <span className="text-xs text-[#6F6A62] truncate max-w-[40%] shrink-0">
          {pair.answer.length > 40 ? pair.answer.slice(0, 40) + "…" : pair.answer}
        </span>
      </div>
      {open && (
        <div className="px-4 pb-3 pt-1 border-t border-[#2A2A30] space-y-1">
          <p className="text-xs font-medium text-[#F2EFE8]">{pair.question}</p>
          <p className="text-xs text-[#A8A29A]">{pair.answer}</p>
        </div>
      )}
    </button>
  );
}

function BriefSection({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-semibold tracking-widest text-[#6F6A62] uppercase">{label}</p>
      {value ? (
        <p className="text-sm text-[#F2EFE8] leading-relaxed">{value}</p>
      ) : (
        <div className="space-y-1.5">
          <Skeleton className="h-3 w-full bg-[#2A2A30] animate-pulse rounded-sm" />
          <Skeleton className="h-3 w-3/4 bg-[#2A2A30] animate-pulse rounded-sm" />
        </div>
      )}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function handleCopy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 text-xs text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
    >
      {copied ? <><Check className="h-3 w-3 text-[#7BAE7F]" /> Copied ✓</> : <><Copy className="h-3 w-3" /> Copy prompt</>}
    </button>
  );
}

function buildClaudeCodePrompt(brief: Brief): string {
  return `You are an expert Python developer building a workflow automation module.

Build a self-contained Python script for the following automation:

GOAL
${brief.goal}

TRIGGER
${brief.trigger || "On demand / manual run"}

INPUTS
${brief.inputs || "To be defined by the user"}

EXPECTED OUTPUT
${brief.output || "To be defined"}

TOOLS / INTEGRATIONS NEEDED
${brief.tools || "Standard Python libraries + Claude API"}

Requirements:
- Clean, readable Python 3.11+ code
- Use environment variables for all API keys
- Include a main() function that runs the workflow end to end
- Add brief inline comments only where logic is non-obvious
- Return a structured result dict at the end

Start coding now.`;
}

function buildCodexPrompt(brief: Brief): string {
  return `Task: Build a workflow automation script.

## Brief

**Goal:** ${brief.goal}
**Trigger:** ${brief.trigger || "Manual / on demand"}
**Inputs:** ${brief.inputs || "TBD"}
**Output:** ${brief.output || "TBD"}
**Tools:** ${brief.tools || "Python standard library + Claude API"}

## Instructions

1. Write a single Python 3.11+ script
2. All external credentials loaded from .env via python-dotenv
3. Expose a run(inputs: dict) -> dict entry point
4. The script should be production-ready and handle errors gracefully
5. No placeholder comments — implement every step

Implement the full solution.`;
}

function extractBriefUpdates(msg: string, currentBrief: Brief, idea: string): Partial<Brief> {
  const lower = msg.toLowerCase();
  const updates: Partial<Brief> = {};

  if (!currentBrief.goal && idea) updates.goal = idea;

  if (!currentBrief.trigger && (lower.includes("when") || lower.includes("trigger") || lower.includes("every") || lower.includes("on schedule") || lower.includes("scheduled"))) {
    const match = msg.match(/(?:when|trigger(?:ed)? by|every|on schedule)[^.?!]{0,120}/i);
    if (match) updates.trigger = match[0].trim();
  }

  if (!currentBrief.inputs && (lower.includes("input") || lower.includes("data") || lower.includes("source") || lower.includes(" from "))) {
    const match = msg.match(/(?:input[s]?|data|source)[^.?!]{0,120}/i);
    if (match) updates.inputs = match[0].trim();
  }

  if (!currentBrief.output && (lower.includes("output") || lower.includes("saves") || lower.includes("produces") || lower.includes("generates") || lower.includes("result"))) {
    const match = msg.match(/(?:output[s]?|save[s]?|produce[s]?|generate[s]?|result[s]?)[^.?!]{0,120}/i);
    if (match) updates.output = match[0].trim();
  }

  if (!currentBrief.tools) {
    const toolKeywords = ["exa", "hunter", "gmail", "claude", "csv", "airtable", "notion", "slack", "api", "scrape", "http", "email", "database", "sheets", "zapier"];
    const found = toolKeywords.filter((t) => lower.includes(t));
    if (found.length > 0) updates.tools = found.join(", ");
  }

  return updates;
}

const STORAGE_KEY = "aios_architect_session";

interface SessionSnapshot {
  phase: 1 | 2 | 3;
  idea: string;
  history: ChatMessage[];
  pastPairs: QAPair[];
  activeQuestion: string;
  brief: Brief;
  activeTab: "claude" | "codex";
  savedBrief: boolean;
}

function loadSession(): SessionSnapshot | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SessionSnapshot) : null;
  } catch {
    return null;
  }
}

export default function ArchitectPage() {
  const saved = loadSession();
  const [phase, setPhase] = useState<1 | 2 | 3>(saved?.phase ?? 1);
  const [idea, setIdea] = useState(saved?.idea ?? "");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<ChatMessage[]>(saved?.history ?? []);
  const [pastPairs, setPastPairs] = useState<QAPair[]>(saved?.pastPairs ?? []);
  const [activeQuestion, setActiveQuestion] = useState(saved?.activeQuestion ?? "");
  const [answerInput, setAnswerInput] = useState("");
  const [brief, setBrief] = useState<Brief>(saved?.brief ?? { goal: "", trigger: "", inputs: "", output: "", tools: "" });
  const [activeTab, setActiveTab] = useState<"claude" | "codex">(saved?.activeTab ?? "claude");
  const [savedBrief, setSavedBrief] = useState(saved?.savedBrief ?? false);
  const answerRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const snapshot: SessionSnapshot = { phase, idea, history, pastPairs, activeQuestion, brief, activeTab, savedBrief };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  }, [phase, idea, history, pastPairs, activeQuestion, brief, activeTab, savedBrief]);

  function reset() {
    setPhase(1);
    setIdea("");
    setLoading(false);
    setHistory([]);
    setPastPairs([]);
    setActiveQuestion("");
    setAnswerInput("");
    setBrief({ goal: "", trigger: "", inputs: "", output: "", tools: "" });
    setActiveTab("claude");
    setSavedBrief(false);
    localStorage.removeItem(STORAGE_KEY);
  }

  async function startInterview() {
    const trimmed = idea.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setBrief((b) => ({ ...b, goal: trimmed }));
    try {
      const res = await architectChat(trimmed, []);
      setHistory([{ role: "user", content: trimmed }, { role: "assistant", content: res.reply }]);
      if (res.yaml_detected) {
        setActiveQuestion(res.reply);
        setPhase(3);
      } else {
        setActiveQuestion(res.reply);
        setPhase(2);
      }
      setBrief((b) => ({ ...b, ...extractBriefUpdates(res.reply, b, trimmed) }));
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to start interview");
    } finally {
      setLoading(false);
    }
  }

  async function sendAnswer() {
    const answer = answerInput.trim();
    if (!answer || loading) return;
    setAnswerInput("");

    const pair: QAPair = { question: activeQuestion, answer };
    const historyWithAnswer: ChatMessage[] = [...history, { role: "user", content: answer }];

    setLoading(true);
    try {
      const res = await architectChat(answer, history);
      const updatedHistory: ChatMessage[] = [...historyWithAnswer, { role: "assistant", content: res.reply }];
      setHistory(updatedHistory);
      setPastPairs((p) => [...p, pair]);
      setBrief((b) => ({ ...b, ...extractBriefUpdates(res.reply, b, idea) }));

      if (res.yaml_detected) {
        setActiveQuestion(res.reply);
        setPhase(3);
      } else {
        setActiveQuestion(res.reply);
        setTimeout(() => answerRef.current?.focus(), 50);
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Error sending answer");
    } finally {
      setLoading(false);
    }
  }

  function saveBrief() {
    setSavedBrief(true);
    toast.success("Brief saved to knowledge_base/briefs/");
  }

  const claudePrompt = buildClaudeCodePrompt(brief);
  const codexPrompt = buildCodexPrompt(brief);
  const briefFilled = brief.goal || brief.trigger || brief.inputs || brief.output || brief.tools;

  return (
    <div className="flex gap-6 h-[calc(100vh-4rem)]">
      {/* LEFT COLUMN */}
      <div className="flex flex-col flex-1 min-w-0 border border-[#2A2A30] rounded-md overflow-hidden bg-[#141418]">
        <div className="px-4 py-3 border-b border-[#2A2A30] flex items-center justify-between shrink-0">
          <div>
            <h1 className="font-semibold text-[#F2EFE8]">Architect</h1>
            <p className="text-xs text-[#A8A29A]">Design automations via Q&A</p>
          </div>
          <button
            onClick={reset}
            className="inline-flex items-center gap-1.5 text-xs text-[#A8A29A] hover:text-[#F2EFE8] border border-[#2A2A30] rounded-md px-2.5 py-1.5 transition-colors"
          >
            <RotateCcw className="h-3 w-3" /> New interview
          </button>
        </div>

        <ScrollArea className="flex-1">
          <div className="px-4 py-4 space-y-3">
            {/* Phase 1 — idea box */}
            {phase === 1 && (
              <div className="border border-[#2A2A30] rounded-md p-4 space-y-3 bg-[#1B1C20]">
                <p className="text-sm font-medium text-[#F2EFE8]">Describe your automation idea</p>
                <Textarea
                  value={idea}
                  onChange={(e) => setIdea(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); startInterview(); } }}
                  placeholder="Describe the task you want to automate. One sentence is enough."
                  rows={3}
                  className="border-[#2A2A30] bg-[#111113] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A] resize-none"
                />
                <div className="flex justify-end">
                  <button
                    onClick={startInterview}
                    disabled={!idea.trim() || loading}
                    className="inline-flex items-center gap-2 rounded-md bg-[#BCA06A] px-4 py-2 text-sm font-semibold text-[#0D0B08] hover:bg-[#CDB07A] disabled:opacity-50 transition-colors"
                  >
                    {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                    Start interview →
                  </button>
                </div>
              </div>
            )}

            {/* Idea recap (phases 2+) */}
            {phase !== 1 && (
              <div className="flex items-start gap-2">
                <div className="shrink-0 mt-0.5 h-5 w-5 rounded-sm bg-[#BCA06A]/15 flex items-center justify-center">
                  <span className="text-[10px] font-bold text-[#BCA06A]">I</span>
                </div>
                <p className="text-sm text-[#A8A29A] italic">{idea}</p>
              </div>
            )}

            {/* Past Q+A rows */}
            {pastPairs.map((pair, i) => (
              <PastRow key={i} pair={pair} index={i} />
            ))}

            {/* Active question card (phases 2 & 3) */}
            {(phase === 2 || phase === 3) && (
              <div className="border border-[#BCA06A]/30 rounded-md p-4 space-y-3 bg-[#1B1C20]">
                {loading && !activeQuestion ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-[#A8A29A]" />
                    <span className="text-xs text-[#A8A29A]">Thinking…</span>
                  </div>
                ) : (
                  <>
                    <p className="text-sm font-semibold text-[#F2EFE8] leading-snug">{activeQuestion}</p>
                    {phase === 2 && (
                      <div className="flex gap-2">
                        <Input
                          ref={answerRef}
                          value={answerInput}
                          onChange={(e) => setAnswerInput(e.target.value)}
                          onKeyDown={(e) => { if (e.key === "Enter") sendAnswer(); }}
                          placeholder="Your answer…"
                          disabled={loading}
                          className="flex-1 border-[#2A2A30] bg-[#111113] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A] h-9 text-sm"
                        />
                        <button
                          onClick={sendAnswer}
                          disabled={loading || !answerInput.trim()}
                          className="inline-flex items-center justify-center h-9 w-9 rounded-md bg-[#EEE8DC] text-[#171717] hover:bg-[#DED4C3] disabled:opacity-50 transition-colors shrink-0"
                        >
                          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                        </button>
                      </div>
                    )}
                  </>
                )}
                {loading && activeQuestion && phase === 2 && (
                  <div className="flex items-center gap-2 pt-1">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-[#A8A29A]" />
                    <span className="text-xs text-[#A8A29A]">Generating next question…</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* RIGHT COLUMN — Brief panel */}
      <div className="w-80 shrink-0 flex flex-col border border-[#2A2A30] rounded-md overflow-hidden bg-[#141418]">
        <div className="px-4 py-3 border-b border-[#2A2A30] shrink-0">
          <h2 className="font-semibold text-[#F2EFE8]">Brief</h2>
        </div>

        <ScrollArea className="flex-1">
          <div className="px-4 py-4 space-y-5">
            {phase < 3 ? (
              <>
                {!briefFilled ? (
                  <p className="text-sm text-[#A8A29A]">Answers will appear here as you respond.</p>
                ) : (
                  <>
                    <BriefSection label="Goal" value={brief.goal} />
                    <BriefSection label="Trigger" value={brief.trigger} />
                    <BriefSection label="Inputs" value={brief.inputs} />
                    <BriefSection label="Output" value={brief.output} />
                    <BriefSection label="Tools needed" value={brief.tools} />
                  </>
                )}
              </>
            ) : (
              <>
                {/* Tabs */}
                <div className="flex border-b border-[#2A2A30]">
                  {(["claude", "codex"] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`px-3 py-2 text-xs font-medium transition-colors ${
                        activeTab === tab
                          ? "text-[#F2EFE8] border-b-2 border-[#BCA06A] -mb-px"
                          : "text-[#A8A29A] hover:text-[#F2EFE8]"
                      }`}
                    >
                      {tab === "claude" ? "Claude Code" : "Codex"}
                    </button>
                  ))}
                </div>

                <div className="space-y-2">
                  <div className="rounded-md border border-[#2A2A30] overflow-hidden">
                    <div className="flex items-center justify-between px-3 py-1.5 bg-[#111113] border-b border-[#2A2A30]">
                      <span className="text-[10px] font-mono text-[#A8A29A]">
                        {activeTab === "claude" ? "claude-code-prompt.txt" : "codex-prompt.txt"}
                      </span>
                      <CopyButton text={activeTab === "claude" ? claudePrompt : codexPrompt} />
                    </div>
                    <pre className="text-[11px] font-mono text-[#A8A29A] p-3 leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto bg-[#111113]">
                      {activeTab === "claude" ? claudePrompt : codexPrompt}
                    </pre>
                  </div>
                </div>

                <button
                  onClick={saveBrief}
                  disabled={savedBrief}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-[#2A2A30] px-3 py-2 text-sm text-[#A8A29A] hover:text-[#F2EFE8] hover:border-[#3A3A40] disabled:opacity-50 transition-colors"
                >
                  {savedBrief ? (
                    <><Check className="h-3.5 w-3.5 text-[#7BAE7F]" /> Saved</>
                  ) : (
                    <><BookOpen className="h-3.5 w-3.5" /> Save brief to KB</>
                  )}
                </button>
              </>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

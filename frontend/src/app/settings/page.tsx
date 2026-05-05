"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle, KeyRound, Loader2, Save, XCircle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { getSettings, updateSetting, getHealth } from "@/lib/api";
import type { Settings, HealthCheck, CredentialHealth } from "@/lib/types";

const API_KEY_LABELS: Record<string, string> = {
  anthropic: "Anthropic (Claude)",
  exa: "Exa (live search)",
  tavily: "Tavily (web search)",
  groq: "Groq (fast inference)",
  hunter: "Hunter (email lookup)",
  gmail: "Gmail (send emails)",
  twitter: "Twitter / X",
};

function credentialIcon(credential: CredentialHealth) {
  if (credential.status === "connected") {
    return <CheckCircle className="h-4 w-4 text-[#7BAE7F] shrink-0" />;
  }
  if (credential.status === "partial") {
    return <AlertTriangle className="h-4 w-4 text-[#C8903D] shrink-0" />;
  }
  return <XCircle className="h-4 w-4 text-[#A8A29A] shrink-0" />;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [senderName, setSenderName] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getSettings(), getHealth()]).then(([s, h]) => {
      setSettings(s);
      setHealth(h);
      setSenderName(s.sender_name ?? "");
    }).finally(() => setLoading(false));
  }, []);

  async function saveSenderName() {
    setSaving(true);
    try {
      await updateSetting("sender_name", senderName);
      toast.success("Saved");
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-10">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-[#A8A29A] text-sm mt-1">Profile and system configuration</p>
      </div>

      {/* Profile */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-[#F2EFE8]">Profile</h2>
        <Separator />
        <div className="space-y-2">
          <label className="text-sm font-medium text-[#F2EFE8]">Your name</label>
          <p className="text-xs text-[#A8A29A]">Used in email drafts and workflow outputs</p>
          {loading ? (
            <Skeleton className="h-10 w-full" />
          ) : (
            <div className="flex gap-2">
              <Input
                value={senderName}
                onChange={(e) => setSenderName(e.target.value)}
                placeholder="e.g. Alex"
                className="max-w-xs border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] focus-visible:ring-[#BCA06A]"
              />
              <button
                onClick={saveSenderName}
                disabled={saving}
                className="inline-flex items-center rounded-md bg-[#EEE8DC] px-3 py-2 text-sm font-semibold text-[#171717] hover:bg-[#DED4C3] disabled:opacity-50"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
                Save
              </button>
            </div>
          )}
        </div>
      </section>

      {/* API Keys / Credential Health */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-[#BCA06A]" />
          <h2 className="text-sm font-semibold text-[#F2EFE8]">Credential Health</h2>
        </div>
        <Separator />
        <p className="text-xs text-[#A8A29A]">
          Managed in <span className="font-mono">ai-os/.env</span> — restart the server after changes.
        </p>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-8 rounded" />)}
          </div>
        ) : settings?.credential_health?.length ? (
          <div className="space-y-2">
            {settings.credential_health.map((credential) => (
              <div key={credential.id} className="rounded-md border border-[#2A2A30] bg-[#141418] px-4 py-3">
                <div className="flex items-start gap-3">
                  {credentialIcon(credential)}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-[#F2EFE8]">{credential.label}</span>
                      {credential.configured ? (
                        <span className="border border-[#7BAE7F]/30 bg-[#7BAE7F]/10 text-[#BFE5C2] rounded-sm px-2 py-0.5 text-[11px] font-medium capitalize">
                          {credential.status}
                        </span>
                      ) : (
                        <span className="border border-[#2A2A30] text-[#A8A29A] rounded-sm px-2 py-0.5 text-[11px] capitalize">
                          {credential.status}
                        </span>
                      )}
                      <span className="border border-[#2A2A30] text-[#A8A29A] rounded-sm px-2 py-0.5 text-[11px] capitalize">
                        {credential.category}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[#A8A29A]">{credential.risk}</p>
                    <p className="mt-2 text-xs text-[#A8A29A]">
                      Required for: {credential.required_for.join(", ")}
                    </p>
                    {credential.missing_env.length > 0 && (
                      <p className="mt-1 text-xs font-mono text-[#A8A29A]">
                        Missing: {credential.missing_env.join(", ")}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {Object.entries(settings?.api_status ?? {}).map(([key, active]) => (
              <div key={key} className="flex items-center gap-3 rounded-md border border-[#2A2A30] bg-[#141418] px-4 py-2.5">
                {active
                  ? <CheckCircle className="h-4 w-4 text-[#7BAE7F] shrink-0" />
                  : <XCircle className="h-4 w-4 text-[#A8A29A] shrink-0" />}
                <span className="text-sm text-[#F2EFE8]">{API_KEY_LABELS[key] ?? key}</span>
                <span className={`text-xs ml-auto font-mono ${active ? "text-[#7BAE7F]" : "text-[#A8A29A]"}`}>
                  {active ? "connected" : "missing"}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* System */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-[#F2EFE8]">System</h2>
        <Separator />
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-8 rounded" />)}
          </div>
        ) : health ? (
          <div className="space-y-2">
            {Object.entries(health.checks).map(([key, val]) => (
              <div key={key} className="flex items-center gap-3 rounded-md border border-[#2A2A30] bg-[#141418] px-4 py-2.5">
                {val === true || (typeof val === "number" && val > 0)
                  ? <CheckCircle className="h-4 w-4 text-[#7BAE7F] shrink-0" />
                  : <XCircle className="h-4 w-4 text-[#D7827E] shrink-0" />}
                <span className="text-sm font-mono text-[#F2EFE8]">{key.replace(/_/g, " ")}</span>
                <span className="text-xs ml-auto font-mono text-[#A8A29A]">{String(val)}</span>
              </div>
            ))}

            {health.warnings.length > 0 && (
              <div className="mt-4 rounded-md border border-[#C8903D]/30 bg-[#C8903D]/10 px-4 py-3 space-y-1">
                {health.warnings.map((w, i) => (
                  <p key={i} className="text-xs text-[#E8C982]">{w}</p>
                ))}
              </div>
            )}
          </div>
        ) : null}
      </section>
    </div>
  );
}

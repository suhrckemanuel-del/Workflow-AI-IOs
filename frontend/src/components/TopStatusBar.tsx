"use client";

import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { getClients } from "@/lib/api";
import { getActiveClient, setActiveClient } from "@/lib/client";
import type { ClientInfo } from "@/lib/types";

export function TopStatusBar() {
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [workflowCount] = useState(6);

  useEffect(() => {
    setActiveId(getActiveClient());
    getClients().then(setClients).catch(() => {});

    const handler = () => setActiveId(getActiveClient());
    window.addEventListener("aios_client_change", handler);
    return () => window.removeEventListener("aios_client_change", handler);
  }, []);

  const active = clients.find((c) => c.id === activeId) ?? clients[0];

  function select(id: string | null) {
    setActiveClient(id);
    setActiveId(id);
    setOpen(false);
  }

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 border-b border-[#2A2A30] bg-[#141418]"
      style={{ height: "var(--top-bar-h)" }}
    >
      {/* Left — local indicator */}
      <div className="flex items-center gap-1.5 font-mono text-[11px] text-[#A8A29A]">
        <span className="h-1.5 w-1.5 rounded-full bg-[#7BAE7F] shrink-0" />
        <span>Local</span>
      </div>

      {/* Center — system state */}
      <div className="flex items-center gap-1.5 font-mono text-[11px] text-[#A8A29A]">
        <span>● Obsidian vault connected</span>
        <span className="text-[#2A2A30]">·</span>
        <span>● {workflowCount} workflows</span>
        <span className="text-[#2A2A30]">·</span>
        <span>○ 0 emails sent</span>
      </div>

      {/* Right — client switcher */}
      <div className="relative">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1 font-mono text-[11px] text-[#A8A29A] hover:text-[#F2EFE8] transition-colors"
        >
          <span>{active?.display_name ?? "Default workspace"}</span>
          <ChevronDown className="h-2.5 w-2.5" />
        </button>

        {open && (
          <div className="absolute top-full right-0 mt-1 min-w-[180px] rounded-md border border-[#2A2A30] bg-[#141418] shadow-lg z-20 overflow-hidden">
            {clients.map((c) => (
              <button
                key={String(c.id)}
                onClick={() => select(c.id)}
                className={`flex flex-col w-full px-3 py-2 text-left hover:bg-[#1B1C20] transition-colors text-xs ${
                  c.id === activeId ? "text-[#BCA06A]" : "text-[#F2EFE8]"
                }`}
              >
                <span className="font-medium truncate">{c.display_name}</span>
                {c.owner_name && (
                  <span className="text-[#A8A29A]">{c.owner_name}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  );
}

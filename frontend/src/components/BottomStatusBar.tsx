"use client";

import { useEffect, useState } from "react";
import { Lock } from "lucide-react";
import { getActiveClient } from "@/lib/client";
import { getClients } from "@/lib/api";

export function BottomStatusBar() {
  const [clientName, setClientName] = useState("Default workspace");
  const [lastSync, setLastSync] = useState("");

  useEffect(() => {
    setLastSync(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));

    const update = async () => {
      const activeId = getActiveClient();
      const clients = await getClients().catch(() => []);
      const active = clients.find((c) => c.id === activeId) ?? clients[0];
      if (active) setClientName(active.display_name);
    };
    update();

    const handler = () => update();
    window.addEventListener("aios_client_change", handler);
    return () => window.removeEventListener("aios_client_change", handler);
  }, []);

  return (
    <footer
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between px-4 border-t border-[#2A2A30] bg-[#141418]"
      style={{ height: "var(--bot-bar-h)" }}
    >
      <div className="flex items-center gap-1.5 font-mono text-[11px] text-[#A8A29A]">
        <span className="h-1.5 w-1.5 rounded-full bg-[#7BAE7F] shrink-0" />
        <span>All systems operational</span>
      </div>

      <div className="flex items-center gap-1.5 font-mono text-[11px] text-[#A8A29A]">
        <span>Vault: {clientName}</span>
        <span className="text-[#2A2A30]">·</span>
        <span>Branch: main</span>
        <span className="text-[#2A2A30]">·</span>
        <span>Last sync: {lastSync}</span>
      </div>

      <div className="flex items-center gap-1.5 font-mono text-[11px] text-[#A8A29A]">
        <Lock className="h-2.5 w-2.5" />
        <span>Data is local. Nothing is sent.</span>
      </div>
    </footer>
  );
}

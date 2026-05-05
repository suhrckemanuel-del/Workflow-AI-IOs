"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Users } from "lucide-react";
import { getClients } from "@/lib/api";
import { getActiveClient, setActiveClient } from "@/lib/client";
import type { ClientInfo } from "@/lib/types";

export function ClientSwitcher() {
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

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

  if (clients.length === 0) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 w-full rounded-md px-3 py-2 text-xs hover:bg-secondary transition-colors text-left"
      >
        <Users className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <span className="truncate text-muted-foreground">{active?.display_name ?? "Default workspace"}</span>
        <ChevronDown className="h-3 w-3 text-muted-foreground ml-auto shrink-0" />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-1 rounded-md border border-border bg-card shadow-lg z-20 overflow-hidden">
          {clients.map((c) => (
            <button
              key={String(c.id)}
              onClick={() => select(c.id)}
              className={`flex flex-col w-full px-3 py-2 text-left hover:bg-secondary transition-colors text-xs ${
                c.id === activeId ? "bg-accent/10 text-accent" : "text-foreground"
              }`}
            >
              <span className="font-medium truncate">{c.display_name}</span>
              {c.owner_name && <span className="text-muted-foreground">{c.owner_name}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

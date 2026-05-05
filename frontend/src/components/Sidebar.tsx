"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Zap,
  History,
  BookOpen,
  Bot,
  Settings,
  PanelLeft,
  Timer,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getClients } from "@/lib/api";
import { getActiveClient } from "@/lib/client";
import type { ClientInfo } from "@/lib/types";

const nav = [
  { href: "/",               label: "Command Center", icon: LayoutDashboard },
  { href: "/workflows",      label: "Workflows",      icon: Zap },
  { href: "/history",        label: "Runs",           icon: History },
  { href: "/agents",         label: "Agents",         icon: Timer },
  { href: "/knowledge-base", label: "Knowledge Base", icon: BookOpen },
  { href: "/architect",      label: "Architect",      icon: Bot },
  { href: "/settings",       label: "Settings",       icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [activeClient, setActiveClientInfo] = useState<ClientInfo | null>(null);

  useEffect(() => {
    const load = async () => {
      const id = getActiveClient();
      const clients = await getClients().catch(() => []);
      const found = clients.find((c) => c.id === id) ?? clients[0] ?? null;
      setActiveClientInfo(found);
    };
    load();

    const handler = () => load();
    window.addEventListener("aios_client_change", handler);
    return () => window.removeEventListener("aios_client_change", handler);
  }, []);

  const vaultName = activeClient
    ? activeClient.display_name.toLowerCase().replace(/[\s–—]+/g, "-").replace(/[^a-z0-9-]/g, "") + "-kb"
    : "knowledge-base";

  const vaultPath = activeClient?.id
    ? `clients/${activeClient.id}/knowledge_base`
    : "ai-os/knowledge_base";

  return (
    <aside
      className="border-b border-[#2A2A30] bg-[#141418] lg:fixed lg:left-0 lg:z-10 lg:flex lg:flex-col lg:w-60 lg:border-b-0 lg:border-r"
      style={{ top: "var(--top-bar-h)", bottom: "var(--bot-bar-h)" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-4 border-b border-[#2A2A30]">
        <span className="text-base font-bold tracking-tight text-[#BCA06A]">AI-OS</span>
        <span className="text-xs text-[#A8A29A] font-mono">v2</span>
      </div>

      {/* Nav */}
      <nav className="grid grid-cols-2 gap-0.5 overflow-x-auto px-2 py-2 sm:grid-cols-3 lg:block lg:flex-1 lg:overflow-y-auto lg:py-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-[#EEE8DC] text-[#171717] font-medium"
                  : "text-[#A8A29A] hover:bg-[#1B1C20] hover:text-[#F2EFE8]"
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom client info — flat dark, no highlight */}
      <div className="hidden lg:block px-3 py-3 text-xs space-y-1 border-t border-[#2A2A30]">
        <div className="font-bold text-[#F2EFE8] truncate">
          {activeClient?.display_name ?? "Default workspace"}
        </div>
        <div className="text-[10px] text-[#A8A29A]">Active client</div>

        <div className="flex gap-1.5 pt-1">
          <span className="text-[#A8A29A] shrink-0">Vault</span>
          <span className="truncate text-[#A8A29A]">{vaultName}</span>
        </div>
        <div className="flex gap-1.5">
          <span className="text-[#A8A29A] shrink-0">Path</span>
          <span className="truncate text-[#A8A29A]">{vaultPath}</span>
        </div>

        <button className="flex items-center gap-1 pt-2 text-[10px] text-[#A8A29A] hover:text-[#F2EFE8] transition-colors">
          <PanelLeft className="h-2.5 w-2.5" />
          <span>&lt;&lt; Collapse</span>
        </button>
      </div>
    </aside>
  );
}

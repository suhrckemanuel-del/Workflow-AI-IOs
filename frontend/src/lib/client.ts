export interface ClientInfo {
  id: string | null;
  display_name: string;
  owner_name: string;
  active_workflows: string[];
}

const KEY = "aios_active_client";

export function getActiveClient(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY);
}

export function setActiveClient(id: string | null): void {
  if (typeof window === "undefined") return;
  if (id === null) {
    localStorage.removeItem(KEY);
  } else {
    localStorage.setItem(KEY, id);
  }
  // Dispatch event so other components can react
  window.dispatchEvent(new Event("aios_client_change"));
}

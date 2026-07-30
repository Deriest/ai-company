import { useEffect, useCallback } from "react";
import type { View } from "../types";

const STORE_KEY = "aic-session-state";

interface SessionState {
  view: View;
  selectedProjectId: string | null;
  conversationId: string | null;
  dockCollapsed: boolean;
  sidebarVisible: boolean;
  recentProjects: string[];
  recentConversations: string[];
  recentMissions: string[];
  timestamp: string;
}

const DEFAULT_STATE: SessionState = {
  view: "home",
  selectedProjectId: null,
  conversationId: null,
  dockCollapsed: true,
  sidebarVisible: true,
  recentProjects: [],
  recentConversations: [],
  recentMissions: [],
  timestamp: "",
};

export function useSessionRecovery() {
  // Load saved state
  const load = useCallback((): SessionState => {
    try {
      const raw = window.aic ? undefined : localStorage.getItem(STORE_KEY);
      if (raw) return { ...DEFAULT_STATE, ...JSON.parse(raw) };
    } catch {}
    return DEFAULT_STATE;
  }, []);

  // Save state
  const save = useCallback((state: Partial<SessionState>) => {
    try {
      const current = load();
      const merged = { ...current, ...state, timestamp: new Date().toISOString() };
      localStorage.setItem(STORE_KEY, JSON.stringify(merged));
    } catch {}
  }, [load]);

  // Track recent items
  const addRecent = useCallback((type: "projects" | "conversations" | "missions", id: string) => {
    const current = load();
    const key = `recent${type.charAt(0).toUpperCase() + type.slice(1)}` as keyof SessionState;
    const list = (current[key] as string[] || []).filter((x) => x !== id);
    const updated = [id, ...list].slice(0, 10);
    save({ [key]: updated });
  }, [load, save]);

  return { load, save, addRecent };
}

import { apiClient } from "./client";

// ── Types ────────────────────────────────────────────────────

export type MemoryScope = "session" | "conversation" | "workspace" | "project" | "user";
export type MemoryCategory = "fact" | "preference" | "context" | "summary";

export type MemoryEntryRecord = {
  id: string;
  scope: MemoryScope;
  key: string;
  value: any;
  importance: number;
  category: MemoryCategory | null;
  accessCount: number;
  accessedAt: string | null;
};

export type MemoryStats = {
  total_entries: number;
  avg_importance: number;
  total_accesses: number;
};

export type StoreMemoryPayload = {
  scope: MemoryScope;
  key: string;
  value: any;
  scope_id?: string;
  category?: MemoryCategory;
  importance?: number;
};

export type RetrieveMemoryParams = {
  scope: MemoryScope;
  key?: string;
  scope_id?: string;
  category?: MemoryCategory;
  min_importance?: number;
  limit?: number;
};

export type CompressMemoryPayload = {
  scope: MemoryScope;
  scope_id?: string;
  threshold?: number;
};

export type CompressMemoryResult = {
  id?: string;
  compressed: boolean;
  reason?: string;
};

// ── API ──────────────────────────────────────────────────────

export const memoryApi = {
  async store(payload: StoreMemoryPayload): Promise<MemoryEntryRecord> {
    return apiClient.post<MemoryEntryRecord>("/memory", payload);
  },

  async retrieve(params: RetrieveMemoryParams): Promise<MemoryEntryRecord[]> {
    const query = new URLSearchParams();
    query.append("scope", params.scope);
    if (params.key) query.append("key", params.key);
    if (params.scope_id) query.append("scope_id", params.scope_id);
    if (params.category) query.append("category", params.category);
    if (params.min_importance !== undefined) query.append("min_importance", String(params.min_importance));
    if (params.limit !== undefined) query.append("limit", String(params.limit));
    return apiClient.get<MemoryEntryRecord[]>(`/memory?${query.toString()}`);
  },

  async forget(entryId: string): Promise<void> {
    await apiClient.delete(`/memory/${entryId}`);
  },

  async compress(payload: CompressMemoryPayload): Promise<CompressMemoryResult> {
    return apiClient.post<CompressMemoryResult>("/memory/compress", payload);
  },

  async stats(scope?: string): Promise<MemoryStats> {
    const qs = scope ? `?scope=${encodeURIComponent(scope)}` : "";
    return apiClient.get<MemoryStats>(`/memory/stats${qs}`);
  },
};

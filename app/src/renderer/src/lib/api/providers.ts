import { apiClient } from "./client";

export type ProviderRecord = {
  id: string;
  name: string;
  endpoint: string; // mapped to base_url in backend
  apiKey: string;   // mapped to api_key in backend
  status: "connected" | "disconnected" | "error" | "disabled";
  enabled: boolean;
  latencyMs: number;
  version: string;
  healthNotes: string[];
  models: ModelInfo[];
  modelsCachedAt?: string;
  lastRefreshAt?: string;
};

export type ModelCapabilities = {
  contextWindow: number;
  vision: boolean;
  toolCalling: boolean;
  streaming: boolean;
  reasoning: boolean;
  functionCalling: boolean;
  jsonMode: boolean;
  embedding: boolean;
  maxOutputTokens: number;
};

export type ModelInfo = {
  id: string;
  name: string;
  capabilities: ModelCapabilities;
};

// Backend DTO
export interface ProviderResponse {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  enabled: boolean;
}

export interface ProviderWithModelsResponse {
  id: string;
  name: string;
  endpoint: string;
  apiKey: string;
  enabled: boolean;
  status: string;
  latencyMs: number;
  version: string;
  healthNotes: string[];
  models: ModelInfo[];
  modelsCachedAt?: string;
  lastRefreshAt?: string;
}

// Convert from backend format to frontend UI format
function mapProvider(p: ProviderWithModelsResponse): ProviderRecord {
  return {
    id: p.id,
    name: p.name,
    endpoint: p.endpoint,
    apiKey: p.apiKey,
    enabled: p.enabled,
    status: p.status as ProviderRecord["status"],
    latencyMs: p.latencyMs,
    version: p.version,
    healthNotes: p.healthNotes || ["chat"],
    // Defensive: if the backend ever returns models without capabilities
    // (e.g. a fresh provider before the model scan), fill from the local
    // heuristic so vision/tooling models never silently disappear from the
    // tier dropdowns.
    models: (p.models || []).map((m) =>
      m.capabilities ? m : { ...m, capabilities: inferModelCapabilities(m.id) }
    ),
    modelsCachedAt: p.modelsCachedAt,
    lastRefreshAt: p.lastRefreshAt
  };
}

  // Mock metadata provider logic (since backend doesn't provide it yet)
  // Vision rules mirror the backend's extended detection: gpt-4o, o4, "vl"/
  // "vision" family (qwen-vl, llava, pixtral), llama-4, gemini, claude.
  // EXACT mirroring of backend/services/provider_client.py::infer_capabilities
  export function inferModelCapabilities(modelId: string): ModelCapabilities {
    const id = modelId.toLowerCase();
    // Backend is_gpt = ["gpt", "o1", "o3"] (no "o4") — o4 handled by \bo4\b below.
    const isClaude = id.includes("claude") || id.includes("opus") || id.includes("sonnet") || id.includes("haiku");
    const isGpt = id.includes("gpt") || id.includes("o3") || id.includes("o1");
    const isDs = id.includes("deepseek");
    const isQwen = id.includes("qwen");
    const isGemini = id.includes("gemini");
    const isSmall = id.includes("mini") || id.includes("3b") || id.includes("haiku") || id.includes("flash");
    const isReason = id.includes("opus") || id.includes("o3") || id.includes("reasoner") || id.includes("r1");

    // Vision — EXACT mirror of backend _supports_vision (word-boundaries use
    // JS \b semantics same as Python re \b; \b treats [A-Za-z0-9_] as word chars).
    const isVision =
      isClaude || isGpt || isGemini ||
      id.includes("vision") ||
      id.includes("4o") ||
      id.includes("llava") ||
      id.includes("pixtral") ||
      id.includes("llama-4") ||
      id.includes("image") ||
      /\b(o4|vl|vlm)\b/.test(id);

    let contextWindow = 128_000;
    if (isClaude && id.includes("opus")) contextWindow = 200_000;
    else if (isClaude) contextWindow = 200_000;
    else if (isGpt && id.includes("4.1")) contextWindow = 1_000_000;
    else if (isGpt) contextWindow = 128_000;
    else if (isGemini) contextWindow = 1_000_000;
    else if (isDs) contextWindow = 64_000;
    else if (isSmall) contextWindow = 32_000;

    return {
      contextWindow,
      vision: isVision,
      toolCalling: !id.includes("embed"),
      streaming: true,
      reasoning: isReason || isClaude || id.includes("think"),
      functionCalling: !id.includes("embed") && !isSmall,
      jsonMode: isGpt || isDs || isQwen || isClaude,
      embedding: id.includes("embed"),
      maxOutputTokens: isSmall ? 4096 : isReason ? 32_768 : 16_384,
    };
  }

export type ConnectionStatus = "idle" | "connecting" | "connected" | "error";

export const providersApi = {
  async list(): Promise<ProviderRecord[]> {
    const data = await apiClient.get<ProviderWithModelsResponse[]>("/providers");
    return data.map(mapProvider);
  },

  async listEnabled(): Promise<ProviderRecord[]> {
    const data = await this.list();
    return data.filter(x => x.enabled);
  },

  async create(input: { name: string; endpoint: string; apiKey: string }): Promise<ProviderRecord> {
    const data = await apiClient.post<ProviderWithModelsResponse>("/providers", {
      name: input.name,
      endpoint: input.endpoint,
      apiKey: input.apiKey,
    });
    return mapProvider(data);
  },

  async update(id: string, partial: Partial<{ name: string; endpoint: string; apiKey: string; enabled: boolean }>): Promise<ProviderRecord> {
    const req: any = {};
    if (partial.name !== undefined) req.name = partial.name;
    if (partial.endpoint !== undefined) req.endpoint = partial.endpoint;
    if (partial.apiKey !== undefined) req.apiKey = partial.apiKey;
    if (partial.enabled !== undefined) req.enabled = partial.enabled;
    
    const data = await apiClient.patch<ProviderWithModelsResponse>(`/providers/${id}`, req);
    return mapProvider(data);
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/providers/${id}`);
  },

  async fetchModels(endpoint: string, apiKey: string): Promise<ModelInfo[]> {
    const p = await apiClient.post<ProviderWithModelsResponse>("/providers/test-ephemeral", {
      name: "fetch",
      endpoint,
      apiKey: apiKey
    });
    return p.models || [];
  },

  async fetchModelsAndUpdate(id: string): Promise<ProviderRecord> {
    const data = await apiClient.post<ProviderWithModelsResponse>(`/providers/${id}/fetch-models`);
    return mapProvider(data);
  },

  async testConnection(input: {
    name: string;
    endpoint: string;
    apiKey: string;
  }): Promise<
    | { ok: true; latencyMs: number; version: string; healthNotes: string[] }
    | { ok: false; error: string }
  > {
    try {
      const data = await apiClient.post<any>("/providers/test-ephemeral", {
        name: input.name,
        endpoint: input.endpoint,
        apiKey: input.apiKey
      });
      if (data.ok) {
        return {
          ok: true,
          latencyMs: data.latencyMs,
          version: data.version,
          healthNotes: data.healthNotes
        };
      } else {
        return { ok: false, error: data.error || "Connection failed" };
      }
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : "Connection failed" };
    }
  }
};

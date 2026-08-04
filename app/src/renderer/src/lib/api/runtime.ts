import { apiClient } from "./client";

export type WorkerRoleId = string;

export type WorkerMetrics = {
  role: string;
  totalExecutions: number;
  completed: number;
  errors: number;
  avgLatencyMs: number;
  lastExecutedAt?: string;
  currentlyRunning: boolean;
};

export type WorkerRuntimeConfig = {
  id?: string;
  role: WorkerRoleId;
  label: string;
  description: string;
  systemPrompt: string;
  providerId: string;
  modelId: string;
  temperature: number;
  topP: number;
  maxOutputTokens?: number;
  isEnabled: boolean;
  metrics?: WorkerMetrics;
};

export const DEFAULT_WORKER_ROLES = [
  { role: "thinker", label: "Thinker", description: "Planning · Reasoning · Long context" },
  { role: "crafter", label: "Crafter", description: "Implementation · Coding" },
  { role: "reviewer", label: "Reviewer", description: "Code review · QA · Bug detection" },
  { role: "planner", label: "Planner", description: "Task planning · Architecture" },
  { role: "manager", label: "Manager", description: "Workflow orchestration · Delegation" },
];

function getMetaForRole(role: string) {
  return DEFAULT_WORKER_ROLES.find(r => r.role === role) || { label: role, description: "" };
}

function mapRuntime(r: any): WorkerRuntimeConfig {
  return {
    id: r.id,
    role: r.role,
    label: r.label || getMetaForRole(r.role).label,
    description: r.description || getMetaForRole(r.role).description,
    systemPrompt: r.systemPrompt || "",
    providerId: r.providerId || "",
    modelId: r.modelId || "",
    temperature: r.temperature ?? 0.4,
    topP: r.topP ?? 1.0,
    maxOutputTokens: r.maxOutputTokens || undefined,
    isEnabled: r.isEnabled !== false,
    metrics: r.metrics ? {
      role: r.metrics.role,
      totalExecutions: r.metrics.totalExecutions,
      completed: r.metrics.completed,
      errors: r.metrics.errors,
      avgLatencyMs: r.metrics.avgLatencyMs,
      lastExecutedAt: r.metrics.lastExecutedAt,
      currentlyRunning: r.metrics.currentlyRunning,
    } : undefined,
  };
}

export const runtimeApi = {
  async list(): Promise<WorkerRuntimeConfig[]> {
    const data = await apiClient.get<any[]>("/runtime/workers");
    return data.map(mapRuntime);
  },

  async update(role: string, partial: Partial<WorkerRuntimeConfig>): Promise<WorkerRuntimeConfig> {
    const req: any = {};
    if (partial.providerId !== undefined) req.providerId = partial.providerId;
    if (partial.modelId !== undefined) req.modelId = partial.modelId;
    if (partial.temperature !== undefined) req.temperature = partial.temperature;
    if (partial.topP !== undefined) req.topP = partial.topP;
    if (partial.maxOutputTokens !== undefined) req.maxOutputTokens = partial.maxOutputTokens;
    if (partial.systemPrompt !== undefined) req.systemPrompt = partial.systemPrompt;
    if (partial.isEnabled !== undefined) req.isEnabled = partial.isEnabled;

    const data = await apiClient.patch<any>(`/runtime/workers/${role}`, req);
    return mapRuntime(data);
  },
  
  async saveAll(runtimes: WorkerRuntimeConfig[]): Promise<WorkerRuntimeConfig[]> {
    const results: WorkerRuntimeConfig[] = [];
    for (const r of runtimes) {
      results.push(await this.update(r.role, r));
    }
    return results;
  }
};

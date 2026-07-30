import { apiClient } from "./client";

// ── Types ────────────────────────────────────────────────────

export type WorkflowDagNode = {
  id: string;
  worker?: string;
  title?: string;
  description?: string;
  input?: Record<string, any>;
};

export type WorkflowDagEdge = {
  from: string;
  to: string;
};

export type WorkflowDag = {
  nodes: WorkflowDagNode[];
  edges: WorkflowDagEdge[];
};

export type WorkflowRecord = {
  id: string;
  name: string;
  description: string | null;
  dag: WorkflowDag;
  version: number;
};

export type CreateWorkflowPayload = {
  name: string;
  dag: WorkflowDag;
  description?: string;
};

export type InstantiateWorkflowPayload = {
  conversation_id: string;
};

// ── API ──────────────────────────────────────────────────────

export const workflowsApi = {
  async create(payload: CreateWorkflowPayload): Promise<WorkflowRecord> {
    return apiClient.post<WorkflowRecord>("/workflows", payload);
  },

  async list(): Promise<WorkflowRecord[]> {
    return apiClient.get<WorkflowRecord[]>("/workflows");
  },

  async get(id: string): Promise<WorkflowRecord> {
    return apiClient.get<WorkflowRecord>(`/workflows/${id}`);
  },

  async instantiate(id: string, payload: InstantiateWorkflowPayload): Promise<{ id: string; status: string; mode: string }> {
    return apiClient.post(`/workflows/${id}/instantiate`, payload);
  },
};

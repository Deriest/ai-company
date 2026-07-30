import { apiClient } from "./client";

// ── Types ────────────────────────────────────────────────────

export type OrchestrationSessionStatus = "pending" | "running" | "paused" | "completed" | "failed" | "cancelled";
export type OrchestrationTaskStatus = "pending" | "queued" | "running" | "completed" | "failed" | "skipped" | "cancelled";
export type ApprovalStatus = "pending" | "approved" | "rejected";

export type OrchestrationSessionRecord = {
  id: string;
  conversationId: string;
  mode: string;
  status: OrchestrationSessionStatus;
  sharedContext: Record<string, any> | null;
  createdBy: string | null;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string | null;
};

export type OrchestrationSessionDetail = OrchestrationSessionRecord & {
  tasks: OrchestrationTaskRecord[];
  approvals: OrchestrationApprovalRecord[];
};

export type OrchestrationTaskRecord = {
  id: string;
  workerRole: string;
  title: string;
  description: string | null;
  status: OrchestrationTaskStatus;
  dependsOn: string[];
  sequenceOrder: number;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
};

export type OrchestrationApprovalRecord = {
  id: string;
  taskId: string;
  status: ApprovalStatus;
  reason: string | null;
  reviewerNotes: string | null;
  requestedAt: string | null;
  resolvedAt: string | null;
};

export type CheckpointRecord = {
  id: string;
  taskId: string;
  state: Record<string, any>;
  createdAt: string;
};

export type CreateSessionPayload = {
  conversation_id: string;
  mode?: string;
};

export type CreateTaskPayload = {
  worker_role: string;
  title: string;
  description?: string;
  input_context?: Record<string, any>;
  depends_on?: string[];
};

export type ApprovalResolvePayload = {
  approved: boolean;
  notes?: string;
};

// ── API ──────────────────────────────────────────────────────

export const orchestrationApi = {
  async createSession(payload: CreateSessionPayload): Promise<{ id: string; conversationId: string; mode: string; status: string; sharedContext: Record<string, any> | null; createdAt: string | null }> {
    return apiClient.post("/orchestration/sessions", payload);
  },

  async listSessions(params?: { conversation_id?: string; status?: string }): Promise<OrchestrationSessionRecord[]> {
    const query = new URLSearchParams();
    if (params?.conversation_id) query.append("conversation_id", params.conversation_id);
    if (params?.status) query.append("status", params.status);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiClient.get<OrchestrationSessionRecord[]>(`/orchestration/sessions${qs}`);
  },

  async getSession(sessionId: string): Promise<OrchestrationSessionDetail> {
    return apiClient.get<OrchestrationSessionDetail>(`/orchestration/sessions/${sessionId}`);
  },

  async addTask(sessionId: string, payload: CreateTaskPayload): Promise<{ id: string; workerRole: string; title: string; status: string; sequenceOrder: number }> {
    return apiClient.post(`/orchestration/sessions/${sessionId}/tasks`, payload);
  },

  async executeSession(sessionId: string): Promise<{ id: string; status: string }> {
    return apiClient.post(`/orchestration/sessions/${sessionId}/execute`);
  },

  async cancelSession(sessionId: string): Promise<{ id: string; status: string }> {
    return apiClient.post(`/orchestration/sessions/${sessionId}/cancel`);
  },

  async resumeSession(sessionId: string): Promise<{ id: string; status: string }> {
    return apiClient.post(`/orchestration/sessions/${sessionId}/resume`);
  },

  async listCheckpoints(sessionId: string): Promise<CheckpointRecord[]> {
    return apiClient.get<CheckpointRecord[]>(`/orchestration/sessions/${sessionId}/checkpoints`);
  },

  async requestApproval(taskId: string, reason?: string): Promise<{ id: string; status: string }> {
    const qs = reason ? `?reason=${encodeURIComponent(reason)}` : "";
    return apiClient.post(`/orchestration/tasks/${taskId}/approval${qs}`);
  },

  async resolveApproval(approvalId: string, payload: ApprovalResolvePayload): Promise<{ id: string; status: string }> {
    return apiClient.patch(`/orchestration/approvals/${approvalId}`, payload);
  },
};

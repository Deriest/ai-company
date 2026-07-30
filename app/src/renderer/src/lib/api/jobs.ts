import { apiClient } from "./client";

// ── Types ────────────────────────────────────────────────────

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | "paused";
export type JobType = "orchestration" | "chat" | "tool" | "custom";

export type JobRecord = {
  id: string;
  title: string;
  jobType: JobType;
  priority: number;
  status: JobStatus;
  progress: number;
  retryCount: number;
  maxRetries: number;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string | null;
};

export type JobDetail = JobRecord & {
  result: Record<string, any> | null;
  logs: JobLogRecord[];
};

export type JobLogRecord = {
  level: string;
  message: string;
  createdAt: string;
};

export type CreateJobPayload = {
  title: string;
  job_type: JobType;
  payload?: Record<string, any>;
  priority?: number;
  max_retries?: number;
  conversation_id?: string;
  session_id?: string;
};

// ── API ──────────────────────────────────────────────────────

export const jobsApi = {
  async create(payload: CreateJobPayload): Promise<{ id: string; title: string; jobType: string; priority: number; status: string; progress: number }> {
    return apiClient.post("/jobs", payload);
  },

  async list(params?: { status?: string; job_type?: string; limit?: number }): Promise<JobRecord[]> {
    const query = new URLSearchParams();
    if (params?.status) query.append("status", params.status);
    if (params?.job_type) query.append("job_type", params.job_type);
    if (params?.limit !== undefined) query.append("limit", String(params.limit));
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiClient.get<JobRecord[]>(`/jobs${qs}`);
  },

  async get(id: string): Promise<JobDetail> {
    return apiClient.get<JobDetail>(`/jobs/${id}`);
  },

  async cancel(id: string): Promise<{ id: string; status: string }> {
    return apiClient.post(`/jobs/${id}/cancel`);
  },

  async pause(id: string): Promise<{ id: string; status: string }> {
    return apiClient.post(`/jobs/${id}/pause`);
  },

  async resume(id: string): Promise<{ id: string; status: string }> {
    return apiClient.post(`/jobs/${id}/resume`);
  },
};

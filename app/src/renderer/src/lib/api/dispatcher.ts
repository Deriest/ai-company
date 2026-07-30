import { apiClient } from './client';

// ============================================================
// Types
// ============================================================

export interface WorkerAssignment {
  taskId: string;
  workerId: string;
  workerRole: string;
  status: string;
  startedAt: string | null;
  completedAt: string | null;
  result: Record<string, unknown> | null;
}

export interface DispatchResult {
  id: string;
  graphId: string;
  state: string;
  assignments: WorkerAssignment[];
  executionLog: unknown[];
  status: string;
  createdAt: string;
  completedAt: string | null;
}

// ============================================================
// API Functions
// ============================================================

export const dispatcherApi = {
  /**
   * Dispatch tasks for execution
   */
  async dispatch(graphId: string): Promise<DispatchResult> {
    return apiClient.post<DispatchResult>('/api/dispatcher/dispatch', {
      graph_id: graphId
    });
  },

  /**
   * Get dispatch status
   */
  async getStatus(dispatchId: string): Promise<DispatchResult> {
    return apiClient.get<DispatchResult>(`/api/dispatcher/${dispatchId}`);
  },

  /**
   * Get execution log
   */
  async getExecutionLog(dispatchId: string): Promise<unknown[]> {
    return apiClient.get<unknown[]>(`/api/dispatcher/${dispatchId}/log`);
  },

  /**
   * List all dispatches
   */
  async listDispatches(): Promise<DispatchResult[]> {
    return apiClient.get<DispatchResult[]>('/api/dispatcher');
  }
};

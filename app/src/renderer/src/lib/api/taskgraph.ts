import { apiClient } from './client';

// ============================================================
// Types
// ============================================================

export interface TaskNode {
  id: string;
  title: string;
  description: string;
  type: string;
  status: string;
  dependencies: string[];
  estimatedEffort: number;
  assignedWorker: string | null;
}

export interface TaskEdge {
  from: string;
  to: string;
  type: string;
}

export interface TaskGraph {
  id: string;
  planId: string;
  nodes: TaskNode[];
  edges: TaskEdge[];
  executionOrder: string[];
  criticalPath: string[];
  parallelGroups: string[][];
  status: string;
  createdAt: string;
}

export interface GraphValidation {
  isValid: boolean;
  errors: string[];
  warnings: string[];
}

// ============================================================
// API Functions
// ============================================================

export const taskgraphApi = {
  /**
   * Generate a task graph from a plan
   */
  async generateGraph(planId: string): Promise<TaskGraph> {
    return apiClient.post<TaskGraph>('/api/taskgraph/generate', {
      plan_id: planId
    });
  },

  /**
   * Get task graph
   */
  async getGraph(graphId: string): Promise<TaskGraph> {
    return apiClient.get<TaskGraph>(`/api/taskgraph/${graphId}`);
  },

  /**
   * Validate a task graph
   */
  async validateGraph(graphId: string): Promise<GraphValidation> {
    return apiClient.post<GraphValidation>(`/api/taskgraph/${graphId}/validate`);
  },

  /**
   * Get execution order
   */
  async getExecutionOrder(graphId: string): Promise<string[]> {
    return apiClient.get<string[]>(`/api/taskgraph/${graphId}/execution-order`);
  },

  /**
   * Get critical path
   */
  async getCriticalPath(graphId: string): Promise<string[]> {
    return apiClient.get<string[]>(`/api/taskgraph/${graphId}/critical-path`);
  },

  /**
   * List all task graphs
   */
  async listGraphs(): Promise<TaskGraph[]> {
    return apiClient.get<TaskGraph[]>('/api/taskgraph');
  }
};

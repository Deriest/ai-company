import { apiClient } from './client';

// ============================================================
// Types
// ============================================================

export interface EngineeringReport {
  id: string;
  briefId: string;
  planId: string;
  graphId: string;
  verificationId: string;
  summary: string;
  deliverables: unknown[];
  metrics: Record<string, unknown>;
  status: string;
  createdAt: string;
}

export interface LessonLearned {
  id: string;
  reportId: string;
  category: string;
  description: string;
  impact: string;
  recommendation: string;
  createdAt: string;
}

// ============================================================
// API Functions
// ============================================================

export const deliveryApi = {
  /**
   * Deliver engineering output
   */
  async deliver(
    briefId: string,
    planId?: string,
    graphId?: string,
    verificationId?: string,
    taskResults?: Record<string, unknown>
  ): Promise<EngineeringReport> {
    return apiClient.post<EngineeringReport>('/api/delivery/deliver', {
      brief_id: briefId,
      plan_id: planId || '',
      graph_id: graphId || '',
      verification_id: verificationId || '',
      task_results: taskResults
    });
  },

  /**
   * Get engineering report
   */
  async getReport(reportId: string): Promise<EngineeringReport> {
    return apiClient.get<EngineeringReport>(`/api/delivery/${reportId}`);
  },

  /**
   * Get report for a brief
   */
  async getForBrief(briefId: string): Promise<EngineeringReport> {
    return apiClient.get<EngineeringReport>(`/api/delivery/brief/${briefId}`);
  },

  /**
   * Get delivery statistics
   */
  async getStats(): Promise<Record<string, unknown>> {
    return apiClient.get<Record<string, unknown>>('/api/delivery/stats');
  }
};

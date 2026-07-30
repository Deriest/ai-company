import { apiClient } from './client';

// ============================================================
// Types
// ============================================================

export interface RequirementCheck {
  requirementId: string;
  description: string;
  status: 'passed' | 'failed' | 'skipped';
  evidence: string;
}

export interface VerificationReport {
  id: string;
  briefId: string;
  requirementsMet: RequirementCheck[];
  acceptanceCriteriaMet: RequirementCheck[];
  qualityScore: number;
  status: 'passed' | 'failed' | 'partial';
  issues: unknown[];
  recommendations: string[];
  createdAt: string;
}

// ============================================================
// API Functions
// ============================================================

export const verificationApi = {
  /**
   * Verify output against acceptance criteria
   */
  async verify(
    briefId: string, 
    taskResults?: Record<string, unknown>
  ): Promise<VerificationReport> {
    return apiClient.post<VerificationReport>('/api/verification/verify', {
      brief_id: briefId,
      task_results: taskResults
    });
  },

  /**
   * Get verification report
   */
  async getReport(verificationId: string): Promise<VerificationReport> {
    return apiClient.get<VerificationReport>(`/api/verification/${verificationId}`);
  },

  /**
   * Get verification for a brief
   */
  async getForBrief(briefId: string): Promise<VerificationReport> {
    return apiClient.get<VerificationReport>(`/api/verification/brief/${briefId}`);
  },

  /**
   * List all verifications
   */
  async listVerifications(): Promise<VerificationReport[]> {
    return apiClient.get<VerificationReport[]>('/api/verification');
  }
};

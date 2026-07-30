import { apiClient } from './client';

// ============================================================
// Types
// ============================================================

export interface PlanningSession {
  id: string;
  briefId: string;
  state: string;
  analysis: Record<string, unknown>;
  decisions: unknown[];
  risks: unknown[];
  effortEstimate: Record<string, unknown>;
  plan: EngineeringPlan | null;
  createdAt: string;
  updatedAt: string;
}

export interface EngineeringPlan {
  id: string;
  sessionId: string;
  briefId: string;
  title: string;
  summary: string;
  tasks: unknown[];
  dependencies: unknown[];
  timeline: Record<string, unknown>;
  status: string;
  createdAt: string;
}

export interface TechnicalDecision {
  id: string;
  decision: string;
  rationale: string;
  alternatives: string[];
  impact: string;
}

export interface RiskAssessment {
  id: string;
  risk: string;
  severity: string;
  probability: string;
  mitigation: string;
}

// ============================================================
// API Functions
// ============================================================

export const planningApi = {
  /**
   * Generate an engineering plan from a brief
   */
  async generatePlan(briefId: string): Promise<PlanningSession> {
    return apiClient.post<PlanningSession>('/api/planning/generate', {
      brief_id: briefId
    });
  },

  /**
   * Get planning session status
   */
  async getSession(sessionId: string): Promise<PlanningSession> {
    return apiClient.get<PlanningSession>(`/api/planning/${sessionId}`);
  },

  /**
   * Get the engineering plan
   */
  async getPlan(sessionId: string): Promise<EngineeringPlan> {
    return apiClient.get<EngineeringPlan>(`/api/planning/${sessionId}/plan`);
  },

  /**
   * Get technical decisions
   */
  async getDecisions(sessionId: string): Promise<TechnicalDecision[]> {
    return apiClient.get<TechnicalDecision[]>(`/api/planning/${sessionId}/decisions`);
  },

  /**
   * Get risk assessments
   */
  async getRisks(sessionId: string): Promise<RiskAssessment[]> {
    return apiClient.get<RiskAssessment[]>(`/api/planning/${sessionId}/risks`);
  },

  /**
   * List all planning sessions
   */
  async listSessions(): Promise<PlanningSession[]> {
    return apiClient.get<PlanningSession[]>('/api/planning');
  }
};

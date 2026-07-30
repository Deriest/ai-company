import { apiClient } from './client';

// ============================================================
// Types
// ============================================================

export interface DiscoverySession {
  id: string;
  conversationId: string | null;
  state: string;
  intent: Record<string, unknown>;
  requirements: Record<string, unknown>;
  ambiguities: unknown[];
  readinessScore: number;
  brief: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface ClarificationQuestion {
  id: string;
  question: string;
  priority: string;
}

export interface EngineeringBrief {
  id: string;
  sessionId: string;
  title: string;
  summary: string;
  requirements: unknown[];
  constraints: unknown[];
  acceptanceCriteria: unknown[];
  createdAt: string;
}

// ============================================================
// API Functions
// ============================================================

export const discoveryApi = {
  /**
   * Start a new discovery session
   */
  async startSession(content: string, conversationId?: string): Promise<DiscoverySession> {
    return apiClient.post<DiscoverySession>('/api/discovery/start', {
      content,
      conversation_id: conversationId
    });
  },

  /**
   * Respond to clarification questions
   */
  async respondToClarification(
    sessionId: string, 
    response: string
  ): Promise<DiscoverySession> {
    return apiClient.post<DiscoverySession>(
      `/api/discovery/${sessionId}/clarify`,
      { response }
    );
  },

  /**
   * Get discovery session status
   */
  async getSession(sessionId: string): Promise<DiscoverySession> {
    return apiClient.get<DiscoverySession>(`/api/discovery/${sessionId}`);
  },

  /**
   * Get engineering brief for a session
   */
  async getBrief(sessionId: string): Promise<EngineeringBrief> {
    return apiClient.get<EngineeringBrief>(`/api/discovery/${sessionId}/brief`);
  },

  /**
   * List all discovery sessions
   */
  async listSessions(): Promise<DiscoverySession[]> {
    return apiClient.get<DiscoverySession[]>('/api/discovery');
  }
};

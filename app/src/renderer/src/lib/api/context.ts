import { apiClient } from './client';

// ============================================================
// Types
// ============================================================

export interface KnowledgeEntry {
  id: string;
  domain: string;
  key: string;
  value: string;
  source: string;
  confidence: number;
  usageCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface DecisionRecord {
  id: string;
  decision: string;
  rationale: string;
  context: string;
  outcome: string | null;
  createdAt: string;
}

export interface ProjectContext {
  id: string;
  projectId: string;
  knowledge: KnowledgeEntry[];
  decisions: DecisionRecord[];
  lastUpdated: string;
}

// ============================================================
// API Functions
// ============================================================

export const contextApi = {
  /**
   * Get project context
   */
  async getProjectContext(projectId: string): Promise<ProjectContext> {
    return apiClient.get<ProjectContext>(`/api/context/${projectId}`);
  },

  /**
   * Add knowledge entry
   */
  async addKnowledge(
    projectId: string,
    domain: string,
    key: string,
    value: string
  ): Promise<KnowledgeEntry> {
    return apiClient.post<KnowledgeEntry>(`/api/context/${projectId}/knowledge`, {
      domain,
      key,
      value
    });
  },

  /**
   * Record decision
   */
  async recordDecision(
    projectId: string,
    decision: string,
    rationale: string,
    context?: string
  ): Promise<DecisionRecord> {
    return apiClient.post<DecisionRecord>(`/api/context/${projectId}/decisions`, {
      decision,
      rationale,
      context: context || ''
    });
  },

  /**
   * Search knowledge
   */
  async searchKnowledge(
    projectId: string,
    query: string,
    domain?: string
  ): Promise<KnowledgeEntry[]> {
    const params = new URLSearchParams({ q: query });
    if (domain) params.set('domain', domain);
    return apiClient.get<KnowledgeEntry[]>(
      `/api/context/${projectId}/search?${params}`
    );
  },

  /**
   * Get context statistics
   */
  async getStats(projectId: string): Promise<Record<string, unknown>> {
    return apiClient.get<Record<string, unknown>>(`/api/context/${projectId}/stats`);
  }
};

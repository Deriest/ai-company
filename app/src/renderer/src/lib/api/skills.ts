import { apiClient } from "./client";

export interface SkillRecord {
  id: string;
  skill_id: string;
  name: string;
  description: string;
  category: string;
  source: string;
  assigned_workers: string[];
  is_enabled: boolean;
  instructions: string;
}

export const skillsApi = {
  async list(enabledOnly = false): Promise<SkillRecord[]> {
    const qs = enabledOnly ? "?enabled_only=true" : "";
    return apiClient.get<SkillRecord[]>(`/skills${qs}`);
  },

  async toggle(skillId: string, enabled: boolean): Promise<{ skill_id: string; is_enabled: boolean }> {
    return apiClient.post(`/skills/${skillId}/toggle`, { enabled });
  },

  async assignWorkers(skillId: string, workers: string[]): Promise<{ skill_id: string; assigned_workers: string[] }> {
    return apiClient.post(`/skills/${skillId}/assign`, { workers });
  },

  async create(payload: {
    skill_id: string;
    name: string;
    description?: string;
    category?: string;
    instructions: string;
    assigned_workers?: string[];
  }): Promise<SkillRecord> {
    return apiClient.post<SkillRecord>("/skills", payload);
  },

  async delete(skillId: string): Promise<void> {
    return apiClient.delete(`/skills/${skillId}`);
  },

  async reseed(): Promise<void> {
    return apiClient.post("/skills/seed");
  },
};

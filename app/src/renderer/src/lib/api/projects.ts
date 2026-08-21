import { apiClient } from "./client";

export interface ProjectRecord {
  id: string;
  name: string;
  slug: string;
  description: string;
  repo_path: string;
  folder?: string;
  tags: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export const projectsApi = {
  list: () => apiClient.get<ProjectRecord[]>("/projects"),
create: (data: { name: string; description?: string; repo_path?: string; folder?: string; tags?: string[] }) =>
    apiClient.post<ProjectRecord>("/projects", data),
  update: (id: string, data: Partial<ProjectRecord>) =>
    apiClient.patch<ProjectRecord>(`/projects/${id}`, data),
  delete: (id: string) => apiClient.delete(`/projects/${id}`),
  activate: (id: string) => apiClient.post(`/projects/${id}/activate`),
  getActive: () => apiClient.get<ProjectRecord | null>("/projects/active"),
};

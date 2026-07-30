import { apiClient } from "./client";

export interface HealthCheckResult {
  id: string;
  name: string;
  status: "connected" | "error";
  latency_ms?: number;
  error?: string;
}

export interface TestConnectionResult {
  success: boolean;
  latency_ms?: number;
  models?: number;
  error?: string;
}

export interface EnvConfig {
  base_url: string;
  api_key: string;
  provider_name: string;
  thinker: string;
  crafter: string;
  sprinter: string;
}

export const providerManageApi = {
  getEnvConfig: () =>
    apiClient.get<EnvConfig>("/providers/config"),

  updateEnvConfig: (payload: Partial<EnvConfig>) =>
    apiClient.post<{ success: boolean }>("/providers/config", payload),

  testConnection: (endpoint: string, apiKey: string) =>
    apiClient.post<TestConnectionResult>("/providers/test-connection", {
      endpoint,
      api_key: apiKey,
    }),

  healthCheck: () =>
    apiClient.get<HealthCheckResult[]>("/providers/health"),

  updateConfig: (providerId: string, config: Record<string, unknown>) =>
    apiClient.put<{ id: string; name: string; status: string }>(
      `/providers/${providerId}/config`,
      config,
    ),
};

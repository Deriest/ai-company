import { apiClient } from "./client";

export type TelemetryPrefs = {
  crashReports: boolean;
  diagnostics: boolean;
  performance: boolean;
  usageAnalytics: boolean;
};

// Backend DTO
interface SettingsResponse {
  crash_reports: boolean;
  diagnostics: boolean;
  performance: boolean;
  usage_analytics: boolean;
  session_timeout: number;
}

interface CompanyResponse {
  id: string;
  name: string;
  slug: string;
  language: string;
  timezone: string;
}

export const settingsApi = {
  async getTelemetry(): Promise<TelemetryPrefs> {
    const data = await apiClient.get<SettingsResponse>("/settings");
    return {
      crashReports: data.crash_reports,
      diagnostics: data.diagnostics,
      performance: data.performance,
      usageAnalytics: data.usage_analytics,
    };
  },

  async updateTelemetry(prefs: Partial<TelemetryPrefs>): Promise<TelemetryPrefs> {
    const req: { crash_reports?: boolean; diagnostics?: boolean; performance?: boolean; usage_analytics?: boolean } = {};
    if (prefs.crashReports !== undefined) req.crash_reports = prefs.crashReports;
    if (prefs.diagnostics !== undefined) req.diagnostics = prefs.diagnostics;
    if (prefs.performance !== undefined) req.performance = prefs.performance;
    if (prefs.usageAnalytics !== undefined) req.usage_analytics = prefs.usageAnalytics;

    const data = await apiClient.patch<SettingsResponse>("/settings", req);
    return {
      crashReports: data.crash_reports,
      diagnostics: data.diagnostics,
      performance: data.performance,
      usageAnalytics: data.usage_analytics,
    };
  },
  
  async getCompany(): Promise<CompanyResponse> {
    return apiClient.get<CompanyResponse>("/company");
  },

  async updateCompany(data: Partial<CompanyResponse>): Promise<CompanyResponse> {
    return apiClient.patch<CompanyResponse>("/company", data);
  }
};

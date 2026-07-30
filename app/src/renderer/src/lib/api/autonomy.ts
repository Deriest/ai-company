import { apiClient } from './client';

// ============================================================
// Types
// ============================================================

export interface AnomalyDetection {
  id: string;
  anomalyType: string;
  severity: string;
  description: string;
  affectedComponent: string;
  detectedAt: string;
  status: string;
}

export interface RecoveryAction {
  id: string;
  anomalyId: string;
  actionType: string;
  description: string;
  status: string;
  executedAt: string | null;
  result: Record<string, unknown> | null;
}

export interface HealingResult {
  id: string;
  anomalyId: string;
  recoveryId: string;
  success: boolean;
  duration: number;
  details: string;
  createdAt: string;
}

// ============================================================
// API Functions
// ============================================================

export const autonomyApi = {
  /**
   * Detect anomaly
   */
  async detectAnomaly(
    anomalyType: string,
    severity: string,
    description: string,
    affectedComponent?: string
  ): Promise<AnomalyDetection> {
    return apiClient.post<AnomalyDetection>('/api/autonomy/detect', {
      anomaly_type: anomalyType,
      severity,
      description,
      affected_component: affectedComponent || ''
    });
  },

  /**
   * Handle anomaly
   */
  async handleAnomaly(
    anomalyType: string,
    severity: string,
    description: string,
    affectedComponent?: string
  ): Promise<HealingResult> {
    return apiClient.post<HealingResult>('/api/autonomy/handle', {
      anomaly_type: anomalyType,
      severity,
      description,
      affected_component: affectedComponent || ''
    });
  },

  /**
   * Get autonomy statistics
   */
  async getStats(): Promise<Record<string, unknown>> {
    return apiClient.get<Record<string, unknown>>('/api/autonomy/stats');
  }
};

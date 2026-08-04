import { apiClient } from "./client";

/** A backup archive produced by POST /backup/create. */
export interface BackupRecord {
  filename: string;
  size: number;
  created_at: string;
}

/** Result of validating a backup archive via POST /backup/validate. */
export interface BackupValidateResult {
  valid: boolean;
  version?: string;
  created_at?: string;
  entries?: number;
  error?: string;
}

/**
 * Client for the backend backup endpoints (POST /backup/create,
 * POST /backup/validate, GET /backup/list). Creation persists the archive
 * into the backend DATA_DIR/backups; the Electron main process then offers
 * it through a native save dialog (aic:backup-create-to).
 */
export const backupApi = {
  async createBackup(): Promise<BackupRecord> {
    return apiClient.post<BackupRecord>("/backup/create");
  },

  async validateBackup(filename: string): Promise<BackupValidateResult> {
    return apiClient.post<BackupValidateResult>("/backup/validate", { filename });
  },

  async listBackups(): Promise<BackupRecord[]> {
    return apiClient.get<BackupRecord[]>("/backup/list");
  },
};
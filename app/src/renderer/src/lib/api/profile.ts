import { apiClient } from './client';

export interface LocalProfile {
  id: string;
  displayName: string;
  deviceId: string;
  projectRoot?: string;
  appVersion: string;
  onboardingCompleted: boolean;
  createdAt: string | null;
  lastSeen: string | null;
}

export const profileApi = {
  async get(): Promise<LocalProfile | null> {
    try {
      return await apiClient.get('/profile');
    } catch (e: unknown) {
      if (e instanceof Error && e.message.includes('404')) return null;
      throw e;
    }
  },

  async create(displayName: string): Promise<LocalProfile> {
    return apiClient.post('/profile', { displayName });
  },

  async update(data: { displayName?: string; appVersion?: string; projectRoot?: string }): Promise<LocalProfile> {
    return apiClient.patch('/profile', data);
  },

  async completeOnboarding(): Promise<LocalProfile> {
    return apiClient.post('/profile/complete-onboarding', {});
  },
};

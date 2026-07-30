import { apiClient } from "./client";

// ── Types ────────────────────────────────────────────────────

export type ActionType = "notify" | "job" | "webhook" | "script";
export type NotificationLevel = "info" | "warning" | "error" | "success";

export type EventHookRecord = {
  id: string;
  name: string;
  eventType: string;
  actionType: ActionType;
  isEnabled: boolean;
  fireCount: number;
};

export type TriggerRecord = {
  id: string;
  name: string;
  condition: Record<string, any>;
  action: Record<string, any>;
  isEnabled: boolean;
  fireCount: number;
};

export type NotificationRecord = {
  id: string;
  title: string;
  message: string;
  level: NotificationLevel;
  source: string | null;
  isRead: boolean;
  createdAt: string;
};

export type CreateHookPayload = {
  event_type: string;
  name: string;
  action_type: ActionType;
  action_config?: Record<string, any>;
  description?: string;
};

export type CreateTriggerPayload = {
  name: string;
  condition: Record<string, any>;
  action: Record<string, any>;
  description?: string;
};

// ── API ──────────────────────────────────────────────────────

export const automationApi = {
  // ── Event Hooks ────────────────────────────────────────────

  async createHook(payload: CreateHookPayload): Promise<{ id: string; name: string; eventType: string; actionType: string }> {
    return apiClient.post("/hooks", payload);
  },

  async listHooks(params?: { event_type?: string }): Promise<EventHookRecord[]> {
    const query = new URLSearchParams();
    if (params?.event_type) query.append("event_type", params.event_type);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiClient.get<EventHookRecord[]>(`/hooks${qs}`);
  },

  async deleteHook(hookId: string): Promise<void> {
    await apiClient.delete(`/hooks/${hookId}`);
  },

  async fireEvent(eventType: string): Promise<{ fired: number }> {
    return apiClient.post(`/hooks/fire/${eventType}`);
  },

  // ── Triggers ───────────────────────────────────────────────

  async createTrigger(payload: CreateTriggerPayload): Promise<{ id: string; name: string }> {
    return apiClient.post("/triggers", payload);
  },

  async listTriggers(): Promise<TriggerRecord[]> {
    return apiClient.get<TriggerRecord[]>("/triggers");
  },

  async deleteTrigger(triggerId: string): Promise<void> {
    await apiClient.delete(`/triggers/${triggerId}`);
  },

  // ── Notifications ──────────────────────────────────────────

  async listNotifications(params?: { is_read?: boolean }): Promise<NotificationRecord[]> {
    const query = new URLSearchParams();
    if (params?.is_read !== undefined) query.append("is_read", String(params.is_read));
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiClient.get<NotificationRecord[]>(`/notifications${qs}`);
  },

  async markRead(notifId: string): Promise<{ id: string; isRead: boolean }> {
    return apiClient.patch(`/notifications/${notifId}/read`);
  },

  async markAllRead(): Promise<void> {
    await apiClient.post("/notifications/read-all");
  },
};

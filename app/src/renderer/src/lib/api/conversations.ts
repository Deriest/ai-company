import { apiClient } from "./client";

export type ConversationRecord = {
  id: string;
  title: string;
  folder_id?: string | null;
  is_archived: boolean;
  is_favorite: boolean;
  is_pinned: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type AttachmentRecord = {
  id: string;
  message_id: string;
  file_name: string;
  file_type: string;
  mime_type: string;
  file_size: number;
  attachment_metadata?: Record<string, any>;
  created_at: string;
};

export type MessageRecord = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool" | "developer";
  content: string;
  message_metadata?: Record<string, any>;
  token_count?: number | null;
  model_id?: string | null;
  provider_id?: string | null;
  status: "pending" | "streaming" | "completed" | "error";
  created_at: string;
  updated_at: string;
  attachments: AttachmentRecord[];
};

export type SearchResultItem = {
  target_type: "conversation" | "message";
  target_id: string;
  conversation_id: string;
  title: string;
  snippet: string;
  tags: string;
};

export const conversationsApi = {
  async list(params?: { folder_id?: string; is_archived?: boolean; is_favorite?: boolean; tag?: string }): Promise<ConversationRecord[]> {
    const query = new URLSearchParams();
    if (params?.folder_id) query.append("folder_id", params.folder_id);
    if (params?.is_archived !== undefined) query.append("is_archived", String(params.is_archived));
    if (params?.is_favorite !== undefined) query.append("is_favorite", String(params.is_favorite));
    if (params?.tag) query.append("tag", params.tag);
    
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiClient.get<ConversationRecord[]>(`/api/conversations${qs}`);
  },

  async create(title = "New Conversation", folder_id?: string, tags: string[] = [], project_id?: string): Promise<ConversationRecord> {
    return apiClient.post<ConversationRecord>(`/api/conversations`, { title, folder_id, tags, project_id });
  },

  async get(id: string): Promise<ConversationRecord> {
    return apiClient.get<ConversationRecord>(`/api/conversations/${id}`);
  },

  /**
   * Fetch several conversations by id in parallel, skipping any that no longer
   * exist (404). Used by sidebar search: /conversations/search returns ids
   * (not full records), and re-filtering search hits against /conversations —
   * which defaults to a limit of 50 — silently dropped matches older than the
   * 50 most-recent conversations. Fetching each hit by id surfaces ALL matches.
   */
  async getMany(ids: string[]): Promise<ConversationRecord[]> {
    const unique = Array.from(new Set(ids));
    const fetched = await Promise.all(unique.map(async (id) => {
      try {
        return await conversationsApi.get(id);
      } catch {
        return null;
      }
    }));
    return fetched.filter((c): c is ConversationRecord => c !== null);
  },

  async update(id: string, partial: Partial<{ title: string; folder_id: string | null; is_archived: boolean; is_favorite: boolean; is_pinned: boolean; tags: string[] }>): Promise<ConversationRecord> {
    return apiClient.put<ConversationRecord>(`/api/conversations/${id}`, partial);
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/api/conversations/${id}`);
  },

  async duplicate(id: string): Promise<ConversationRecord> {
    return apiClient.post<ConversationRecord>(`/api/conversations/${id}/duplicate`);
  },

  async search(query: string): Promise<SearchResultItem[]> {
    return apiClient.get<SearchResultItem[]>(`/api/conversations/search?q=${encodeURIComponent(query)}`);
  },

  async listMessages(conversationId: string, limit?: number): Promise<MessageRecord[]> {
    // Backend caps limit at 1000 (messages route). Explicit limit avoids the
    // 500-message default silently truncating long conversations.
    const qs = limit !== undefined ? `?limit=${Math.min(Math.max(limit, 1), 1000)}` : "";
    return apiClient.get<MessageRecord[]>(`/api/conversations/${conversationId}/messages${qs}`);
  },

  async createMessage(conversationId: string, payload: { role: string; content: string; message_metadata?: any; token_count?: number; model_id?: string; provider_id?: string; status?: string; attachments?: any[] }): Promise<MessageRecord> {
    return apiClient.post<MessageRecord>(`/api/conversations/${conversationId}/messages`, payload);
  },

  async updateMessage(messageId: string, partial: Partial<{ content: string; message_metadata: any; token_count: number; status: string }>): Promise<MessageRecord> {
    return apiClient.patch<MessageRecord>(`/api/messages/${messageId}`, partial);
  },

  async deleteMessage(messageId: string): Promise<void> {
    await apiClient.delete(`/api/messages/${messageId}`);
  }
};
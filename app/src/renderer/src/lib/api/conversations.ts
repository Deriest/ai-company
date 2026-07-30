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
    return apiClient.get<ConversationRecord[]>(`/conversations${qs}`);
  },

  async create(title = "New Conversation", folder_id?: string, tags: string[] = []): Promise<ConversationRecord> {
    return apiClient.post<ConversationRecord>("/conversations", { title, folder_id, tags });
  },

  async get(id: string): Promise<ConversationRecord> {
    return apiClient.get<ConversationRecord>(`/conversations/${id}`);
  },

  async update(id: string, partial: Partial<{ title: string; folder_id: string | null; is_archived: boolean; is_favorite: boolean; is_pinned: boolean; tags: string[] }>): Promise<ConversationRecord> {
    return apiClient.patch<ConversationRecord>(`/conversations/${id}`, partial);
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/conversations/${id}`);
  },

  async duplicate(id: string): Promise<ConversationRecord> {
    return apiClient.post<ConversationRecord>(`/conversations/${id}/duplicate`);
  },

  async search(query: string): Promise<SearchResultItem[]> {
    return apiClient.get<SearchResultItem[]>(`/conversations/search?q=${encodeURIComponent(query)}`);
  },

  async listMessages(conversationId: string): Promise<MessageRecord[]> {
    return apiClient.get<MessageRecord[]>(`/conversations/${conversationId}/messages`);
  },

  async createMessage(conversationId: string, payload: { role: string; content: string; message_metadata?: any; token_count?: number; model_id?: string; provider_id?: string; status?: string; attachments?: any[] }): Promise<MessageRecord> {
    return apiClient.post<MessageRecord>(`/conversations/${conversationId}/messages`, payload);
  },

  async updateMessage(messageId: string, partial: Partial<{ content: string; message_metadata: any; token_count: number; status: string }>): Promise<MessageRecord> {
    return apiClient.patch<MessageRecord>(`/messages/${messageId}`, partial);
  },

  async deleteMessage(messageId: string): Promise<void> {
    await apiClient.delete(`/messages/${messageId}`);
  }
};

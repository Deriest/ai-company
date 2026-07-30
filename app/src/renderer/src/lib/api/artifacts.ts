import { apiClient } from "./client";

export type ArtifactRecord = {
  id: string;
  conversation_id: string;
  message_id?: string;
  type: string;
  title: string;
  content: string;
  language?: string;
  mime_type: string;
  created_at: string;
};

export const artifactsApi = {
  async listForConversation(conversationId: string): Promise<ArtifactRecord[]> {
    return apiClient.get<ArtifactRecord[]>(`/artifacts/${conversationId}`);
  }
};

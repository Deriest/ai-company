import { apiClient } from "./client";

// ── Types ────────────────────────────────────────────────────

export type DocumentContentType = "text" | "pdf" | "markdown" | "code";
export type DocumentStatus = "loaded" | "chunking" | "embedding" | "ready" | "error";

export type RagDocumentRecord = {
  id: string;
  title: string;
  source: string | null;
  contentType: DocumentContentType;
  chunkCount: number;
  status: DocumentStatus;
  createdAt: string;
};

export type RagDocumentDetail = RagDocumentRecord & {
  embeddingModel: string | null;
};

export type RagRetrieveResult = {
  chunkId: string;
  documentId: string;
  documentTitle: string;
  content: string;
  similarity: number;
  chunkIndex: number;
  tokenCount: number | null;
};

export type RagContextResult = {
  context: string;
  citations: RagCitation[];
  totalTokens: number;
  chunksUsed: number;
};

export type RagCitation = {
  index: number;
  documentTitle: string;
  chunkIndex: number;
  similarity: number;
};

export type LoadDocumentPayload = {
  title: string;
  content: string;
  source?: string;
  content_type?: DocumentContentType;
  chunk_size?: number;
  chunk_overlap?: number;
};

export type RetrievePayload = {
  query: string;
  top_k?: number;
};

export type ContextPayload = {
  query: string;
  top_k?: number;
  max_tokens?: number;
};

// ── API ──────────────────────────────────────────────────────

export const ragApi = {
  async loadDocument(payload: LoadDocumentPayload): Promise<RagDocumentDetail> {
    return apiClient.post<RagDocumentDetail>("/rag/documents", payload);
  },

  async listDocuments(): Promise<RagDocumentRecord[]> {
    return apiClient.get<RagDocumentRecord[]>("/rag/documents");
  },

  async deleteDocument(docId: string): Promise<void> {
    await apiClient.delete(`/rag/documents/${docId}`);
  },

  async retrieve(payload: RetrievePayload): Promise<RagRetrieveResult[]> {
    return apiClient.post<RagRetrieveResult[]>("/rag/retrieve", payload);
  },

  async buildContext(payload: ContextPayload): Promise<RagContextResult> {
    return apiClient.post<RagContextResult>("/rag/context", payload);
  },
};

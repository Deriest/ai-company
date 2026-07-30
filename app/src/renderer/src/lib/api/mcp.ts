import { apiClient } from "./client";

// ── Types ────────────────────────────────────────────────────

export type MCPServerProtocol = "stdio" | "sse" | "http";

export type MCPServerRecord = {
  id: string;
  name: string;
  endpoint: string;
  protocol: MCPServerProtocol;
  isEnabled: boolean;
  status: string;
  description: string | null;
};

export type MCPToolRecord = {
  id: string;
  registryId: string;
  toolName: string;
  description: string | null;
  isEnabled: boolean;
  requiresApproval: boolean;
};

export type MCPToolExecutionRecord = {
  id: string;
  toolName: string;
  status: string;
  executionTimeMs: number;
  createdAt: string;
};

export type MCPToolExecutionDetail = MCPToolExecutionRecord & {
  output: any;
  errorMessage: string | null;
};

export type RegisterServerPayload = {
  name: string;
  endpoint: string;
  protocol?: MCPServerProtocol;
  description?: string;
  config?: Record<string, any>;
};

export type UpdateServerPayload = {
  name?: string;
  endpoint?: string;
  protocol?: MCPServerProtocol;
  description?: string;
  is_enabled?: boolean;
  config?: Record<string, any>;
};

export type DiscoverToolsPayload = {
  tools: { name: string; description?: string; inputSchema?: Record<string, any>; requires_approval?: boolean }[];
};

export type ExecuteToolPayload = {
  arguments: Record<string, any>;
  conversation_id?: string;
};

export type ApproveExecutionPayload = {
  approved: boolean;
};

// ── API ──────────────────────────────────────────────────────

export const mcpApi = {
  async registerServer(payload: RegisterServerPayload): Promise<{ id: string; name: string; endpoint: string; status: string }> {
    return apiClient.post("/mcp/servers", payload);
  },

  async listServers(): Promise<MCPServerRecord[]> {
    return apiClient.get<MCPServerRecord[]>("/mcp/servers");
  },

  async updateServer(serverId: string, payload: UpdateServerPayload): Promise<{ id: string; name: string; status: string }> {
    return apiClient.patch(`/mcp/servers/${serverId}`, payload);
  },

  async deleteServer(serverId: string): Promise<void> {
    await apiClient.delete(`/mcp/servers/${serverId}`);
  },

  async discoverTools(serverId: string, payload: DiscoverToolsPayload): Promise<{ id: string; toolName: string; description: string | null }[]> {
    return apiClient.post(`/mcp/servers/${serverId}/discover`, payload);
  },

  async listTools(params?: { server_id?: string }): Promise<MCPToolRecord[]> {
    const query = new URLSearchParams();
    if (params?.server_id) query.append("server_id", params.server_id);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiClient.get<MCPToolRecord[]>(`/mcp/tools${qs}`);
  },

  async executeTool(toolId: string, payload: ExecuteToolPayload): Promise<MCPToolExecutionDetail> {
    return apiClient.post<MCPToolExecutionDetail>(`/mcp/tools/${toolId}/execute`, payload);
  },

  async approveExecution(executionId: string, payload: ApproveExecutionPayload): Promise<{ id: string; status: string }> {
    return apiClient.post(`/mcp/executions/${executionId}/approve`, payload);
  },

  async listExecutions(params?: { conversation_id?: string }): Promise<MCPToolExecutionRecord[]> {
    const query = new URLSearchParams();
    if (params?.conversation_id) query.append("conversation_id", params.conversation_id);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiClient.get<MCPToolExecutionRecord[]>(`/mcp/executions${qs}`);
  },

  async connectServer(serverId: string): Promise<{ status: string; server_id: string; tools_discovered: number; tools: any[] }> {
    return apiClient.post(`/mcp/servers/${serverId}/connect`);
  },

  async disconnectServer(serverId: string): Promise<{ status: string; server_id: string }> {
    return apiClient.post(`/mcp/servers/${serverId}/disconnect`);
  },

  async getToolSchemas(): Promise<any[]> {
    return apiClient.get("/mcp/tools/schema");
  },
};

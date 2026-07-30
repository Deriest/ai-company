/* ================================================================
   AIC-ADE Frontend API Contracts
   Typed interfaces — frontend never depends on backend internals.
   ================================================================ */

// ── Worker ──────────────────────────────────────────────────────

export type WorkerStatus = "idle" | "thinking" | "planning" | "coding" | "testing" | "reviewing" | "waiting_approval" | "completed" | "failed" | "offline";

export type Department = "Leadership" | "Product" | "Engineering" | "Platform";

export interface WorkerDTO {
  id: string;
  name: string;
  role: string;
  tier: string;
  department: Department;
  personality: string;
  phase: string;
  initial: string;
  status: WorkerStatus;
  currentTask?: string;
  currentObjective?: string;
  assignedMission?: string;
  executionLog?: string[];
  recentEvents?: TimelineEventDTO[];
  reasoningSummary?: string;
  model?: string;
  runtime?: string;
  queue?: number;
  eta?: string;
  cpu?: number;
  mem?: string;
  memPct?: number;
  tasksCompleted?: number;
  health?: "healthy" | "degraded" | "unhealthy";
}

// ── Mission ─────────────────────────────────────────────────────

export type MissionPhase = "investigate" | "planning" | "approval" | "implementation" | "verification" | "closeout" | "completed" | "blocked" | "failed" | "cancelled";

export interface MissionDTO {
  id: string;
  projectId: string;
  title: string;
  description: string;
  type: string;
  phase: MissionPhase;
  progress: number;
  workerType?: string;
  approvalRequired: boolean;
  errorMessage?: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

// ── Project ─────────────────────────────────────────────────────

export interface ProjectDTO {
  id: string;
  name: string;
  type: string;
  status: "Active" | "Archived";
  missionCount: number;
  activeMissions: number;
  workerCount: number;
  progress: number;
  updatedAt: string;
}

// ── Conversation ────────────────────────────────────────────────

export interface ConversationDTO {
  id: string;
  title: string;
  preview: string;
  updatedAt: string;
  unread?: boolean;
  messageCount: number;
}

export interface MessageDTO {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  intent?: string;
  metadata?: Record<string, unknown>;
}

// ── Timeline / Events ───────────────────────────────────────────

export type EventType = "mission" | "worker" | "approval" | "system" | "deployment" | "runtime";
export type EventSeverity = "info" | "warning" | "error" | "success";

export interface TimelineEventDTO {
  id: string;
  type: EventType;
  title: string;
  description?: string;
  actor: string;
  target?: string;
  severity: EventSeverity;
  timestamp: string;
}

// ── Provider ────────────────────────────────────────────────────

export interface ProviderDTO {
  id: string;
  name: string;
  status: "ACTIVE" | "INACTIVE";
  endpoint: string;
  models: {
    thinker?: string;
    crafter?: string;
    sprinter?: string;
  };
  latency?: number;
  lastHealthCheck?: string;
  capabilities?: string[];
}

// ── Approval ────────────────────────────────────────────────────

export interface ApprovalDTO {
  id: string;
  missionId: string;
  type: string;
  reason: string;
  status: "pending" | "approved" | "rejected";
  createdAt: string;
  riskLevel?: "low" | "medium" | "high";
}

// ── Update ──────────────────────────────────────────────────────

export interface UpdateStateDTO {
  currentVersion: string;
  availableVersion?: string;
  status: "idle" | "checking" | "available" | "downloading" | "verifying" | "ready_to_install" | "up_to_date" | "error";
  progress?: number;
  bytesDownloaded?: number;
  bytesTotal?: number;
  error?: string;
  releaseNotes?: string;
  channel: string;
}

// ── System ──────────────────────────────────────────────────────

export interface SystemStatusDTO {
  health: "ok" | "error";
  version: string;
  database: "connected" | "disconnected";
  providers: "configured" | "not_configured";
  activeWorkers: number;
  totalWorkers: number;
  activeMissions: number;
  totalMissions: number;
  tokensToday: number;
  tokensTotal: number;
}

// ── Approval Policy ─────────────────────────────────────────────

export type ApprovalMode = "manual" | "semi_auto" | "full_auto";

export interface ApprovalPolicyDTO {
  mode: ApprovalMode;
  description: string;
  riskLevel: "low" | "medium" | "high";
  scope: string[];
}

// ── API Contract Interface ──────────────────────────────────────

export interface IAICApi {
  // Workers
  getWorkers(): Promise<WorkerDTO[]>;
  getWorker(id: string): Promise<WorkerDTO | null>;

  // Missions
  getMissions(projectId?: string): Promise<MissionDTO[]>;
  getMission(id: string): Promise<MissionDTO | null>;
  dispatchMission(id: string): Promise<void>;
  cancelMission(id: string): Promise<void>;

  // Projects
  getProjects(): Promise<ProjectDTO[]>;

  // Conversations
  getConversations(): Promise<ConversationDTO[]>;
  getMessages(conversationId: string): Promise<MessageDTO[]>;
  sendMessage(conversationId: string, content: string): Promise<MessageDTO>;

  // Timeline
  getTimeline(limit?: number, target?: string): Promise<TimelineEventDTO[]>;

  // Providers
  getProviders(): Promise<ProviderDTO[]>;
  testProvider(id: string): Promise<{ success: boolean; latency?: number; models?: string[] }>;

  // Approvals
  getApprovals(): Promise<ApprovalDTO[]>;
  approve(id: string): Promise<void>;
  reject(id: string, reason: string): Promise<void>;

  // System
  getSystemStatus(): Promise<SystemStatusDTO>;
}

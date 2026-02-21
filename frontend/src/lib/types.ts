// =============================================================
// TypeScript types that mirror the backend API schemas.
// These define the "shape" of every piece of data in the app.
//
// We use "const objects" instead of enums because the project's
// TypeScript config has erasableSyntaxOnly enabled.
// =============================================================

// ---- Status / role constants ----

export const TaskStatus = {
  PENDING: "pending",
  ASSIGNED: "assigned",
  IN_PROGRESS: "in_progress",
  COMPLETED: "completed",
  FAILED: "failed",
  CANCELLED: "cancelled",
} as const;
export type TaskStatus = (typeof TaskStatus)[keyof typeof TaskStatus];

export const PlanStatus = {
  DRAFT: "draft",
  PENDING_PM_APPROVAL: "pending_pm_approval",
  APPROVED: "approved",
  REJECTED: "rejected",
  EXECUTED: "executed",
} as const;
export type PlanStatus = (typeof PlanStatus)[keyof typeof PlanStatus];

export const SubtaskStatus = {
  PENDING: "pending",
  DRAFT_GENERATED: "draft_generated",
  IN_REVIEW: "in_review",
  APPROVED: "approved",
  FINALIZED: "finalized",
  REJECTED: "rejected",
} as const;
export type SubtaskStatus = (typeof SubtaskStatus)[keyof typeof SubtaskStatus];

export const AgentStatus = {
  PENDING: "pending",
  ONLINE: "online",
  BUSY: "busy",
  OFFLINE: "offline",
  ERROR: "error",
} as const;
export type AgentStatus = (typeof AgentStatus)[keyof typeof AgentStatus];

export const RiskSeverity = {
  LOW: "low",
  MEDIUM: "medium",
  HIGH: "high",
  CRITICAL: "critical",
} as const;
export type RiskSeverity = (typeof RiskSeverity)[keyof typeof RiskSeverity];

export const RiskSource = {
  MERGE_CONFLICT: "merge_conflict",
  CI_FAILURE: "ci_failure",
  INTEGRATION: "integration",
  DEPENDENCY: "dependency",
  SECURITY: "security",
  REVIEWER: "reviewer",
} as const;
export type RiskSource = (typeof RiskSource)[keyof typeof RiskSource];

export const UserRole = {
  ADMIN: "admin",
  PM: "pm",
  DEVELOPER: "developer",
} as const;
export type UserRole = (typeof UserRole)[keyof typeof UserRole];

export const PricingType = {
  FREE: "free",
  USAGE_BASED: "usage_based",
} as const;
export type PricingType = (typeof PricingType)[keyof typeof PricingType];

// ---- Core data types ----

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Team {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  created_at: string;
  agent_count: number;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  goals: string[];
  milestones: Record<string, unknown>[];
  timeline: Record<string, unknown>;
  github_repo: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string | null;
}

export interface Task {
  id: string;
  title: string;
  description: string | null;
  task_type: string;
  status: TaskStatus;
  progress: number;
  assigned_agent_id: string | null;
  team_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TaskDetail extends Task {
  input_data: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  metadata: Record<string, unknown>;
}

export interface Subtask {
  id: string;
  task_id: string;
  plan_id: string | null;
  title: string;
  description: string | null;
  priority: number;
  status: SubtaskStatus;
  assignee_id: string | null;
  assigned_agent_id: string | null;
  draft_version: number;
  risk_flags: string[];
  created_at: string;
  updated_at: string | null;
}

export interface SubtaskDetail extends Subtask {
  draft_content: Record<string, unknown> | null;
  draft_generated_at: string | null;
  draft_agent_id: string | null;
  final_content: Record<string, unknown> | null;
  finalized_at: string | null;
  finalized_by_id: string | null;
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  description: string | null;
  mcp_endpoint: string;
  status: AgentStatus;
  owner_id: string;
  team_id: string | null;
  created_at: string;
  last_seen: string | null;
}

export interface AgentDetail extends Agent {
  capabilities: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface MarketplaceAgent {
  id: string;
  agent_id: string;
  seller_id: string;
  name: string;
  category: string;
  description: string | null;
  pricing_type: PricingType;
  price_per_use: number | null;
  is_verified: boolean;
  is_active: boolean;
}

export interface Plan {
  id: string;
  task_id: string;
  project_id: string;
  status: PlanStatus;
  plan_data: Record<string, unknown>;
  approved_by_id: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  version: number;
  created_at: string;
  updated_at: string | null;
}

export interface TeamMember {
  id: string;
  user_id: string;
  project_id: string;
  role: UserRole;
  skills: string[];
  capacity: number;
  current_load: number;
  created_at: string;
  updated_at: string | null;
}

export interface RiskSignal {
  id: string;
  project_id: string;
  task_id: string | null;
  subtask_id: string | null;
  source: RiskSource;
  severity: RiskSeverity;
  title: string;
  description: string | null;
  rationale: string | null;
  recommended_action: string | null;
  is_resolved: boolean;
  resolved_at: string | null;
  resolved_by_id: string | null;
  created_at: string;
  updated_at: string | null;
}

// ---- Dashboard response types ----

export interface DeveloperDashboard {
  user_id: string;
  assigned_tasks: Task[];
  assigned_subtasks: Subtask[];
  pending_reviews: Subtask[];
  recent_risks: RiskSignal[];
  workload: number;
}

export interface PMDashboard {
  project_id: string;
  project: Project;
  team_members: TeamMember[];
  tasks_by_status: Record<string, number>;
  recent_plans: Plan[];
  open_risks: RiskSignal[];
  critical_alerts: RiskSignal[];
}

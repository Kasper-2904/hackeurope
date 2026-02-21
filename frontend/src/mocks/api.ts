// =============================================================
// Mock API service — fake async functions that return mock data.
// Each function mimics a real backend endpoint.
// When the real API is ready, swap these for actual fetch/axios calls.
// =============================================================

import type {
  DeveloperDashboard,
  MarketplaceAgent,
  Plan,
  Project,
  RiskSignal,
  SubtaskDetail,
  Task,
  TeamMember,
} from "@/lib/types";

import {
  mockMarketplaceAgents,
  mockPlans,
  mockProjects,
  mockRiskSignals,
  mockSubtasks,
  mockTasks,
  mockTeamMembers,
} from "./data";

/** Small delay to simulate network latency */
function delay(ms = 200): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---- Tasks ----

export async function getTasks(): Promise<Task[]> {
  await delay();
  return mockTasks;
}

export async function getTask(id: string): Promise<Task | undefined> {
  await delay();
  return mockTasks.find((t) => t.id === id);
}

// ---- Subtasks ----

export async function getSubtasks(taskId: string): Promise<SubtaskDetail[]> {
  await delay();
  return mockSubtasks.filter((s) => s.task_id === taskId);
}

// ---- Projects ----

export async function getProjects(): Promise<Project[]> {
  await delay();
  return mockProjects;
}

export async function getProject(id: string): Promise<Project | undefined> {
  await delay();
  return mockProjects.find((p) => p.id === id);
}

// ---- Team Members ----

export async function getTeamMembers(
  projectId: string
): Promise<TeamMember[]> {
  await delay();
  return mockTeamMembers.filter((tm) => tm.project_id === projectId);
}

// ---- Plans ----

export async function getPlans(taskId?: string): Promise<Plan[]> {
  await delay();
  if (taskId) {
    return mockPlans.filter((p) => p.task_id === taskId);
  }
  return mockPlans;
}

// ---- Risk Signals ----

export async function getRiskSignals(taskId?: string): Promise<RiskSignal[]> {
  await delay();
  if (taskId) {
    return mockRiskSignals.filter((r) => r.task_id === taskId);
  }
  return mockRiskSignals;
}

// ---- Marketplace ----

export async function getMarketplaceCatalog(
  category?: string
): Promise<MarketplaceAgent[]> {
  await delay();
  if (category) {
    return mockMarketplaceAgents.filter((a) => a.category === category);
  }
  return mockMarketplaceAgents;
}

export async function getMarketplaceAgent(
  id: string
): Promise<MarketplaceAgent | undefined> {
  await delay();
  return mockMarketplaceAgents.find((a) => a.id === id);
}

// ---- Dashboard ----

export async function getDeveloperDashboard(
  userId: string
): Promise<DeveloperDashboard> {
  await delay();
  return {
    user_id: userId,
    assigned_tasks: mockTasks.filter(
      (t) => t.status !== "completed" && t.status !== "cancelled"
    ),
    assigned_subtasks: mockSubtasks.filter((s) => s.assignee_id === userId),
    pending_reviews: mockSubtasks.filter(
      (s) => s.status === "draft_generated"
    ),
    recent_risks: mockRiskSignals.filter((r) => !r.is_resolved),
    workload: 0.7,
  };
}

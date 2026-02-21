import { apiClient } from '@/lib/apiClient'
import type { Agent, PMDashboard, Plan, Project, ProjectAllowedAgent } from '@/lib/types'

export async function listProjects(): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>('/projects')
  return data
}

export async function fetchPMDashboard(projectId: string): Promise<PMDashboard> {
  const { data } = await apiClient.get<PMDashboard>(`/dashboard/pm/${projectId}`)
  return data
}

export async function listOwnedAgents(): Promise<Agent[]> {
  const { data } = await apiClient.get<Agent[]>('/agents')
  return data
}

export async function addProjectAllowedAgent(
  projectId: string,
  agentId: string,
): Promise<ProjectAllowedAgent> {
  const { data } = await apiClient.post<ProjectAllowedAgent>(
    `/projects/${projectId}/allowlist/${agentId}`,
  )
  return data
}

export async function removeProjectAllowedAgent(projectId: string, agentId: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/allowlist/${agentId}`)
}

export async function approvePlan(planId: string): Promise<Plan> {
  const { data } = await apiClient.post<Plan>(`/plans/${planId}/approve`)
  return data
}

export async function rejectPlan(planId: string, rejectionReason: string): Promise<Plan> {
  const { data } = await apiClient.post<Plan>(`/plans/${planId}/reject`, {
    rejection_reason: rejectionReason,
  })
  return data
}

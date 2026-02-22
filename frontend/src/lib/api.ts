// =============================================================
// Real API service — actual fetch calls to the backend.
// Replaces mock API with real backend endpoints at /api/v1
// =============================================================

import { apiClient } from '@/lib/apiClient'
import { authStorage } from '@/lib/authStorage'
import type {
  Agent,
  DeveloperDashboard,
  MarketplaceAgent,
  MarketplacePublishRequest,
  MarketplacePublishResponse,
  Plan,
  Project,
  RiskSignal,
  TaskReasoningLog,
  TaskReasoningLogStreamEvent,
  SubtaskDetail,
  Task,
  TaskLogsResponse,
  Team,
  TeamMember,
} from '@/lib/types'

// ---- Tasks ----

export async function getTasks(): Promise<Task[]> {
  const { data } = await apiClient.get<Task[]>('/tasks')
  return data
}

export async function getTask(id: string): Promise<Task | null> {
  try {
    const { data } = await apiClient.get<Task>(`/tasks/${id}`)
    return data
  } catch {
    return null
  }
}

export async function getTaskReasoningLogs(taskId: string): Promise<TaskReasoningLog[]> {
  const { data } = await apiClient.get<TaskReasoningLog[]>(`/tasks/${taskId}/reasoning-logs`)
  return data
}

interface ReasoningLogStreamCallbacks {
  onOpen?: () => void
  onEvent: (event: TaskReasoningLogStreamEvent) => void
  onError?: (error: Error) => void
  onClose?: () => void
}

function parseSseFrame(frame: string): { event: string; data: string } | null {
  const lines = frame.split('\n')
  let eventName = 'message'
  const dataLines: string[] = []

  for (const line of lines) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  return { event: eventName, data: dataLines.join('\n') }
}

export function subscribeTaskReasoningLogs(
  taskId: string,
  callbacks: ReasoningLogStreamCallbacks,
): () => void {
  const abortController = new AbortController()

  const run = async () => {
    try {
      const token = authStorage.getToken()
      const headers: HeadersInit = {
        Accept: 'text/event-stream',
      }
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }

      const response = await fetch(`/api/v1/tasks/${taskId}/reasoning-logs/stream`, {
        headers,
        signal: abortController.signal,
      })

      if (!response.ok || !response.body) {
        throw new Error(`Reasoning stream request failed (${response.status})`)
      }

      callbacks.onOpen?.()

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        let boundary = buffer.indexOf('\n\n')
        while (boundary !== -1) {
          const frame = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          const parsed = parseSseFrame(frame)
          if (parsed) {
            const parsedData = JSON.parse(parsed.data) as TaskReasoningLogStreamEvent
            callbacks.onEvent(parsedData)
          }
          boundary = buffer.indexOf('\n\n')
        }
      }

      callbacks.onClose?.()
    } catch (error) {
      if (abortController.signal.aborted) {
        return
      }
      callbacks.onError?.(
        error instanceof Error ? error : new Error('Unknown reasoning stream error'),
      )
    }
  }

  void run()

  return () => {
    abortController.abort()
  }
}

// ---- Subtasks ----

export async function getSubtasks(taskId: string): Promise<SubtaskDetail[]> {
  const { data } = await apiClient.get<SubtaskDetail[]>('/subtasks', {
    params: { task_id: taskId },
  })
  return data
}

// ---- Projects ----

export async function getProjects(): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>('/projects')
  return data
}

export async function getProject(id: string): Promise<Project | undefined> {
  try {
    const { data } = await apiClient.get<Project>(`/projects/${id}`)
    return data
  } catch {
    return undefined
  }
}

// ---- Team Members ----

export async function getTeamMembers(projectId: string): Promise<TeamMember[]> {
  const { data } = await apiClient.get<TeamMember[]>(`/team-members/project/${projectId}`)
  return data
}

// ---- Plans ----

export async function getPlans(taskId?: string): Promise<Plan[]> {
  const params = taskId ? { task_id: taskId } : {}
  const { data } = await apiClient.get<Plan[]>('/plans', { params })
  return data
}

// ---- Risk Signals ----

export async function getRiskSignals(taskId?: string): Promise<RiskSignal[]> {
  const params = taskId ? { task_id: taskId } : {}
  const { data } = await apiClient.get<RiskSignal[]>('/risks', { params })
  return data
}

// ---- Agents ----

export async function getAgents(): Promise<Agent[]> {
  const { data } = await apiClient.get<Agent[]>('/agents')
  return data
}

export async function getAgent(id: string): Promise<Agent | undefined> {
  try {
    const { data } = await apiClient.get<Agent>(`/agents/${id}`)
    return data
  } catch {
    return undefined
  }
}

// ---- Marketplace ----

export async function getMarketplaceCatalog(category?: string): Promise<MarketplaceAgent[]> {
  const params = category ? { category } : {}
  const { data } = await apiClient.get<MarketplaceAgent[]>('/marketplace/catalog', { params })
  return data
}

export async function getMarketplaceAgent(id: string): Promise<MarketplaceAgent | null> {
  try {
    const { data } = await apiClient.get<MarketplaceAgent>(`/marketplace/catalog/${id}`)
    return data
  } catch {
    return null
  }
}

export async function publishAgent(
  agentData: MarketplacePublishRequest,
  options?: { returnUrl?: string; refreshUrl?: string }
): Promise<MarketplacePublishResponse> {
  const params = new URLSearchParams()
  if (options?.returnUrl) {
    params.append('return_url', options.returnUrl)
  }
  if (options?.refreshUrl) {
    params.append('refresh_url', options.refreshUrl)
  }
  const queryString = params.toString()
  const url = queryString ? `/marketplace/publish?${queryString}` : '/marketplace/publish'
  const { data } = await apiClient.post<MarketplacePublishResponse>(url, agentData)
  return data
}

// ---- Reviewer Findings ----

export async function getReviewerFindings(projectId: string): Promise<RiskSignal[]> {
  const { data } = await apiClient.get<RiskSignal[]>('/risks', {
    params: { project_id: projectId, source: 'reviewer' },
  })
  return data
}

// ---- Teams ----

export async function getTeams(): Promise<Team[]> {
  const { data } = await apiClient.get<Team[]>('/teams')
  return data
}

export async function getTeam(teamId: string): Promise<Team | undefined> {
  try {
    const { data } = await apiClient.get<Team>(`/teams/${teamId}`)
    return data
  } catch {
    return undefined
  }
}

export async function getTeamProjects(teamId: string): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>(`/teams/${teamId}/projects`)
  return data
}

// ---- Project Tasks ----

export async function getProjectTasks(projectId: string): Promise<Task[]> {
  const { data } = await apiClient.get<Task[]>(`/projects/${projectId}/tasks`)
  return data
}

// ---- Task Status Updates ----

export async function updateTaskStatus(
  taskId: string,
  status: string,
  assignedAgentId?: string,
): Promise<Task> {
  const { data } = await apiClient.patch<Task>(`/tasks/${taskId}`, {
    status,
    assigned_agent_id: assignedAgentId,
  })
  return data
}

export async function updateTaskProgress(
  taskId: string,
  progress: number,
  message?: string,
): Promise<Task> {
  const { data } = await apiClient.patch<Task>(`/tasks/${taskId}/progress`, {
    progress,
    message,
  })
  return data
}

export async function cancelTask(taskId: string): Promise<Task> {
  const { data } = await apiClient.post<Task>(`/tasks/${taskId}/cancel`)
  return data
}

export interface TaskStartResponse {
  task_id: string
  status: string
  message: string
  orchestration_result: Record<string, unknown> | null
  error: string | null
}

export async function startTask(taskId: string, projectId: string): Promise<TaskStartResponse> {
  const { data } = await apiClient.post<TaskStartResponse>(`/tasks/${taskId}/start`, {
    project_id: projectId,
  })
  return data
}

// ---- Task Logs (Real-time Activity) ----

export async function getTaskLogs(
  taskId: string,
  afterSequence: number = 0,
  limit: number = 50,
): Promise<TaskLogsResponse> {
  const { data } = await apiClient.get<TaskLogsResponse>(`/tasks/${taskId}/logs`, {
    params: { after_sequence: afterSequence, limit },
  })
  return data
}

// ---- Dashboard ----

export async function getDeveloperDashboard(userId: string): Promise<DeveloperDashboard> {
  const { data } = await apiClient.get<DeveloperDashboard>(`/dashboard/developer/${userId}`)
  return data
}

// ---- Shared Context Files ----

export interface SharedContextFileInfo {
  filename: string
  size_bytes: number
  updated_at: string
}

export interface SharedContextFileDetail {
  filename: string
  content: string
  updated_at: string
}

export async function getSharedContextFiles(): Promise<SharedContextFileInfo[]> {
  const { data } = await apiClient.get<SharedContextFileInfo[]>('/shared-context/files')
  return data
}

export async function getSharedContextFile(filename: string): Promise<SharedContextFileDetail> {
  const { data } = await apiClient.get<SharedContextFileDetail>(
    `/shared-context/files/${encodeURIComponent(filename)}`,
  )
  return data
}

export async function updateSharedContextFile(
  filename: string,
  content: string,
): Promise<SharedContextFileDetail> {
  const { data } = await apiClient.put<SharedContextFileDetail>(
    `/shared-context/files/${encodeURIComponent(filename)}`,
    { content },
  )
  return data
}

export async function createSharedContextFile(
  filename: string,
  content: string,
): Promise<SharedContextFileDetail> {
  const { data } = await apiClient.post<SharedContextFileDetail>(
    '/shared-context/files',
    { filename, content },
  )
  return data
}

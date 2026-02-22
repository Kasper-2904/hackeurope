import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ProgressBar } from '@/components/shared/ProgressBar'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { toApiErrorMessage } from '@/lib/apiClient'
import { AxiosError } from 'axios'
import { getProjectTasks } from '@/lib/api'
import {
  addProjectAllowedAgent,
  addMarketplaceAgentToProject,
  approvePlan,
  createPMTask,
  fetchPMDashboard,
  getMarketplaceCatalogForProject,
  listOwnedAgents,
  rejectPlan,
  removeProjectAllowedAgent,
} from '@/lib/pmApi'
import { TaskStatus, type MarketplaceAgent } from '@/lib/types'

const taskColumns = [
  { status: TaskStatus.PENDING, label: 'Pending', color: 'bg-slate-100' },
  { status: TaskStatus.ASSIGNED, label: 'Assigned', color: 'bg-blue-50' },
  { status: TaskStatus.IN_PROGRESS, label: 'In Progress', color: 'bg-amber-50' },
  { status: TaskStatus.COMPLETED, label: 'Completed', color: 'bg-green-50' },
]

const taskTypeOptions = [
  { value: 'code_generation', label: 'Code Generation' },
  { value: 'code_review', label: 'Code Review' },
  { value: 'test_generation', label: 'Test Generation' },
  { value: 'documentation', label: 'Documentation' },
  { value: 'bug_fix', label: 'Bug Fix' },
  { value: 'refactor', label: 'Refactor' },
]

function formatDate(value: string | null): string {
  if (!value) return 'n/a'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'n/a'
  return date.toLocaleDateString()
}

function getTaskCreateErrorMessage(error: unknown): string {
  if (!(error instanceof AxiosError)) {
    return 'Unable to create task right now. Please try again.'
  }

  if (error.response?.status === 403) {
    return 'You do not have permission to create tasks for this project.'
  }

  if (error.response?.status === 404) {
    return 'Project not found or you no longer have access.'
  }

  if (error.response?.status === 422) {
    return 'Please check required fields and task type before submitting.'
  }

  if (error.response?.status === 400) {
    return 'Task request is invalid. Please review the form and try again.'
  }

  return toApiErrorMessage(error, 'Unable to create task right now. Please try again.')
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [marketplaceCategory, setMarketplaceCategory] = useState('')
  const [rejectingPlanId, setRejectingPlanId] = useState<string | null>(null)
  const [rejectionReason, setRejectionReason] = useState('')
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [newTaskType, setNewTaskType] = useState(taskTypeOptions[0].value)
  const [newTaskDescription, setNewTaskDescription] = useState('')
  const [taskCreateError, setTaskCreateError] = useState<string | null>(null)
  const projectId = id ?? ''

  const dashboardQuery = useQuery({
    queryKey: ['pm-dashboard', projectId],
    queryFn: () => fetchPMDashboard(projectId),
    enabled: Boolean(projectId),
  })

  const tasksQuery = useQuery({
    queryKey: ['project-tasks', projectId],
    queryFn: () => getProjectTasks(projectId),
    enabled: Boolean(projectId),
  })

  const agentsQuery = useQuery({
    queryKey: ['owned-agents'],
    queryFn: listOwnedAgents,
    enabled: Boolean(projectId),
  })

  const marketplaceQuery = useQuery({
    queryKey: ['marketplace-catalog', marketplaceCategory],
    queryFn: () => getMarketplaceCatalogForProject(marketplaceCategory || undefined),
    enabled: Boolean(projectId),
  })

  const addAllowedAgentMutation = useMutation({
    mutationFn: (agentId: string) => addProjectAllowedAgent(projectId, agentId),
    onSuccess: () => {
      setActionMessage('Agent added to project allowlist.')
      setSelectedAgentId('')
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['owned-agents'] })
    },
    onError: (error: unknown) => {
      const message = toApiErrorMessage(error, 'Failed to add agent')
      if (message.includes('already') || (error instanceof AxiosError && error.response?.status === 409)) {
        setActionMessage('Agent is already in the allowlist.')
        void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
      } else {
        setActionMessage(message)
      }
    },
  })

  const removeAllowedAgentMutation = useMutation({
    mutationFn: (agentId: string) => removeProjectAllowedAgent(projectId, agentId),
    onSuccess: () => {
      setActionMessage('Agent removed from project allowlist.')
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['owned-agents'] })
      void queryClient.invalidateQueries({ queryKey: ['marketplace-catalog', marketplaceCategory] })
    },
    onError: (error: unknown) => {
      setActionMessage(toApiErrorMessage(error, 'Failed to remove agent'))
    },
  })

  const addMarketplaceAgentMutation = useMutation({
    mutationFn: (agentId: string) => addMarketplaceAgentToProject(projectId, agentId),
    onSuccess: () => {
      setActionMessage('Marketplace agent added to project allowlist.')
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['marketplace-catalog', marketplaceCategory] })
    },
    onError: (error: unknown) => {
      const message = toApiErrorMessage(error, 'Failed to add agent')
      if (message.includes('already') || (error instanceof AxiosError && error.response?.status === 409)) {
        setActionMessage('Agent is already in the allowlist.')
        // Refresh to update the UI
        void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
        void queryClient.invalidateQueries({ queryKey: ['marketplace-catalog', marketplaceCategory] })
      } else {
        setActionMessage(message)
      }
    },
  })

  const approvePlanMutation = useMutation({
    mutationFn: (planId: string) => approvePlan(planId),
    onSuccess: () => {
      setActionMessage(`Plan approved.`)
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
    },
  })

  const rejectPlanMutation = useMutation({
    mutationFn: ({ planId, reason }: { planId: string; reason: string }) => rejectPlan(planId, reason),
    onSuccess: () => {
      setRejectingPlanId(null)
      setRejectionReason('')
      setActionMessage(`Plan rejected.`)
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
    },
  })

  const createTaskMutation = useMutation({
    mutationFn: () =>
      createPMTask({
        title: newTaskTitle.trim(),
        task_type: newTaskType,
        description: newTaskDescription.trim() || undefined,
        project_id: projectId,
      }),
    onSuccess: () => {
      setNewTaskTitle('')
      setNewTaskType(taskTypeOptions[0].value)
      setNewTaskDescription('')
      setTaskCreateError(null)
      setActionMessage('Task created successfully.')
      void queryClient.invalidateQueries({ queryKey: ['project-tasks', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
    },
    onError: (error) => {
      setTaskCreateError(getTaskCreateErrorMessage(error))
    },
  })

  const allowedAgentIds = useMemo(
    () => new Set((dashboardQuery.data?.allowed_agents ?? []).map((entry) => entry.agent_id)),
    [dashboardQuery.data?.allowed_agents],
  )

  const candidateAgents = useMemo(
    () => (agentsQuery.data ?? []).filter((agent) => !allowedAgentIds.has(agent.id)),
    [agentsQuery.data, allowedAgentIds],
  )

  // Filter marketplace agents that are not already in the allowlist
  const candidateMarketplaceAgents = useMemo(
    () => (marketplaceQuery.data ?? []).filter((agent: MarketplaceAgent) => !allowedAgentIds.has(agent.agent_id)),
    [marketplaceQuery.data, allowedAgentIds],
  )

  if (!projectId) {
    return <p className="text-sm text-red-600">Project ID is missing.</p>
  }

  if (dashboardQuery.isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-sm text-slate-500">Loading project...</div>
      </div>
    )
  }

  if (dashboardQuery.isError) {
    return (
      <div className="p-4">
        <p className="text-sm text-red-600">
          {toApiErrorMessage(dashboardQuery.error, 'Failed to load project.')}
        </p>
      </div>
    )
  }

  const dashboard = dashboardQuery.data
  const tasks = tasksQuery.data ?? []

  if (!dashboard || !dashboard.project) {
    return <p className="text-sm text-red-600">Project not found or you don't have access.</p>
  }

  const project = dashboard.project

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-slate-200 pb-4">
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-2">
          <Link to="/dashboard" className="hover:text-slate-700">Dashboard</Link>
          <span>/</span>
          <Link to="/projects" className="hover:text-slate-700">Projects</Link>
          <span>/</span>
          <span className="text-slate-900">{project.name}</span>
        </div>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">{project.name}</h1>
            <p className="text-sm text-slate-500 mt-1">
              {project.description || 'No description'}
            </p>
          </div>
          {project.github_repo && (
            <a
              href={project.github_repo}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 rounded-md hover:bg-slate-200"
            >
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              GitHub
            </a>
          )}
        </div>
      </div>

      {actionMessage && (
        <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-700">
          {actionMessage}
          <button
            className="ml-2 text-sky-500 hover:text-sky-700"
            onClick={() => setActionMessage(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <Tabs defaultValue="tasks" className="space-y-4">
        <TabsList variant="jira">
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="plans">Plans</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        {/* Tasks Tab - Kanban Board */}
        <TabsContent value="tasks" className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Create Task</CardTitle>
              <CardDescription>Create a new project task for PM workflow.</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-3"
                onSubmit={(event) => {
                  event.preventDefault()
                  setTaskCreateError(null)

                  if (!newTaskTitle.trim()) {
                    setTaskCreateError('Task title is required.')
                    return
                  }

                  createTaskMutation.mutate()
                }}
              >
                <Input
                  value={newTaskTitle}
                  onChange={(event) => setNewTaskTitle(event.target.value)}
                  placeholder="Task title"
                  disabled={createTaskMutation.isPending}
                  required
                />

                <div className="grid gap-3 md:grid-cols-2">
                  <select
                    className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm"
                    value={newTaskType}
                    onChange={(event) => setNewTaskType(event.target.value)}
                    disabled={createTaskMutation.isPending}
                    required
                  >
                    {taskTypeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>

                  <Input
                    value={newTaskDescription}
                    onChange={(event) => setNewTaskDescription(event.target.value)}
                    placeholder="Description (optional)"
                    disabled={createTaskMutation.isPending}
                  />
                </div>

                {taskCreateError && (
                  <p className="text-sm text-red-600" role="alert">
                    {taskCreateError}
                  </p>
                )}

                <Button type="submit" disabled={createTaskMutation.isPending}>
                  {createTaskMutation.isPending ? 'Creating...' : 'Create Task'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">Task Board</h2>
            <Badge variant="outline" className="text-xs">
              {tasks.length} {tasks.length === 1 ? 'task' : 'tasks'}
            </Badge>
          </div>

          {tasksQuery.isLoading ? (
            <p className="text-sm text-slate-500">Loading tasks...</p>
          ) : tasks.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <div className="rounded-full bg-slate-100 p-3 mb-4">
                  <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                </div>
                <p className="text-sm text-slate-600 mb-2">No tasks yet</p>
                <p className="text-xs text-slate-400">Tasks linked to this project will appear here.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="flex gap-4 overflow-x-auto pb-4">
              {taskColumns.map((col) => {
                const columnTasks = tasks.filter((t) => t.status === col.status)
                return (
                  <div key={col.status} className="flex-shrink-0 w-[280px]">
                    {/* Column Header */}
                    <div className="flex items-center justify-between mb-3 px-1">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={col.status} />
                        <span className="text-xs text-slate-500 font-medium">
                          {columnTasks.length}
                        </span>
                      </div>
                    </div>

                    {/* Column Body */}
                    <div className={`space-y-3 min-h-[300px] rounded-lg ${col.color} p-3`}>
                      {columnTasks.length > 0 ? (
                        columnTasks.map((task) => (
                          <Card
                            key={task.id}
                            className="cursor-pointer transition-all hover:shadow-md hover:border-slate-300 bg-white"
                            onClick={() => navigate(`/tasks/${task.id}`)}
                          >
                            <CardContent className="p-3 space-y-2">
                              <div className="font-medium text-sm leading-tight">
                                {task.title}
                              </div>
                              {task.description && (
                                <p className="text-xs text-slate-500 line-clamp-2">
                                  {task.description}
                                </p>
                              )}
                              <ProgressBar value={task.progress} />
                              <div className="flex items-center justify-between text-xs text-slate-400">
                                <span>{task.task_type}</span>
                                {task.assigned_agent_id && (
                                  <Badge variant="outline" className="text-xs">
                                    Assigned
                                  </Badge>
                                )}
                              </div>
                            </CardContent>
                          </Card>
                        ))
                      ) : (
                        <div className="text-xs text-slate-400 text-center py-8">
                          No tasks
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </TabsContent>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Goals */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Goals</CardTitle>
              </CardHeader>
              <CardContent>
                {project.goals.length === 0 ? (
                  <p className="text-sm text-slate-500">No goals defined.</p>
                ) : (
                  <ul className="space-y-2">
                    {project.goals.map((goal, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm">
                        <svg className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="text-slate-700">{goal}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            {/* Task Status Summary */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Task Status</CardTitle>
              </CardHeader>
              <CardContent>
                {Object.keys(dashboard.tasks_by_status).length === 0 ? (
                  <p className="text-sm text-slate-500">No tasks linked yet.</p>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(dashboard.tasks_by_status).map(([status, count]) => (
                      <div key={status} className="rounded-md bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-500">
                          {status.replaceAll('_', ' ')}
                        </p>
                        <p className="text-xl font-semibold text-slate-900">{count}</p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Team Members */}
            <Card className="md:col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Team Members</CardTitle>
              </CardHeader>
              <CardContent>
                {dashboard.team_members.length === 0 ? (
                  <p className="text-sm text-slate-500">No team members assigned.</p>
                ) : (
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {dashboard.team_members.map((member) => (
                      <div key={member.id} className="flex items-center gap-3 rounded-md border border-slate-200 p-3">
                        <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-xs font-medium text-slate-600">
                          {member.user_id.slice(0, 2).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{member.role}</p>
                          <p className="text-xs text-slate-500">
                            Load: {(member.current_load * 100).toFixed(0)}%
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Plans Tab */}
        <TabsContent value="plans" className="space-y-4">
          {/* Pending Approvals */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pending Approvals</CardTitle>
              <CardDescription>Plans waiting for your review.</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboard.pending_approvals.length === 0 ? (
                <p className="text-sm text-slate-500">No plans pending approval.</p>
              ) : (
                <div className="space-y-3">
                  {dashboard.pending_approvals.map((plan) => (
                    <div key={plan.id} className="rounded-md border border-slate-200 p-4 space-y-3">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-medium">Plan #{plan.id.slice(0, 8)}</p>
                          <p className="text-xs text-slate-500">
                            Created {formatDate(plan.created_at)}
                          </p>
                        </div>
                        <Badge variant="outline" className="bg-amber-50 text-amber-700">
                          {plan.status.replaceAll('_', ' ')}
                        </Badge>
                      </div>
                      
                      {typeof plan.plan_data.summary === 'string' && (
                        <p className="text-sm text-slate-600">{plan.plan_data.summary}</p>
                      )}

                      {rejectingPlanId === plan.id ? (
                        <form
                          className="space-y-2"
                          onSubmit={(e) => {
                            e.preventDefault()
                            if (!rejectionReason.trim()) return
                            rejectPlanMutation.mutate({ planId: plan.id, reason: rejectionReason })
                          }}
                        >
                          <Input
                            placeholder="Rejection reason..."
                            value={rejectionReason}
                            onChange={(e) => setRejectionReason(e.target.value)}
                          />
                          <div className="flex gap-2">
                            <Button type="submit" variant="destructive" size="sm" disabled={rejectPlanMutation.isPending}>
                              Confirm Reject
                            </Button>
                            <Button type="button" variant="outline" size="sm" onClick={() => setRejectingPlanId(null)}>
                              Cancel
                            </Button>
                          </div>
                        </form>
                      ) : (
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={() => approvePlanMutation.mutate(plan.id)}
                            disabled={approvePlanMutation.isPending}
                          >
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setRejectingPlanId(plan.id)}
                          >
                            Reject
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Plans */}
          {dashboard.recent_plans.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent Plans</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {dashboard.recent_plans.map((plan) => (
                    <div key={plan.id} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                      <span className="text-sm">Plan #{plan.id.slice(0, 8)}</span>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {plan.status.replaceAll('_', ' ')}
                        </Badge>
                        <span className="text-xs text-slate-500">
                          {formatDate(plan.approved_at ?? plan.updated_at ?? plan.created_at)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-4">
          {/* Current Agent Allowlist */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Agent Allowlist</CardTitle>
              <CardDescription>Agents currently allowed to work on this project.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {dashboard.allowed_agents.length === 0 ? (
                <p className="text-sm text-slate-500">No agents allowed yet. Add agents from your owned agents or the marketplace below.</p>
              ) : (
                <div className="space-y-2">
                  {dashboard.allowed_agents.map((entry) => (
                    <div key={entry.id} className="flex items-center justify-between rounded-md border border-slate-200 p-3">
                      <div>
                        <p className="font-medium text-sm">{entry.agent.name}</p>
                        <p className="text-xs text-slate-500">
                          {entry.agent.role} - Added {formatDate(entry.created_at)}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => removeAllowedAgentMutation.mutate(entry.agent_id)}
                        disabled={removeAllowedAgentMutation.isPending}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Add from Owned Agents */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Add from Your Agents</CardTitle>
              <CardDescription>Add agents you own to this project.</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="flex flex-wrap items-center gap-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (!selectedAgentId) return
                  addAllowedAgentMutation.mutate(selectedAgentId)
                }}
              >
                <select
                  className="h-9 flex-1 min-w-[200px] rounded-md border border-slate-300 bg-white px-3 text-sm"
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                >
                  <option value="">Select an agent...</option>
                  {candidateAgents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} ({agent.role})
                    </option>
                  ))}
                </select>
                <Button type="submit" disabled={!selectedAgentId || addAllowedAgentMutation.isPending}>
                  Add Agent
                </Button>
              </form>
              {agentsQuery.isLoading && (
                <p className="text-xs text-slate-400 mt-2">Loading your agents...</p>
              )}
              {!agentsQuery.isLoading && candidateAgents.length === 0 && (agentsQuery.data?.length ?? 0) === 0 && (
                <p className="text-xs text-slate-400 mt-2">You don't have any agents yet. Create agents or add from the marketplace below.</p>
              )}
              {!agentsQuery.isLoading && candidateAgents.length === 0 && (agentsQuery.data?.length ?? 0) > 0 && (
                <p className="text-xs text-slate-400 mt-2">All your agents are already in the allowlist.</p>
              )}
            </CardContent>
          </Card>

          {/* Add from Marketplace */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Add from Marketplace</CardTitle>
              <CardDescription>Browse and add agents from the marketplace to this project.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Category Filter */}
              <div className="flex flex-wrap items-center gap-2">
                <select
                  className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm"
                  value={marketplaceCategory}
                  onChange={(e) => setMarketplaceCategory(e.target.value)}
                >
                  <option value="">All Categories</option>
                  <option value="coder">Coder</option>
                  <option value="reviewer">Reviewer</option>
                  <option value="designer">Designer</option>
                  <option value="tester">Tester</option>
                  <option value="devops">DevOps</option>
                </select>
                {marketplaceQuery.isLoading && (
                  <span className="text-xs text-slate-500">Loading...</span>
                )}
              </div>

              {/* Marketplace Agent Grid */}
              {marketplaceQuery.isError ? (
                <p className="text-sm text-red-600">Failed to load marketplace agents.</p>
              ) : candidateMarketplaceAgents.length === 0 ? (
                <p className="text-sm text-slate-500">
                  {marketplaceQuery.isLoading
                    ? 'Loading marketplace agents...'
                    : 'No available marketplace agents found. All agents may already be in your allowlist.'}
                </p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {candidateMarketplaceAgents.map((agent: MarketplaceAgent) => (
                    <div
                      key={agent.id}
                      className="rounded-lg border border-slate-200 p-3 hover:border-slate-300 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{agent.name}</p>
                          <p className="text-xs text-slate-500">{agent.category}</p>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          {agent.is_verified && (
                            <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700">
                              Verified
                            </Badge>
                          )}
                          <Badge
                            variant="outline"
                            className={`text-xs ${
                              agent.pricing_type === 'free'
                                ? 'bg-green-50 text-green-700'
                                : 'bg-amber-50 text-amber-700'
                            }`}
                          >
                            {agent.pricing_type === 'free' ? 'Free' : `$${agent.price_per_use}/use`}
                          </Badge>
                        </div>
                      </div>
                      {agent.description && (
                        <p className="text-xs text-slate-600 mt-2 line-clamp-2">{agent.description}</p>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        className="mt-3 w-full"
                        disabled={addMarketplaceAgentMutation.isPending}
                        onClick={() => addMarketplaceAgentMutation.mutate(agent.agent_id)}
                      >
                        Add to Project
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

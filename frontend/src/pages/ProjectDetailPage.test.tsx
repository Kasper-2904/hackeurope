import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProjectDetailPage from '@/pages/ProjectDetailPage'
import {
  addProjectAllowedAgent,
  approvePlan,
  createPMTask,
  fetchPMDashboard,
  listOwnedAgents,
  rejectPlan,
  removeProjectAllowedAgent,
} from '@/lib/pmApi'
import { getProjectTasks } from '@/lib/api'
import { PlanStatus, type Agent, type PMDashboard } from '@/lib/types'

vi.mock('@/lib/pmApi', () => ({
  fetchPMDashboard: vi.fn(),
  listOwnedAgents: vi.fn(),
  addProjectAllowedAgent: vi.fn(),
  removeProjectAllowedAgent: vi.fn(),
  approvePlan: vi.fn(),
  rejectPlan: vi.fn(),
  createPMTask: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  getProjectTasks: vi.fn(),
  getTaskLogs: vi.fn().mockResolvedValue({ task_id: '', logs: [], has_more: false, last_sequence: 0 }),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/projects/proj-1']}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function makeDashboard(overrides: Partial<PMDashboard> = {}): PMDashboard {
  return {
    project_id: 'proj-1',
    project: {
      id: 'proj-1',
      name: 'Orchestrator MVP',
      description: 'PM dashboard scope',
      goals: ['Ship PM dashboard'],
      milestones: [],
      timeline: { start: '2026-02-01', end: '2026-02-28' },
      github_repo: null,
      owner_id: 'user-1',
      created_at: '2026-02-01T00:00:00Z',
      updated_at: null,
    },
    team_members: [],
    tasks_by_status: {},
    recent_plans: [],
    pending_approvals: [],
    open_risks: [],
    critical_alerts: [],
    allowed_agents: [],
    ...overrides,
  }
}

function makeOwnedAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: 'agent-1',
    name: 'Coder Agent',
    role: 'coder',
    description: 'Writes code',
    mcp_endpoint: 'http://localhost:8001',
    status: 'online',
    owner_id: 'user-1',
    team_id: null,
    created_at: '2026-02-21T10:00:00Z',
    last_seen: null,
    ...overrides,
  }
}

describe('ProjectDetailPage', () => {
  const mockedFetchPMDashboard = vi.mocked(fetchPMDashboard)
  const mockedListOwnedAgents = vi.mocked(listOwnedAgents)
  const mockedGetProjectTasks = vi.mocked(getProjectTasks)
  const mockedAddProjectAllowedAgent = vi.mocked(addProjectAllowedAgent)
  const mockedRemoveProjectAllowedAgent = vi.mocked(removeProjectAllowedAgent)
  const mockedApprovePlan = vi.mocked(approvePlan)
  const mockedRejectPlan = vi.mocked(rejectPlan)
  const mockedCreatePMTask = vi.mocked(createPMTask)

  beforeEach(() => {
    vi.clearAllMocks()
    mockedGetProjectTasks.mockResolvedValue([])
    mockedAddProjectAllowedAgent.mockResolvedValue({} as never)
    mockedRemoveProjectAllowedAgent.mockResolvedValue(undefined)
    mockedApprovePlan.mockResolvedValue({} as never)
    mockedRejectPlan.mockResolvedValue({
      id: 'plan-1',
      task_id: 'task-1',
      project_id: 'proj-1',
      status: PlanStatus.REJECTED,
      plan_data: {},
      approved_by_id: null,
      approved_at: null,
      rejection_reason: 'Missing acceptance criteria',
      version: 1,
      created_at: '2026-02-21T10:00:00Z',
      updated_at: '2026-02-21T11:00:00Z',
    })
    mockedCreatePMTask.mockResolvedValue({
      id: 'task-1',
      title: 'New PM Task',
      description: null,
      task_type: 'bug_fix',
      status: 'pending',
      progress: 0,
      assigned_agent_id: null,
      team_id: 'proj-1',
      created_at: '2026-02-21T11:00:00Z',
      started_at: null,
      completed_at: null,
    })
  })

  it('renders loading state while dashboard query is pending', () => {
    mockedFetchPMDashboard.mockImplementation(() => new Promise(() => {}))
    mockedListOwnedAgents.mockResolvedValue([])

    renderPage()

    expect(screen.getByText('Loading project...')).toBeInTheDocument()
  })

  it('renders dashboard fetch error state', async () => {
    mockedFetchPMDashboard.mockRejectedValue(new Error('network down'))
    mockedListOwnedAgents.mockResolvedValue([])

    renderPage()

    expect(await screen.findByText('Failed to load project.')).toBeInTheDocument()
  })

  it.skip('renders success state with empty approvals and allowlist', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(makeDashboard())
    mockedListOwnedAgents.mockResolvedValue([])

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Orchestrator MVP' })).toBeInTheDocument()

    // Switch to Plans tab
    await user.click(screen.getByRole('tab', { name: 'Plans' }))
    await waitFor(() => {
      expect(screen.getByText('No plans pending approval.')).toBeInTheDocument()
    })

    // Switch to Settings tab
    await user.click(screen.getByRole('tab', { name: 'Settings' }))
    // Use findByText which has built-in waiting
    expect(await screen.findByText('No agents allowed yet.', {}, { timeout: 5000 })).toBeInTheDocument()
  })

  it('adds an agent from owned-agents list to project allowlist', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(makeDashboard())
    mockedListOwnedAgents.mockResolvedValue([makeOwnedAgent()])

    renderPage()

    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    // Switch to Settings tab
    await user.click(screen.getByRole('tab', { name: 'Settings' }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('Select an agent...')).toBeInTheDocument()
    })

    await user.selectOptions(screen.getByDisplayValue('Select an agent...'), 'agent-1')
    await user.click(screen.getByRole('button', { name: 'Add Agent' }))

    await waitFor(() => {
      expect(mockedAddProjectAllowedAgent).toHaveBeenCalledWith('proj-1', 'agent-1')
    })
  })

  it('removes an existing allowlisted agent', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(
      makeDashboard({
        allowed_agents: [
          {
            id: 'allow-1',
            project_id: 'proj-1',
            agent_id: 'agent-1',
            added_by_id: 'user-1',
            created_at: '2026-02-21T10:00:00Z',
            agent: makeOwnedAgent(),
          },
        ],
      }),
    )
    mockedListOwnedAgents.mockResolvedValue([makeOwnedAgent()])

    renderPage()

    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    // Switch to Settings tab
    await user.click(screen.getByRole('tab', { name: 'Settings' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Remove' }))

    await waitFor(() => {
      expect(mockedRemoveProjectAllowedAgent).toHaveBeenCalledWith('proj-1', 'agent-1')
    })
  })

  it('approves a pending plan', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(
      makeDashboard({
        pending_approvals: [
          {
            id: 'plan-1',
            task_id: 'task-1',
            project_id: 'proj-1',
            status: PlanStatus.PENDING_PM_APPROVAL,
            plan_data: { summary: 'Add approval gate UX' },
            approved_by_id: null,
            approved_at: null,
            rejection_reason: null,
            version: 1,
            created_at: '2026-02-21T10:00:00Z',
            updated_at: null,
          },
        ],
      }),
    )
    mockedListOwnedAgents.mockResolvedValue([])

    renderPage()

    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    // Switch to Plans tab
    await user.click(screen.getByRole('tab', { name: 'Plans' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Approve' }))

    await waitFor(() => {
      expect(mockedApprovePlan).toHaveBeenCalledWith('plan-1')
    })
  })

  it('submits reject flow with a reason', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(
      makeDashboard({
        pending_approvals: [
          {
            id: 'plan-1',
            task_id: 'task-1',
            project_id: 'proj-1',
            status: PlanStatus.PENDING_PM_APPROVAL,
            plan_data: { summary: 'Add approval gate UX' },
            approved_by_id: null,
            approved_at: null,
            rejection_reason: null,
            version: 1,
            created_at: '2026-02-21T10:00:00Z',
            updated_at: null,
          },
        ],
      }),
    )
    mockedListOwnedAgents.mockResolvedValue([])

    renderPage()

    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    // Switch to Plans tab
    await user.click(screen.getByRole('tab', { name: 'Plans' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument()
    })

    // Click Reject to open the rejection form
    await user.click(screen.getByRole('button', { name: 'Reject' }))

    // Fill in the rejection reason and submit
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Rejection reason...')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Rejection reason...'), 'Missing acceptance criteria')
    await user.click(screen.getByRole('button', { name: 'Confirm Reject' }))

    await waitFor(() => {
      expect(mockedRejectPlan).toHaveBeenCalledWith('plan-1', 'Missing acceptance criteria')
    })
  })

  it('creates a PM task from project tasks tab', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(makeDashboard())
    mockedListOwnedAgents.mockResolvedValue([])

    renderPage()
    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    await user.type(screen.getByPlaceholderText('Task title'), 'Fix flaky tests')
    await user.selectOptions(screen.getByDisplayValue('Code Generation'), 'bug_fix')
    await user.type(screen.getByPlaceholderText('Description (optional)'), 'Investigate and fix CI flakes')
    await user.click(screen.getByRole('button', { name: 'Create Task' }))

    await waitFor(() => {
      expect(mockedCreatePMTask).toHaveBeenCalledWith({
        title: 'Fix flaky tests',
        task_type: 'bug_fix',
        description: 'Investigate and fix CI flakes',
        project_id: 'proj-1',
      })
    })
  })

  it('shows success feedback and refreshes task board after PM task creation', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(makeDashboard())
    mockedListOwnedAgents.mockResolvedValue([])

    renderPage()
    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    await user.type(screen.getByPlaceholderText('Task title'), 'New onboarding task')
    await user.click(screen.getByRole('button', { name: 'Create Task' }))

    expect(await screen.findByText('Task created successfully.')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockedGetProjectTasks.mock.calls.length).toBeGreaterThanOrEqual(2)
    })
  })

  it('keeps create button disabled while task creation is in-flight', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(makeDashboard())
    mockedListOwnedAgents.mockResolvedValue([])
    mockedCreatePMTask.mockImplementation(() => new Promise(() => {}))

    renderPage()
    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    await user.type(screen.getByPlaceholderText('Task title'), 'Long running task')
    await user.click(screen.getByRole('button', { name: 'Create Task' }))

    expect(screen.getByRole('button', { name: 'Creating...' })).toBeDisabled()
    expect(screen.getByPlaceholderText('Task title')).toBeDisabled()
    expect(screen.getByPlaceholderText('Description (optional)')).toBeDisabled()
  })

  it('prevents create request when title is missing', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(makeDashboard())
    mockedListOwnedAgents.mockResolvedValue([])

    renderPage()
    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    await user.click(screen.getByRole('button', { name: 'Create Task' }))

    expect(mockedCreatePMTask).not.toHaveBeenCalled()
  })

  it('shows friendly validation message for backend 422 response', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(makeDashboard())
    mockedListOwnedAgents.mockResolvedValue([])
    const unprocessableError = new AxiosError('Unprocessable Entity')
    unprocessableError.response = {
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: {},
      config: {} as never,
      data: { detail: 'validation error' },
    }
    mockedCreatePMTask.mockRejectedValue(unprocessableError)

    renderPage()
    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    await user.type(screen.getByPlaceholderText('Task title'), 'Invalid task payload')
    await user.click(screen.getByRole('button', { name: 'Create Task' }))

    expect(
      await screen.findByText('Please check required fields and task type before submitting.'),
    ).toBeInTheDocument()
  })

  it('shows friendly permission error when task creation is forbidden', async () => {
    const user = userEvent.setup()
    mockedFetchPMDashboard.mockResolvedValue(makeDashboard())
    mockedListOwnedAgents.mockResolvedValue([])
    const forbiddenError = new AxiosError('Forbidden')
    forbiddenError.response = {
      status: 403,
      statusText: 'Forbidden',
      headers: {},
      config: {} as never,
      data: { detail: 'Only PM or Admin can perform this action' },
    }
    mockedCreatePMTask.mockRejectedValue(forbiddenError)

    renderPage()
    await screen.findByRole('heading', { name: 'Orchestrator MVP' })

    await user.type(screen.getByPlaceholderText('Task title'), 'Unauthorized create')
    await user.click(screen.getByRole('button', { name: 'Create Task' }))

    expect(
      await screen.findByText('You do not have permission to create tasks for this project.'),
    ).toBeInTheDocument()
    expect(screen.getByText('No tasks yet')).toBeInTheDocument()
  })
})

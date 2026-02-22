import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import TaskDetailPage from "./TaskDetailPage";
import {
  getTask,
  getSubtasks,
  getRiskSignals,
  getPlans,
  getProject,
  getTeamMembers,
  getTasks,
  getTaskReasoningLogs,
  subscribeTaskReasoningLogs,
} from "@/lib/api";
import type { Task, Plan, TaskReasoningLog, TaskReasoningLogStreamEvent } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getTask: vi.fn(),
  getSubtasks: vi.fn(),
  getRiskSignals: vi.fn(),
  getPlans: vi.fn(),
  getProject: vi.fn(),
  getTeamMembers: vi.fn(),
  getTasks: vi.fn(),
  getTaskReasoningLogs: vi.fn(),
  subscribeTaskReasoningLogs: vi.fn(() => vi.fn()),
  getTaskLogs: vi.fn().mockResolvedValue({ task_id: "", logs: [], has_more: false, last_sequence: 0 }),
}));

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsList: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsTrigger: ({ children }: { children: ReactNode }) => <button role="tab">{children}</button>,
  TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const mockTask: Task = {
  id: "task-2",
  title: "Build GitHub ingestion adapter",
  description: "Pull PRs, issues, commits from GitHub API",
  task_type: "feature",
  status: "in_progress",
  progress: 0.4,
  assigned_agent_id: "agent-1",
  team_id: null,
  created_at: "2025-06-11T10:00:00Z",
  started_at: "2025-06-12T08:00:00Z",
  completed_at: null,
};

const mockPlan: Plan = {
  id: "plan-1",
  task_id: "task-2",
  project_id: "proj-1",
  status: "approved",
  plan_data: { summary: "Build GitHub ingestion in 3 subtasks" },
  approved_by_id: "user-2",
  approved_at: "2025-06-12T07:30:00Z",
  rejection_reason: null,
  version: 1,
  created_at: "2025-06-11T16:00:00Z",
  updated_at: null,
};

function renderWithProviders(taskId: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/tasks/${taskId}`]}>
        <Routes>
          <Route path="/tasks/:id" element={<TaskDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("TaskDetailPage", () => {
  const mockedGetTask = vi.mocked(getTask);
  const mockedGetSubtasks = vi.mocked(getSubtasks);
  const mockedGetRiskSignals = vi.mocked(getRiskSignals);
  const mockedGetPlans = vi.mocked(getPlans);
  const mockedGetProject = vi.mocked(getProject);
  const mockedGetTeamMembers = vi.mocked(getTeamMembers);
  const mockedGetTasks = vi.mocked(getTasks);
  const mockedGetTaskReasoningLogs = vi.mocked(getTaskReasoningLogs);
  const mockedSubscribeTaskReasoningLogs = vi.mocked(subscribeTaskReasoningLogs);
  let streamCallbacks: {
    onOpen?: () => void;
    onEvent: (event: TaskReasoningLogStreamEvent) => void;
    onError?: (error: Error) => void;
    onClose?: () => void;
  } | null = null;

  beforeEach(() => {
    vi.clearAllMocks();
    streamCallbacks = null;
    mockedGetTask.mockResolvedValue(mockTask);
    mockedGetSubtasks.mockResolvedValue([]);
    mockedGetRiskSignals.mockResolvedValue([]);
    mockedGetPlans.mockResolvedValue([mockPlan]);
    mockedGetProject.mockResolvedValue(null as unknown as undefined);
    mockedGetTeamMembers.mockResolvedValue([]);
    mockedGetTasks.mockResolvedValue([]);
    mockedGetTaskReasoningLogs.mockResolvedValue([]);
    mockedSubscribeTaskReasoningLogs.mockImplementation((_taskId, callbacks) => {
      streamCallbacks = callbacks;
      callbacks.onOpen?.();
      return () => {};
    });
  });

  it("shows loading state initially", () => {
    mockedGetTask.mockImplementation(() => new Promise(() => {}));
    renderWithProviders("task-2");
    expect(screen.getByText("Loading task...")).toBeInTheDocument();
  });

  it("renders task title after loading", async () => {
    renderWithProviders("task-2");
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Build GitHub ingestion adapter" })).toBeInTheDocument();
    });
  });

  it("renders tab buttons", async () => {
    renderWithProviders("task-2");
    await waitFor(() => {
      expect(screen.getByText("Overview")).toBeInTheDocument();
    });
    expect(screen.getByRole("tab", { name: /Draft/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Subtasks/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Risks/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Reasoning/ })).toBeInTheDocument();
  });

  it("shows not found for invalid task", async () => {
    mockedGetTask.mockResolvedValue(null);
    renderWithProviders("nonexistent");
    await waitFor(() => {
      expect(screen.getByText("Task not found")).toBeInTheDocument();
    });
  });

  it("renders the View Context button", async () => {
    renderWithProviders("task-2");
    await waitFor(() => {
      expect(screen.getByText("View Context")).toBeInTheDocument();
    });
  });

  it("shows status badge for task", async () => {
    renderWithProviders("task-2");
    await waitFor(() => {
      expect(screen.getAllByText("In Progress").length).toBeGreaterThan(0);
    });
  });

  it("renders initial reasoning history and appends streamed entries in order", async () => {
    const initialLogs: TaskReasoningLog[] = [
      {
        id: "log-2",
        task_id: "task-2",
        subtask_id: null,
        event_type: "task.progress",
        message: "Step 2 complete",
        status: "in_progress",
        sequence: 2,
        payload: {},
        source: "orchestrator",
        created_at: "2026-02-22T12:00:02Z",
      },
      {
        id: "log-1",
        task_id: "task-2",
        subtask_id: null,
        event_type: "task.started",
        message: "Task started",
        status: "in_progress",
        sequence: 1,
        payload: {},
        source: "orchestrator",
        created_at: "2026-02-22T12:00:01Z",
      },
    ];
    mockedGetTaskReasoningLogs.mockResolvedValue(initialLogs);

    renderWithProviders("task-2");
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Reasoning \(2\)/ })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("Task started")).toBeInTheDocument();
      expect(screen.getByText("Step 2 complete")).toBeInTheDocument();
    });

    expect(screen.getAllByText("in progress").length).toBeGreaterThan(0);

    await act(async () => {
      streamCallbacks?.onEvent({
        event: "reasoning_log.created",
        log: {
          id: "log-3",
          task_id: "task-2",
          subtask_id: null,
          event_type: "task.completed",
          message: "Task completed",
          status: "completed",
          sequence: 3,
          payload: {},
          source: "orchestrator",
          created_at: "2026-02-22T12:00:03Z",
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Task completed")).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /Reasoning \(3\)/ })).toBeInTheDocument();
    });

    expect(screen.getByText("completed")).toBeInTheDocument();
    const renderedSequenceBadges = screen.getAllByText(/^#\d+$/).map((el) => el.textContent);
    expect(renderedSequenceBadges).toEqual(["#1", "#2", "#3"]);
  });

  it("shows non-blocking stream disconnect warning and keeps loaded logs", async () => {
    mockedGetTaskReasoningLogs.mockResolvedValue([
      {
        id: "log-1",
        task_id: "task-2",
        subtask_id: null,
        event_type: "task.started",
        message: "Task started",
        status: "in_progress",
        sequence: 1,
        payload: {},
        source: "orchestrator",
        created_at: "2026-02-22T12:00:01Z",
      },
    ]);

    renderWithProviders("task-2");
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Reasoning \(1\)/ })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("Task started")).toBeInTheDocument();
    });

    await act(async () => {
      streamCallbacks?.onError?.(new Error("network down"));
    });

    await waitFor(() => {
      expect(screen.getByText(/Live updates disconnected\. Reconnecting\.\.\./)).toBeInTheDocument();
      expect(screen.getByText(/Current stream state: disconnected\./)).toBeInTheDocument();
    });
    expect(screen.getByText("Task started")).toBeInTheDocument();
  });

  it("renders empty reasoning timeline message when no events exist", async () => {
    mockedGetTaskReasoningLogs.mockResolvedValue([]);

    renderWithProviders("task-2");
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Reasoning/ })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("No reasoning logs yet")).toBeInTheDocument();
      expect(
        screen.getByText("Logs will appear here when task orchestration starts."),
      ).toBeInTheDocument();
    });
  });

  it("deduplicates reasoning events that appear in both snapshot and stream", async () => {
    mockedGetTaskReasoningLogs.mockResolvedValue([
      {
        id: "log-1",
        task_id: "task-2",
        subtask_id: null,
        event_type: "task.started",
        message: "Task started",
        status: "in_progress",
        sequence: 1,
        payload: {},
        source: "orchestrator",
        created_at: "2026-02-22T12:00:01Z",
      },
    ]);

    renderWithProviders("task-2");
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Reasoning \(1\)/ })).toBeInTheDocument();
    });
    await act(async () => {
      streamCallbacks?.onEvent({
        event: "reasoning_log.created",
        log: {
          id: "log-1",
          task_id: "task-2",
          subtask_id: null,
          event_type: "task.started",
          message: "Task started",
          status: "in_progress",
          sequence: 1,
          payload: {},
          source: "orchestrator",
          created_at: "2026-02-22T12:00:01Z",
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Task started")).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /Reasoning \(1\)/ })).toBeInTheDocument();
    });
    expect(screen.getAllByText("Task started")).toHaveLength(1);
  });
});

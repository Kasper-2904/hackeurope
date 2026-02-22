// React Query hooks — each hook fetches data from the real API
// and caches it so components don't re-fetch on every render.
//
// How it works:
// - useQuery takes a "key" (like a cache label) and a function to fetch data
// - It returns { data, isLoading, error } that components can use

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  cancelTask,
  getAgent,
  getAgents,
  getMarketplaceAgent,
  getMarketplaceCatalog,
  getPlans,
  getProject,
  getTaskReasoningLogs,
  getReviewerFindings,
  getRiskSignals,
  getSubtasks,
  getTask,
  getTaskLogs,
  getTasks,
  subscribeTaskReasoningLogs,
  getTeamMembers,
  publishAgent,
} from "@/lib/api";
import type { TaskLog, TaskReasoningLog, TaskReasoningLogStreamEvent } from "@/lib/types";

export function useTasks() {
  return useQuery({ queryKey: ["tasks"], queryFn: getTasks });
}

export function useTask(id: string) {
  return useQuery({
    queryKey: ["task", id],
    queryFn: () => getTask(id),
    enabled: !!id,
  });
}

function sortReasoningLogs(logs: TaskReasoningLog[]): TaskReasoningLog[] {
  return [...logs].sort((a, b) => {
    if (a.sequence !== b.sequence) {
      return a.sequence - b.sequence;
    }
    if (a.created_at !== b.created_at) {
      return a.created_at.localeCompare(b.created_at);
    }
    return a.id.localeCompare(b.id);
  });
}

function upsertReasoningLog(
  existing: TaskReasoningLog[],
  incoming: TaskReasoningLog,
): TaskReasoningLog[] {
  const byId = new Map(existing.map((log) => [log.id, log]));
  byId.set(incoming.id, incoming);
  return sortReasoningLogs(Array.from(byId.values()));
}

export function useTaskReasoningLogs(taskId: string) {
  const [liveLogs, setLiveLogs] = useState<TaskReasoningLog[]>([]);
  const [streamState, setStreamState] = useState<"connecting" | "connected" | "disconnected">(
    "connecting",
  );
  const [streamWarning, setStreamWarning] = useState<string | null>(null);

  const historyQuery = useQuery({
    queryKey: ["taskReasoningLogs", taskId],
    queryFn: () => getTaskReasoningLogs(taskId),
    enabled: Boolean(taskId),
  });
  const historyLogs = useMemo(
    () => sortReasoningLogs(historyQuery.data ?? []),
    [historyQuery.data],
  );

  useEffect(() => {
    if (!taskId) {
      return;
    }

    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let stopStream: (() => void) | null = null;
    let attempts = 0;
    let isDisposed = false;

    const connect = () => {
      if (isDisposed) return;
      setStreamState("connecting");

      stopStream = subscribeTaskReasoningLogs(taskId, {
        onOpen: () => {
          attempts = 0;
          setStreamState("connected");
          setStreamWarning(null);
        },
        onEvent: (event: TaskReasoningLogStreamEvent) => {
          if (!event.log) return;
          setLiveLogs((previous) => upsertReasoningLog(previous, event.log));
        },
        onError: () => {
          if (isDisposed) return;
          setStreamState("disconnected");
          setStreamWarning("Live updates disconnected. Reconnecting...");
          attempts += 1;
          const retryDelayMs = Math.min(1000 * 2 ** Math.min(attempts, 4), 15000);
          reconnectTimer = setTimeout(connect, retryDelayMs);
        },
      });
    };

    connect();

    return () => {
      isDisposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      stopStream?.();
    };
  }, [taskId]);

  const mergedLogs = useMemo(() => {
    const byId = new Map<string, TaskReasoningLog>();
    for (const log of historyLogs) {
      byId.set(log.id, log);
    }
    for (const log of liveLogs) {
      byId.set(log.id, log);
    }
    return sortReasoningLogs(Array.from(byId.values()));
  }, [historyLogs, liveLogs]);

  return {
    logs: mergedLogs,
    isLoading: historyQuery.isLoading,
    isError: historyQuery.isError,
    error: historyQuery.error,
    streamState,
    streamWarning,
  };
}

export function useSubtasks(taskId: string) {
  return useQuery({
    queryKey: ["subtasks", taskId],
    queryFn: () => getSubtasks(taskId),
    enabled: !!taskId,
  });
}

export function useRiskSignals(taskId?: string) {
  return useQuery({
    queryKey: ["risks", taskId],
    queryFn: () => getRiskSignals(taskId!),
    enabled: !!taskId,
  });
}

export function usePlans(taskId?: string) {
  return useQuery({
    queryKey: ["plans", taskId],
    queryFn: () => getPlans(taskId),
  });
}

export function useProject(id: string | undefined) {
  return useQuery({
    queryKey: ["project", id],
    queryFn: async () => {
      if (!id) return null;
      const result = await getProject(id);
      return result ?? null;
    },
    enabled: !!id,
  });
}

export function useTeamMembers(projectId: string) {
  return useQuery({
    queryKey: ["teamMembers", projectId],
    queryFn: () => getTeamMembers(projectId),
    enabled: !!projectId,
  });
}

export function useAgents() {
  return useQuery({ queryKey: ["agents"], queryFn: getAgents });
}

export function useAgent(id: string) {
  return useQuery({
    queryKey: ["agent", id],
    queryFn: () => getAgent(id),
    enabled: !!id,
  });
}

export function useMarketplaceCatalog(category?: string) {
  return useQuery({
    queryKey: ["marketplace", category],
    queryFn: () => getMarketplaceCatalog(category),
  });
}

export function useMarketplaceAgent(id: string) {
  return useQuery({
    queryKey: ["marketplaceAgent", id],
    queryFn: () => getMarketplaceAgent(id),
    enabled: !!id,
  });
}

export function useReviewerFindings(projectId: string) {
  return useQuery({
    queryKey: ["reviewerFindings", projectId],
    queryFn: () => getReviewerFindings(projectId),
    enabled: !!projectId,
  });
}

export function usePublishAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: publishAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["marketplace"] });
    },
  });
}

export function useCancelTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task"] });
    },
  });
}

// Store for polling state - used with useSyncExternalStore
const pollingStore = {
  _states: new Map<string, boolean>(),
  _listeners: new Set<() => void>(),
  
  set(taskId: string, value: boolean) {
    if (this._states.get(taskId) !== value) {
      this._states.set(taskId, value);
      this._emit();
    }
  },
  
  get(taskId: string): boolean {
    return this._states.get(taskId) ?? false;
  },
  
  subscribe(listener: () => void) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  },
  
  _emit() {
    this._listeners.forEach((l) => l());
  },
};

// Store for logs - used with useSyncExternalStore
const logsStore = {
  _logs: new Map<string, TaskLog[]>(),
  _listeners: new Set<() => void>(),
  _sequences: new Map<string, number>(),
  
  getLogs(taskId: string): TaskLog[] {
    return this._logs.get(taskId) ?? [];
  },
  
  getSequence(taskId: string): number {
    return this._sequences.get(taskId) ?? 0;
  },
  
  clear(taskId: string) {
    this._logs.set(taskId, []);
    this._sequences.set(taskId, 0);
    this._emit();
  },
  
  append(taskId: string, logs: TaskLog[], lastSequence: number) {
    const current = this._logs.get(taskId) ?? [];
    this._logs.set(taskId, [...current, ...logs]);
    this._sequences.set(taskId, lastSequence);
    this._emit();
  },
  
  subscribe(listener: () => void) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  },
  
  _emit() {
    this._listeners.forEach((l) => l());
  },
};

/**
 * Hook for polling task logs in real-time.
 * Automatically polls when task is in progress.
 */
export function useTaskLogs(
  taskId: string | undefined,
  taskStatus: string | undefined,
  pollInterval: number = 2000
) {
  const isTaskActive = taskStatus === "in_progress" || taskStatus === "assigned";
  
  // Subscribe to external stores to avoid state-in-render issues
  const logs = useSyncExternalStore(
    (cb) => logsStore.subscribe(cb),
    () => (taskId ? logsStore.getLogs(taskId) : [])
  );
  
  const isPolling = useSyncExternalStore(
    (cb) => pollingStore.subscribe(cb),
    () => (taskId ? pollingStore.get(taskId) : false)
  );

  // Refs for internal tracking (not accessed during render)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevTaskIdRef = useRef<string | null>(null);
  const fetchLogsRef = useRef<(() => void) | null>(null);

  // Create fetch function
  const createFetchLogs = useCallback(() => {
    if (!taskId) return;

    const sequence = logsStore.getSequence(taskId);
    getTaskLogs(taskId, sequence)
      .then((response) => {
        if (response.logs.length > 0) {
          logsStore.append(taskId, response.logs, response.last_sequence);
        }
      })
      .catch((error) => {
        console.error("Failed to fetch task logs:", error);
      });
  }, [taskId]);

  // Update fetch ref
  fetchLogsRef.current = createFetchLogs;

  // Initialize on taskId change - runs after render via setImmediate
  if (taskId && prevTaskIdRef.current !== taskId) {
    prevTaskIdRef.current = taskId;
    logsStore.clear(taskId);
    // Defer execution to avoid synchronous setState
    setTimeout(() => {
      fetchLogsRef.current?.();
    }, 0);
  }

  // Manage polling interval
  const shouldPoll = isTaskActive && taskId;
  const isCurrentlyPolling = intervalRef.current !== null;

  if (shouldPoll && !isCurrentlyPolling && taskId) {
    pollingStore.set(taskId, true);
    intervalRef.current = setInterval(() => {
      fetchLogsRef.current?.();
    }, pollInterval);
  } else if (!shouldPoll && isCurrentlyPolling) {
    if (taskId) pollingStore.set(taskId, false);
    clearInterval(intervalRef.current!);
    intervalRef.current = null;
  }

  // Cleanup function
  const cleanup = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  const prevCleanupRef = useRef<(() => void) | null>(null);
  if (prevCleanupRef.current !== cleanup) {
    prevCleanupRef.current?.();
    prevCleanupRef.current = cleanup;
  }

  const refresh = useCallback(() => {
    fetchLogsRef.current?.();
  }, []);

  return { logs, isPolling, refresh };
}

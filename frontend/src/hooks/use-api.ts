// React Query hooks — each hook fetches data from the mock API
// and caches it so components don't re-fetch on every render.
//
// How it works:
// - useQuery takes a "key" (like a cache label) and a function to fetch data
// - It returns { data, isLoading, error } that components can use
// - When the real backend is ready, we just change the fetch functions

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAgent,
  getAgents,
  getMarketplaceAgent,
  getMarketplaceCatalog,
  getPlans,
  getProject,
  getRiskSignals,
  getSubtasks,
  getTask,
  getTasks,
  getTeamMembers,
  publishAgent,
} from "@/mocks/api";

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
    queryFn: () => getRiskSignals(taskId),
  });
}

export function usePlans(taskId?: string) {
  return useQuery({
    queryKey: ["plans", taskId],
    queryFn: () => getPlans(taskId),
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ["project", id],
    queryFn: () => getProject(id),
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

export function usePublishAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: publishAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["marketplace"] });
    },
  });
}

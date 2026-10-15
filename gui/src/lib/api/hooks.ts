"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, json, patch } from "./client";
import type {
  AgentRun,
  AnalysisResult,
  Brief,
  OpenItem,
  Priority,
  ProjectSummary,
  Requirement,
  RequirementChanges,
  RequirementDetail,
  RequirementType,
} from "./types";

const enc = encodeURIComponent;

export const keys = {
  projects: ["projects"] as const,
  project: (name: string) => ["project", name] as const,
  briefs: (name: string) => ["project", name, "briefs"] as const,
  requirements: (name: string) => ["project", name, "requirements"] as const,
  requirement: (name: string, key: string) => ["project", name, "requirement", key] as const,
  openItems: (name: string, includeClosed: boolean) =>
    ["project", name, "open-items", includeClosed] as const,
  runs: (name: string) => ["project", name, "runs"] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ status: string; version: string }>("/api/health"),
    refetchInterval: 15_000,
    retry: false,
  });
}

export function useProjects() {
  return useQuery({ queryKey: keys.projects, queryFn: () => api<ProjectSummary[]>("/api/projects") });
}

export function useProject(name: string) {
  return useQuery({
    queryKey: keys.project(name),
    queryFn: () => api<ProjectSummary>(`/api/projects/${enc(name)}`),
    // While an analysis runs (possibly started from another tab), poll so the
    // page notices when it finishes.
    refetchInterval: (query) => (query.state.data?.analysis_running ? 3_000 : false),
  });
}

export function useBriefs(name: string) {
  return useQuery({
    queryKey: keys.briefs(name),
    queryFn: () => api<Brief[]>(`/api/projects/${enc(name)}/briefs`),
  });
}

export function useRequirements(name: string) {
  return useQuery({
    queryKey: keys.requirements(name),
    queryFn: () => api<Requirement[]>(`/api/projects/${enc(name)}/requirements`),
  });
}

export function useRequirement(name: string, key: string) {
  return useQuery({
    queryKey: keys.requirement(name, key),
    queryFn: () => api<RequirementDetail>(`/api/projects/${enc(name)}/requirements/${enc(key)}`),
  });
}

export function useOpenItems(name: string, includeClosed: boolean) {
  return useQuery({
    queryKey: keys.openItems(name, includeClosed),
    queryFn: () =>
      api<OpenItem[]>(`/api/projects/${enc(name)}/open-items?include_closed=${includeClosed}`),
  });
}

export function useRuns(name: string) {
  return useQuery({
    queryKey: keys.runs(name),
    queryFn: () => api<AgentRun[]>(`/api/projects/${enc(name)}/runs`),
  });
}

/** Everything under one project is refreshed after any write to it. */
function useInvalidateProject(name: string) {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["project", name] }),
      qc.invalidateQueries({ queryKey: keys.projects }),
    ]);
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; root_path: string; description: string }) =>
      api<ProjectSummary>("/api/projects", json(body)),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
  });
}

export function useAddBrief(name: string) {
  const invalidate = useInvalidateProject(name);
  return useMutation({
    mutationFn: (body: { content: string; source_name: string | null }) =>
      api<Brief>(`/api/projects/${enc(name)}/briefs`, json(body)),
    onSuccess: invalidate,
  });
}

export function useRunAnalysis(name: string) {
  const invalidate = useInvalidateProject(name);
  return useMutation({
    mutationFn: (body: { max_budget_usd: number; model: string | null }) =>
      api<AnalysisResult>(`/api/projects/${enc(name)}/analysis`, json(body)),
    // A failed run is still recorded (and costs money), so refresh either way.
    onSettled: invalidate,
  });
}

export function useAddRequirement(name: string) {
  const invalidate = useInvalidateProject(name);
  return useMutation({
    mutationFn: (body: {
      title: string;
      description: string;
      requirement_type: RequirementType;
      priority: Priority;
      acceptance_criteria: string[];
    }) => api<Requirement>(`/api/projects/${enc(name)}/requirements`, json(body)),
    onSuccess: invalidate,
  });
}

export function useUpdateRequirement(name: string, key: string) {
  const invalidate = useInvalidateProject(name);
  return useMutation({
    mutationFn: (changes: RequirementChanges) =>
      api<Requirement>(`/api/projects/${enc(name)}/requirements/${enc(key)}`, patch(changes)),
    onSuccess: invalidate,
  });
}

export function useResolveOpenItem(name: string) {
  const invalidate = useInvalidateProject(name);
  return useMutation({
    mutationFn: ({ key, ...body }: { key: string; resolution: string; dismiss: boolean }) =>
      api<OpenItem>(`/api/projects/${enc(name)}/open-items/${enc(key)}/resolve`, json(body)),
    onSuccess: invalidate,
  });
}

import type { HistoryEntry, PipelineSpec, Stage, StageResult } from '../types/pipeline';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function listPipelines(): Promise<HistoryEntry[]> {
  const res = await fetch(`${API_BASE}/pipelines`);
  if (!res.ok) return [];
  return res.json();
}

export async function createPipeline(
  repoUrl: string,
  goal: string,
  useDocker: boolean = false,
  name: string = '',
): Promise<PipelineSpec> {
  const params = new URLSearchParams({ repo_url: repoUrl, goal });
  if (useDocker) params.set('use_docker', 'true');
  if (name) params.set('name', name);
  const res = await fetch(`${API_BASE}/pipelines?${params}`, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to create pipeline: ${res.statusText}`);
  }
  return res.json();
}

export async function executePipeline(pipelineId: string): Promise<Record<string, StageResult>> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/execute`, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to execute pipeline: ${res.statusText}`);
  }
  return res.json();
}

export async function getPipeline(pipelineId: string): Promise<PipelineSpec> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}`);
  if (!res.ok) throw new Error('Pipeline not found');
  return res.json();
}

export async function getResults(pipelineId: string): Promise<Record<string, StageResult>> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/results`);
  if (!res.ok) throw new Error('Results not found');
  return res.json();
}

export async function updatePipeline(
  pipelineId: string,
  update: { name?: string; goal?: string; stages?: Stage[] },
): Promise<PipelineSpec> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to update pipeline: ${res.statusText}`);
  }
  return res.json();
}

export async function deletePipeline(pipelineId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}`, { method: 'DELETE' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to delete pipeline: ${res.statusText}`);
  }
}

export function createWebSocketUrl(pipelineId: string): string {
  const apiBase = import.meta.env.VITE_API_BASE_URL || '';
  if (apiBase) {
    // Production: use backend URL
    const url = new URL(apiBase);
    const proto = url.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${url.host}/ws/${pipelineId}`;
  }
  // Development: use current host
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/ws/${pipelineId}`;
}

export async function executeFailedStages(pipelineId: string): Promise<Record<string, StageResult>> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/execute-failed`, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to re-run failed stages: ${res.statusText}`);
  }
  return res.json();
}

export async function chainPipelines(pipelineId: string, pipelineIds: string[]): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/chain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pipeline_ids: pipelineIds }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to chain pipelines: ${res.statusText}`);
  }
  return res.json();
}

// Named export for convenience
export const apiClient = {
  listPipelines,
  createPipeline,
  executePipeline,
  executeFailedStages,
  chainPipelines,
  getPipeline,
  getResults,
  updatePipeline,
  deletePipeline,
  createWebSocketUrl,
};

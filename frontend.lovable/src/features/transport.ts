import { demoDiagnostics, demoExplanation, demoGraph, demoProjects, graphToDot } from './fixtures';
import type { AnalysisJob, Diagnostic, FolderSelectionResult, GraphResult, NodeExplanation, Project, Transport, TreeResult } from './types';

export class ApiError extends Error {
  constructor(public code: string, message: string, public retryAfter: number | null = null) { super(message); }
}
async function api(path: string, init: RequestInit = {}) {
  const response = await fetch(`/api/v1${path}`, { ...init, headers: { 'Content-Type': 'application/json' } });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(data?.error?.code || 'HTTP_ERROR', data?.error?.message || `Backend returned ${response.status}`, data?.error?.retry_after_seconds ?? (Number(response.headers.get('Retry-After')) || null));
  }
  return response;
}
function job(value: AnalysisJob & { api_version?: string }) {
  if (value.api_version !== 'v1' || !value.analysis_id || typeof value.terminal !== 'boolean') throw new ApiError('MALFORMED_RESPONSE', 'Invalid analysis response.');
  return value;
}
export function normalizeGraph(data: GraphResult) {
  const graphId = data.metadata?.graph_id ?? data.graph_id;
  if (!graphId || data.schema_version !== '1.0.0' || !Array.isArray(data.nodes) || !Array.isArray(data.edges) || !Array.isArray(data.evidence) || !Array.isArray(data.diagnostics) || !data.summary) throw new ApiError('MALFORMED_RESPONSE', 'Invalid graph response.');
  return { ...data, graph_id: graphId, partial_load: Boolean(data.page?.partial_load ?? data.partial_load) };
}
export function mergePages(first: GraphResult, next: GraphResult): GraphResult {
  if (first.graph_id !== next.graph_id || first.schema_version !== next.schema_version) throw new ApiError('RESULT_MISMATCH', 'Graph pages belong to different results.');
  const unique = <T,>(items: T[], key: (item: T) => string) => [...new Map(items.map(item => [key(item), item])).values()];
  return { ...next, summary: first.summary, nodes: unique([...first.nodes, ...next.nodes], n => n.id), edges: unique([...first.edges, ...next.edges], e => e.id), evidence: unique([...first.evidence, ...next.evidence], e => e.evidence_id), diagnostics: unique([...first.diagnostics, ...next.diagnostics], d => d.id), partial_load: Boolean(next.page?.next_cursor) };
}
export const liveTransport: Transport = {
  mode: 'live',
  async listProjects() {
    const data = await (await api('/projects')).json();
    if (data.api_version !== 'v1' || !Array.isArray(data.projects)) throw new ApiError('MALFORMED_RESPONSE', 'Invalid project response.');
    return data.projects as Project[];
  },
  async analyze(projectId, refresh = false, signal) {
    return job(await (await api('/analyses', { method: 'POST', signal, body: JSON.stringify({ project: { root_id: projectId, relative_path: '.' }, options: { metrics: false }, refresh }) })).json());
  },
  async status(id, signal) { return job(await (await api(`/analyses/${encodeURIComponent(id)}`, { signal })).json()); },
  async cancel(id) { return job(await (await api(`/analyses/${encodeURIComponent(id)}`, { method: 'DELETE' })).json()); },
  async getGraph(id, cursor, signal) {
    const query = new URLSearchParams({ limit: '200' });
    if (cursor) query.set('cursor', cursor);
    return normalizeGraph(await (await api(`/analyses/${encodeURIComponent(id)}/graph?${query}`, { signal })).json());
  },
  async getDiagnostics(id, signal) { return (await (await api(`/analyses/${encodeURIComponent(id)}/diagnostics`, { signal })).json()).items as Diagnostic[]; },
  async explain(id, nodeId) { return await (await api(`/analyses/${encodeURIComponent(id)}/nodes/${encodeURIComponent(nodeId)}/explain?provider=rule-based`)).json() as NodeExplanation; },
  async exportDot(id) { return (await api(`/analyses/${encodeURIComponent(id)}/export/dot`)).blob(); },
  async navigate(path, line, column, sessionToken) {
    if (!sessionToken) throw new ApiError('EDITOR_UNAVAILABLE', 'Launch an analysis from Thonny to enable editor navigation.');
    return await (await api('/editor/navigate', { method: 'POST', body: JSON.stringify({ session_token: sessionToken, relative_path: path, line, ...(column && column > 0 ? { column } : {}) }) })).json();
  },
  async chooseFolder() {
    if (typeof (window as unknown as { codeStructHost?: { chooseProjectFolder?: () => Promise<unknown> } })?.codeStructHost?.chooseProjectFolder === 'function') {
      const res = await (window as unknown as { codeStructHost: { chooseProjectFolder: () => Promise<unknown> } }).codeStructHost.chooseProjectFolder();
      if (res && typeof res === 'object') return res as FolderSelectionResult;
    }
    return (await (await api('/host/choose-folder', { method: 'POST' })).json()) as FolderSelectionResult;
  },
  async getTree(id, signal) {
    return (await (await api(`/analyses/${encodeURIComponent(id)}/tree`, { signal })).json()) as TreeResult;
  },
};
const demoJob: AnalysisJob = { analysis_id: 'ana_canonical_12345', state: 'completed', terminal: true, progress: { phase: 'completed', percent: 100, message_code: 'ANALYSIS_COMPLETE' }, partial: false, cache_hit: false, diagnostics_summary: { info: 0, warning: 1, error: 0 } };
export const demoTransport: Transport = {
  mode: 'demo',
  async listProjects() { return demoProjects; },
  async analyze() { return demoJob; },
  async status() { return demoJob; },
  async cancel() { return { ...demoJob, state: 'cancelled' }; },
  async getGraph() { return demoGraph; },
  async getDiagnostics() { return demoDiagnostics; },
  async explain() { return demoExplanation; },
  async exportDot() { return new Blob([graphToDot(demoGraph)], { type: 'text/vnd.graphviz' }); },
  async navigate() { return { status: 'demo_only' }; },
  async chooseFolder() {
    return { cancelled: false, root_id: 'demo_root', project_name: 'demo_project', path: '/demo/project', analysis_id: 'ana_canonical_12345' };
  },
  async getTree(_analysisId?: string) {
    return {
      api_version: 'v1',
      request_id: 'req_demo',
      analysis_id: 'ana_canonical_12345',
      root_id: 'demo_root',
      root_path: '/demo/project',
      tree: {
        id: 'dir_root',
        name: 'demo_project',
        path: '',
        kind: 'directory' as const,
        children: [
          {
            id: 'file_main',
            name: 'main.py',
            path: 'main.py',
            kind: 'file' as const,
            extension: '.py',
            symbols: [
              {
                id: 'mod_main',
                name: 'main',
                path: 'main.py',
                qualified_name: 'main',
                kind: 'module' as const,
                children: [
                  {
                    id: 'cls_app',
                    name: 'App',
                    path: 'main.py',
                    qualified_name: 'main.App',
                    kind: 'class' as const,
                    children: [
                      { id: 'fn_run', name: 'run', path: 'main.py', qualified_name: 'main.App.run', kind: 'method' as const, children: [] },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
      excluded: [],
    };
  },
};
export const getTransport = (): Transport => import.meta.env.VITE_CODESTRUCT_MODE === 'demo' ? demoTransport : liveTransport;

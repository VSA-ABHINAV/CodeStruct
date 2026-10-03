import { demoDiagnostics, demoExplanation, demoGraph, demoProjects, graphToDot } from "./fixtures";
import type { AnalysisJob, Diagnostic, GraphResult, NodeExplanation, Project, Transport } from "./types";

const api = async (path: string, init?: RequestInit) => {
  const response = await fetch(`/api/v1${path}`, { ...init, headers: { "Content-Type": "application/json" } });
  if (!response.ok) throw new Error(`CodeStruct API returned ${response.status}`);
  return response;
};

const liveTransport: Transport = {
  mode: "live",
  async listProjects() {
    const data = (await (await api("/projects")).json()) as { projects: Project[] };
    return data.projects;
  },
  async analyze(projectId, refresh = false) {
    return (await (await api("/analyses", { method: "POST", body: JSON.stringify({ project: { root_id: projectId, relative_path: "." }, options: { metrics: false }, refresh }) })).json()) as AnalysisJob;
  },
  async getGraph(analysisId) {
    const data = (await (await api(`/analyses/${encodeURIComponent(analysisId)}/graph`)).json()) as GraphResult & { page?: { partial_load?: boolean } };
    return { ...data, graph_id: data.graph_id, partial_load: Boolean(data.page?.partial_load ?? data.partial_load) };
  },
  async getDiagnostics(analysisId) {
    const data = (await (await api(`/analyses/${encodeURIComponent(analysisId)}/diagnostics`)).json()) as { items: Diagnostic[] };
    return data.items;
  },
  async explain(analysisId, nodeId) {
    return (await (await api(`/analyses/${encodeURIComponent(analysisId)}/nodes/${encodeURIComponent(nodeId)}/explain?provider=rule-based`)).json()) as NodeExplanation;
  },
  async exportDot(analysisId) {
    return await (await api(`/analyses/${encodeURIComponent(analysisId)}/export/dot`)).blob();
  },
  async navigate(path, line, column) {
    return (await (await api("/editor/navigate", { method: "POST", body: JSON.stringify({ relative_path: path, line, ...(column ? { column } : {}) }) })).json()) as { status: string };
  },
};

export const demoTransport: Transport = {
  mode: "demo",
  async listProjects() {
    await new Promise((resolve) => setTimeout(resolve, 180));
    return demoProjects;
  },
  async analyze() {
    await new Promise((resolve) => setTimeout(resolve, 280));
    return { analysis_id: "ana_canonical_12345", state: "completed", terminal: true, progress: { phase: "completed", percent: 100, message_code: "ANALYSIS_COMPLETE" }, partial: false, cache_hit: false, diagnostics_summary: { info: 0, warning: 1, error: 0 } };
  },
  async getGraph() {
    await new Promise((resolve) => setTimeout(resolve, 200));
    return demoGraph;
  },
  async getDiagnostics() {
    return demoDiagnostics;
  },
  async explain() {
    await new Promise((resolve) => setTimeout(resolve, 260));
    return demoExplanation;
  },
  async exportDot() {
    return new Blob([graphToDot(demoGraph)], { type: "text/vnd.graphviz" });
  },
  async navigate() {
    await new Promise((resolve) => setTimeout(resolve, 180));
    return { status: "demo_only" };
  },
};

export const getTransport = (): Transport => (import.meta.env.VITE_CODESTRUCT_MODE === "live" ? liveTransport : demoTransport);
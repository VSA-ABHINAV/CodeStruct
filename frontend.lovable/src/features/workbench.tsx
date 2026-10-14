import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import {
  ArrowDownUp,
  Box,
  Check,
  ChevronRight,
  CircleAlert,
  Code2,
  Copy,
  Download,
  ExternalLink,
  FileCode2,
  FolderOpen,
  GitBranch,
  Maximize2,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  RefreshCw,
  Search,
  Table2,
  X,
  Zap,
} from "lucide-react";
import { useWorkbench } from "./useWorkbench";
import { getTransport } from "./transport";
import { graphToDot } from "./fixtures";
import { ProjectExplorerTree } from "./ProjectExplorerTree";
import type {
  Diagnostic,
  GraphEdge,
  GraphNode,
  GraphResult,
  NodeExplanation,
  NodeKind,
} from "./types";

const transport = getTransport();
const kindMeta: Record<string, { label: string; icon: typeof Box; tone: string }> = {
  project: { label: "Project", icon: FolderOpen, tone: "module" },
  directory: { label: "Directory", icon: FolderOpen, tone: "module" },
  package: { label: "Package", icon: FolderOpen, tone: "module" },
  module: { label: "Module", icon: FileCode2, tone: "module" },
  class: { label: "Class", icon: Box, tone: "class" },
  function: { label: "Function", icon: Code2, tone: "function" },
  method: { label: "Method", icon: Code2, tone: "function" },
};

function GraphNodeCard({
  data,
}: {
  data: { node: GraphNode; selected: boolean; onSelect: () => void };
}) {
  const meta = kindMeta[data.node.kind] ?? {
    label: data.node.kind.replaceAll("_", " "),
    icon: FileCode2,
    tone: "module",
  };
  const Icon = meta.icon;
  return (
    <button
      type="button"
      onClick={data.onSelect}
      className={cn(
        "codestruct-node text-left",
        `node-${meta.tone}`,
        data.selected && "node-selected"
      )}
      aria-label={`Inspect ${data.node.kind} ${data.node.name}`}
    >
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />
      <div className="flex items-center gap-2 border-b border-border/70 px-3 py-2">
        <span className="node-icon">
          <Icon size={14} />
        </span>
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          {meta.label}
        </span>
        {data.selected ? <Check className="ml-auto text-primary" size={13} /> : null}
      </div>
      <div className="px-3 py-3">
        <p className="font-mono text-[13px] font-semibold text-foreground truncate">{data.node.name}</p>
        <p className="mt-1 max-w-[190px] truncate font-mono text-[10px] text-muted-foreground">
          {data.node.qualified_name}
        </p>
        <p className="mt-3 flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground truncate">
          <FileCode2 size={11} className="shrink-0" />
          <span className="truncate">{data.node.location?.path ?? "Source unavailable"}</span>
        </p>
      </div>
    </button>
  );
}

export function getNodeLevel(node: GraphNode, allNodes: GraphNode[]): number {
  const kind = (node.kind || "").toLowerCase();
  if (kind === "project" || kind === "root" || kind === "directory" || kind === "folder") return 0;
  if (kind === "package" || kind === "file") return 1;
  if (kind === "module") return 2;
  if (kind === "class") return 3;
  if (kind === "method") return 5;
  if (kind === "function") {
    const parent = node.parent_id ? allNodes.find((n) => n.id === node.parent_id) : null;
    if (parent && parent.kind.toLowerCase() === "class") return 5;
    return 4;
  }
  return 2;
}

export function buildFlow(
  graph: GraphResult,
  selectedId: string | null,
  selectNode: (node: GraphNode) => void
) {
  const levelMap = new Map<number, GraphNode[]>();
  for (const node of graph.nodes) {
    const lvl = getNodeLevel(node, graph.nodes);
    const list = levelMap.get(lvl) ?? [];
    list.push(node);
    levelMap.set(lvl, list);
  }

  const activeLevels = Array.from(levelMap.keys()).sort((a, b) => a - b);
  const nodes: Node[] = [];

  activeLevels.forEach((lvl, tierIndex) => {
    const tierNodes = levelMap.get(lvl)!;
    tierNodes.sort((a, b) => {
      const pathA = a.location?.path || "";
      const pathB = b.location?.path || "";
      if (pathA !== pathB) return pathA.localeCompare(pathB);
      const lineA = a.location?.start_line || 0;
      const lineB = b.location?.start_line || 0;
      if (lineA !== lineB) return lineA - lineB;
      return a.name.localeCompare(b.name);
    });

    tierNodes.forEach((node, colIndex) => {
      nodes.push({
        id: node.id,
        position: {
          x: colIndex * 300 + 60,
          y: tierIndex * 240 + 60,
        },
        data: {
          node,
          selected: node.id === selectedId,
          onSelect: () => selectNode(node),
        },
        type: "codestruct",
      });
    });
  });

  const ids = new Set(nodes.map((n) => n.id));
  const edges: Edge[] = graph.edges
    .filter((edge) => edge.target_id && ids.has(edge.source_id) && ids.has(edge.target_id))
    .map((edge) => ({
      id: edge.id,
      source: edge.source_id,
      target: edge.target_id!,
      label: edge.kind,
      type: "smoothstep",
      markerEnd: { type: MarkerType.ArrowClosed },
      style: {
        stroke: "var(--primary)",
        strokeWidth: 1.5,
        strokeDasharray: edge.resolution_status === "resolved" ? undefined : "5 4",
      },
      labelStyle: { fill: "var(--muted-foreground)", fontSize: 10 },
      labelBgStyle: { fill: "var(--graph-surface)" },
    }));

  return { nodes, edges };
}

function Inspector({
  node,
  edge,
  graph,
  onClose,
  onExplain,
  explanation,
  onNavigate,
  editorAvailable,
  onSelectNode,
  onSelectEdge,
}: {
  node: GraphNode | null;
  edge: GraphEdge | null;
  graph: GraphResult;
  onClose: () => void;
  onExplain: () => void;
  explanation: NodeExplanation | null;
  onNavigate: (node: GraphNode) => void;
  editorAvailable: boolean;
  onSelectNode: (node: GraphNode) => void;
  onSelectEdge: (edge: GraphEdge) => void;
}) {
  const evidence = node
    ? graph.evidence.filter(
        (item) =>
          node.location?.path === item.location?.path &&
          (item.location?.start_line ?? 0) >= (node.location?.start_line ?? 0) &&
          (item.location?.start_line ?? 0) <=
            (node.location?.end_line ?? node.location?.start_line ?? 0)
      )
    : edge
    ? graph.evidence.filter((item) => edge.evidence_ids.includes(item.evidence_id))
    : [];

  return (
    <aside className="inspector-panel" aria-label="Selection inspector">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <p className="eyebrow">Inspector</p>
          <p className="text-sm font-semibold text-foreground">
            {node ? "Node details" : edge ? "Relationship details" : "Overview"}
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close inspector">
          <PanelRightClose size={16} />
        </Button>
      </div>

      {node ? (
        <div className="space-y-5 overflow-y-auto p-4">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <span className={cn("kind-dot", `dot-${node.kind}`)} />
              <Badge variant="outline">{kindMeta[node.kind]?.label ?? node.kind}</Badge>
            </div>
            <h2 className="font-mono text-lg font-semibold text-foreground break-all">{node.name}</h2>
            <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
              {node.qualified_name}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="metric-cell">
              <span>Start</span>
              <strong>
                {node.location
                  ? `${node.location.start_line}:${node.location.start_column}`
                  : "Unavailable"}
              </strong>
            </div>
            <div className="metric-cell">
              <span>End</span>
              <strong>
                {node.location
                  ? `${node.location.end_line}:${node.location.end_column}`
                  : "Unavailable"}
              </strong>
            </div>
          </div>

          <div className="inspector-section">
            <p className="section-label">Source location</p>
            <div className="path-row">
              <FileCode2 size={14} className="shrink-0" />
              <span className="truncate font-mono text-xs text-foreground" title={node.location?.path ?? ""}>
                {node.location
                  ? `${node.location.path}:${node.location.start_line ?? 1}:${node.location.start_column ?? 0}`
                  : "No source coordinates"}
              </span>
            </div>
            {node.location?.path ? (
              <p className="mt-1 text-[10px] text-muted-foreground font-mono break-all">
                {node.location.path}
              </p>
            ) : null}
            {node.location?.start_line ? (
              <Button
                variant="outline"
                size="sm"
                className="mt-3 w-full"
                disabled={!editorAvailable}
                title={
                  editorAvailable
                    ? "Request editor navigation"
                    : "Launch from Thonny or IDE to authorize navigation"
                }
                onClick={() => onNavigate(node)}
              >
                <ExternalLink size={13} className="mr-1.5" />
                Open in editor
              </Button>
            ) : null}
          </div>

          <div className="inspector-section">
            <p className="section-label">Connected relationships</p>
            <div className="space-y-1.5 mt-2">
              {graph.edges
                .filter((e) => e.source_id === node.id || e.target_id === node.id)
                .map((e) => {
                  const isSource = e.source_id === node.id;
                  const otherId = isSource ? e.target_id : e.source_id;
                  const otherNode = otherId ? graph.nodes.find((n) => n.id === otherId) : null;
                  return (
                    <button
                      key={e.id}
                      type="button"
                      className="flex items-center justify-between w-full px-2.5 py-1.5 rounded text-left hover:bg-accent/60 transition-colors font-mono text-xs border border-border/50"
                      onClick={() => {
                        if (otherNode) {
                          onSelectNode(otherNode);
                        } else {
                          onSelectEdge(e);
                        }
                      }}
                    >
                      <div className="flex items-center gap-1.5 truncate">
                        <span className="text-[11px] text-primary font-semibold">{e.kind}</span>
                        <span className="text-muted-foreground">{isSource ? "→" : "←"}</span>
                        <span className="truncate font-medium text-foreground">
                          {otherNode ? otherNode.name : otherId ?? "unresolved"}
                        </span>
                      </div>
                      <Badge variant="outline" className="text-[9px] shrink-0 ml-1">
                        {e.resolution_status}
                      </Badge>
                    </button>
                  );
                })}
              {graph.edges.filter((e) => e.source_id === node.id || e.target_id === node.id).length ===
              0 ? (
                <p className="empty-copy">No connected edges for this symbol.</p>
              ) : null}
            </div>
          </div>

          <div className="inspector-section">
            <p className="section-label">Attributes</p>
            {Object.entries(node.attributes).map(([key, value]) => (
              <div className="attribute-row" key={key}>
                <span>{key}</span>
                <code>{typeof value === "string" ? value : JSON.stringify(value)}</code>
              </div>
            ))}
            {Object.keys(node.attributes).length === 0 ? (
              <p className="empty-copy">No attributes reported.</p>
            ) : null}
          </div>

          <div className="inspector-section">
            <p className="section-label">
              Observed evidence <span>({evidence.length})</span>
            </p>
            {evidence.map((item) => (
              <div className="evidence-item" key={item.evidence_id}>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{item.origin}</Badge>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    line {item.location?.start_line}
                  </span>
                </div>
                <code>{item.excerpt ?? "Excerpt unavailable"}</code>
                <p>{item.explanation ?? "No explanation available."}</p>
              </div>
            ))}
            {evidence.length === 0 ? (
              <p className="empty-copy">No observed evidence records attached.</p>
            ) : null}
          </div>

          <div className="inspector-section">
            <div className="flex items-center justify-between">
              <p className="section-label">Architectural explanation</p>
              <Badge variant="outline">{explanation?.provider ?? "Rule-based"}</Badge>
            </div>
            {explanation ? (
              <div className="explanation-box">
                <p className="font-semibold text-foreground text-xs">{explanation.role}</p>
                <p className="mt-2 text-xs text-muted-foreground">{explanation.summary}</p>
                {explanation.dependencies_summary ? (
                  <p className="mt-2 text-[11px] text-muted-foreground/90 font-mono">
                    {explanation.dependencies_summary}
                  </p>
                ) : null}
                <p className="mt-2 font-mono text-[10px] text-muted-foreground">
                  {explanation.metrics_summary}
                </p>
                {explanation.recommendations?.length ? (
                  <div className="mt-3 border-t border-border/50 pt-2">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase">
                      Recommendations:
                    </p>
                    <ul className="list-disc list-inside text-[11px] text-muted-foreground mt-1 space-y-0.5">
                      {explanation.recommendations.map((rec, i) => (
                        <li key={i}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="mt-2">
                <p className="text-xs text-muted-foreground mb-2">No explanation requested yet.</p>
                <Button variant="outline" size="sm" onClick={onExplain} className="w-full">
                  <Zap size={13} className="mr-1.5 text-primary" />
                  Request explanation
                </Button>
              </div>
            )}
          </div>

          <div className="flex gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigator.clipboard?.writeText(node.qualified_name)}
            >
              <Copy size={13} className="mr-1.5" />
              Copy symbol
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigator.clipboard?.writeText(node.location?.path ?? "")}
            >
              <Copy size={13} className="mr-1.5" />
              Copy path
            </Button>
          </div>
        </div>
      ) : edge ? (
        <div className="space-y-5 overflow-y-auto p-4">
          <div>
            <Badge variant="secondary">{edge.kind}</Badge>
            <h2 className="mt-3 text-lg font-semibold text-foreground">Relationship</h2>
            <p className="mt-1 font-mono text-xs text-muted-foreground break-all">
              {edge.source_id} →{" "}
              {edge.target_id ??
                (typeof edge.target_reference === "string"
                  ? edge.target_reference
                  : JSON.stringify(edge.target_reference)) ??
                "Unresolved target"}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="metric-cell">
              <span>Resolution</span>
              <strong>{edge.resolution_status}</strong>
            </div>
            <div className="metric-cell">
              <span>Confidence</span>
              <strong>{edge.confidence}</strong>
            </div>
          </div>

          <div className="inspector-section">
            <p className="section-label">Relationship evidence</p>
            <p className="empty-copy">Occurrences: {edge.occurrence_count}</p>
            <p className="empty-copy">{edge.confidence_reason ?? "No confidence reason reported"}</p>
            <p className="empty-copy">Candidates: {edge.candidate_ids.join(", ") || "None"}</p>
            <p className="empty-copy">
              {evidence.length} observed record{evidence.length === 1 ? "" : "s"} attached to this
              relationship.
            </p>
            {evidence.map((item) => (
              <div className="evidence-item" key={item.evidence_id}>
                <code>{item.excerpt ?? "Excerpt unavailable"}</code>
                <p>{item.explanation ?? "No explanation available."}</p>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="empty-inspector">
          <Network size={22} />
          <p>Select a node or relationship</p>
          <span>Evidence, source coordinates, and actions will appear here.</span>
        </div>
      )}
    </aside>
  );
}

export function CodeStructWorkbench() {
  const {
    projects,
    projectId,
    openFolder,
    graph,
    tree,
    diagnostics,
    job,
    status,
    setStatus,
    error,
    setError,
    busy,
    paging,
    session,
    analysisId,
    load,
    loadMore,
    cancel,
  } = useWorkbench(transport);

  const activeSelection = useRef("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [explanation, setExplanation] = useState<NodeExplanation | null>(null);
  const [search, setSearch] = useState("");
  const [kindFilter, setKindFilter] = useState<NodeKind | "all">("all");
  const [view, setView] = useState<"graph" | "table">("graph");
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(true);
  const [activeDiag, setActiveDiag] = useState<"all" | "error" | "warning">("all");

  activeSelection.current = `${analysisId}:${selectedNode?.id ?? ""}`;

  useEffect(() => {
    document.documentElement.classList.add("dark");
  }, []);

  useEffect(() => {
    setSelectedNode(null);
    setSelectedEdge(null);
    setExplanation(null);
  }, [analysisId]);

  useEffect(() => {
    setExplanation(null);
  }, [selectedNode?.id]);

  const filteredNodes = useMemo(
    () =>
      graph?.nodes.filter((node) => {
        const matchesSearch =
          !search ||
          `${node.name} ${node.qualified_name} ${node.location?.path ?? ""}`
            .toLowerCase()
            .includes(search.toLowerCase());
        return matchesSearch && (kindFilter === "all" || node.kind === kindFilter);
      }) ?? [],
    [graph, kindFilter, search]
  );

  const flow = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };
    const full = buildFlow(graph, selectedNode?.id ?? null, (node) => {
      setSelectedNode(node);
      setSelectedEdge(null);
      setRightOpen(true);
    });
    const visible = new Set(filteredNodes.map((n) => n.id));
    return {
      nodes: full.nodes.filter((n) => visible.has(n.id)),
      edges: full.edges.filter((e) => visible.has(e.source) && visible.has(e.target)),
    };
  }, [graph, filteredNodes, selectedNode?.id]);

  const [flowNodes, setFlowNodes, onNodesChange] = useNodesState(flow.nodes);
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState(flow.edges);

  useEffect(() => {
    setFlowNodes((previous) => {
      const positions = new Map(previous.map((n) => [n.id, n.position]));
      return flow.nodes.map((n) => ({
        ...n,
        position: positions.get(n.id) ?? n.position,
      }));
    });
    setFlowEdges(flow.edges);
  }, [flow, setFlowNodes, setFlowEdges]);

  const onExplain = async () => {
    if (!selectedNode || !analysisId) return;
    const key = activeSelection.current;
    try {
      const value = await transport.explain(analysisId, selectedNode.id);
      if (key === activeSelection.current) setExplanation(value);
    } catch (err) {
      if (key === activeSelection.current)
        setError(err instanceof Error ? err.message : "Explanation failed");
    }
  };

  const downloadSliceDot = () => {
    if (!graph) return;
    try {
      const sliceGraph: GraphResult = {
        ...graph,
        nodes: filteredNodes,
        edges: graph.edges.filter(
          (e) =>
            filteredNodes.some((n) => n.id === e.source_id) &&
            filteredNodes.some((n) => n.id === e.target_id)
        ),
      };
      const dotContent = graphToDot(sliceGraph);
      const blob = new Blob([dotContent], { type: "text/vnd.graphviz" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `codestruct-slice-${analysisId || "graph"}.dot`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Slice export failed");
    }
  };

  const downloadCompleteDot = async () => {
    if (!analysisId || !graph) return;
    try {
      const blob = await transport.exportDot(analysisId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `codestruct-complete-${analysisId}.dot`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Complete graph export failed");
    }
  };

  const openEditor = async (node: GraphNode) => {
    if (!node.location?.path || !node.location.start_line) return;
    const key = activeSelection.current;
    try {
      const response = await transport.navigate(
        node.location.path,
        node.location.start_line,
        node.location.start_column ?? undefined,
        session ?? undefined
      );
      if (key === activeSelection.current)
        setStatus(
          response.status === "demo_only"
            ? "Demo mode: no editor connected"
            : "Navigation requested (queued)"
        );
    } catch (err) {
      if (key === activeSelection.current)
        setError(err instanceof Error ? err.message : "Navigation failed");
    }
  };

  const shownDiagnostics = diagnostics.filter(
    (item) => activeDiag === "all" || item.severity === activeDiag
  );

  const currentProjectTitle =
    tree?.root_path ||
    projects.find((p) => p.id === projectId)?.description ||
    projects.find((p) => p.id === projectId)?.display_name ||
    "No folder opened";

  return (
    <div className="codestruct-app">
      {error ? (
        <div role="alert" className="integration-alert">
          {error}
        </div>
      ) : null}
      <span className="sr-only" role="status">
        {status}
      </span>

      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">
            <GitBranch size={18} />
          </div>
          <div>
            <div className="brand-name">CodeStruct</div>
            <div className="brand-subtitle">Python architecture workbench</div>
          </div>
        </div>

        <div className="topbar-divider" />

        <Button
          variant="default"
          size="sm"
          onClick={() => void openFolder()}
          disabled={busy}
          className="gap-1.5 font-medium"
        >
          <FolderOpen size={14} />
          Open Folder
        </Button>

        <div className="topbar-divider" />

        <div className="project-heading min-w-0">
          <span className="eyebrow">Workspace</span>
          <span
            className="font-mono text-sm font-semibold text-foreground truncate max-w-[340px]"
            title={currentProjectTitle}
          >
            {currentProjectTitle}
          </span>
        </div>

        <div className="topbar-actions ml-auto flex items-center gap-2">
          <span className="job-status">
            <span className={cn("status-dot", busy ? "status-pulse" : "status-ready")} />
            {status}
          </span>

          <Button
            variant="outline"
            size="sm"
            onClick={() => void load(true)}
            disabled={busy || !projectId}
            className="gap-1.5"
          >
            <RefreshCw className={cn(busy && "animate-spin")} size={14} />
            Refresh
          </Button>

          {busy && job ? (
            <Button variant="outline" size="sm" onClick={() => void cancel()}>
              Cancel
            </Button>
          ) : null}
        </div>
      </header>

      <div
        className="workbench-body"
        style={{
          gridTemplateColumns: `${leftOpen ? "280px" : "0px"} minmax(0, 1fr) ${
            rightOpen ? "320px" : "0px"
          }`,
        }}
      >
        <aside
          className={cn(
            "sidebar transition-all duration-200",
            !leftOpen ? "hidden" : "flex flex-col"
          )}
          style={{ width: leftOpen ? "280px" : "0px" }}
        >
          <div className="sidebar-header border-b border-border">
            <div className="min-w-0 flex-1 mr-2">
              <p className="eyebrow">Project Explorer</p>
              <p
                className="text-xs font-semibold text-foreground truncate"
                title={tree?.tree.name ?? currentProjectTitle}
              >
                {tree?.tree.name ?? currentProjectTitle}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setLeftOpen(false)}
              aria-label="Collapse project sidebar"
            >
              <PanelLeftClose size={16} />
            </Button>
          </div>

          <div className="px-3 py-2 border-b border-border/60">
            <label className="search-field m-0">
              <Search size={14} className="shrink-0" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search files & symbols…"
              />
              {search ? (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="text-muted-foreground hover:text-foreground p-0.5"
                  aria-label="Clear search"
                >
                  <X size={12} />
                </button>
              ) : null}
            </label>
          </div>

          <div className="flex-1 overflow-y-auto px-1 py-2">
            <ProjectExplorerTree
              treeResult={tree}
              search={search}
              selectedNodeId={selectedNode?.id ?? null}
              onSelectSymbol={(symbolId, qname) => {
                const found = graph?.nodes.find(
                  (n) => n.id === symbolId || n.qualified_name === qname || n.name === qname
                );
                if (found) {
                  setSelectedNode(found);
                  setSelectedEdge(null);
                  setRightOpen(true);
                }
              }}
            />
          </div>

          <div className="sidebar-section border-t border-border mt-auto">
            <div className="flex items-center justify-between mb-2">
              <p className="section-label">Kind Filter</p>
              {kindFilter !== "all" ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-5 px-1 text-[10px]"
                  onClick={() => setKindFilter("all")}
                >
                  Reset
                </Button>
              ) : null}
            </div>
            <div className="filter-pills">
              {(["all", "module", "class", "function"] as const).map((kind) => (
                <button
                  type="button"
                  onClick={() => setKindFilter(kind)}
                  className={cn("filter-pill", kindFilter === kind && "active")}
                  key={kind}
                >
                  {kind === "all" ? "All kinds" : kindMeta[kind]?.label ?? kind}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {!leftOpen ? (
          <Button
            variant="outline"
            size="icon"
            className="sidebar-expand"
            onClick={() => setLeftOpen(true)}
            aria-label="Open project sidebar"
            title="Open Project Explorer"
          >
            <PanelLeftOpen size={16} />
          </Button>
        ) : null}

        <main className="main-workspace">
          <div className="workspace-toolbar">
            <div className="toolbar-tabs">
              <button
                type="button"
                className={cn("toolbar-tab", view === "graph" && "active")}
                onClick={() => setView("graph")}
              >
                <Network size={15} />
                Graph
              </button>
              <button
                type="button"
                className={cn("toolbar-tab", view === "table" && "active")}
                onClick={() => setView("table")}
              >
                <Table2 size={15} />
                Accessible table
              </button>
            </div>
            <div className="toolbar-actions">
              <span className="loaded-count">
                {filteredNodes.length} of {graph?.summary.nodes_total ?? 0} nodes loaded
              </span>

              <Button
                variant="outline"
                size="sm"
                onClick={() => downloadSliceDot()}
                disabled={!graph}
                title="Export currently loaded nodes and edges as DOT"
                aria-label="Export DOT (Loaded Slice)"
                className="h-7 text-xs px-2 gap-1"
              >
                <Download size={13} />
                DOT (Slice)
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => void downloadCompleteDot()}
                disabled={!graph || !analysisId}
                title={
                  graph?.partial_load
                    ? "Export complete server-side graph as DOT (includes all pages)"
                    : "Export complete graph as DOT"
                }
                aria-label="Export DOT (Complete Graph)"
                className="h-7 text-xs px-2 gap-1"
              >
                <Download size={13} />
                DOT (Complete)
              </Button>

              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  const action = document.fullscreenElement
                    ? document.exitFullscreen?.()
                    : document.documentElement.requestFullscreen?.();
                  void action?.catch((err) => setError(err.message));
                }}
                aria-label="Enter fullscreen"
                title="Fullscreen"
              >
                <Maximize2 size={16} />
              </Button>

              <Button
                variant="ghost"
                size="icon"
                onClick={() => setRightOpen((value) => !value)}
                aria-label="Toggle inspector"
                title="Toggle inspector"
              >
                {rightOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
              </Button>
            </div>
          </div>

          {view === "graph" ? (
            <div className="graph-stage">
              {!graph ? (
                <div className="empty-inspector">
                  <p>{busy ? status : "Click 'Open Folder' to open a Python project"}</p>
                </div>
              ) : null}

              <ReactFlowProvider>
                <ReactFlow
                  nodes={flowNodes}
                  edges={flowEdges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onNodeClick={(_, node) => {
                    const selected = graph?.nodes.find((item) => item.id === node.id);
                    if (selected) {
                      setSelectedNode(selected);
                      setSelectedEdge(null);
                      setRightOpen(true);
                    }
                  }}
                  onEdgeClick={(_, edge) => {
                    const selected = graph?.edges.find((item) => item.id === edge.id);
                    if (selected) {
                      setSelectedEdge(selected);
                      setSelectedNode(null);
                      setRightOpen(true);
                    }
                  }}
                  nodeTypes={{ codestruct: GraphNodeCard }}
                  fitView
                  fitViewOptions={{ padding: 0.25 }}
                  minZoom={0.35}
                  maxZoom={1.4}
                  proOptions={{ hideAttribution: true }}
                >
                  <Background color="var(--border)" gap={22} size={1} />
                  <Controls showInteractive={false} />
                  <MiniMap
                    nodeColor={(node) =>
                      (node.data?.node as GraphNode | undefined)?.kind === "module"
                        ? "var(--chart-1)"
                        : (node.data?.node as GraphNode | undefined)?.kind === "class"
                        ? "var(--chart-2)"
                        : "var(--chart-3)"
                    }
                    maskColor="var(--graph-background)"
                  />
                </ReactFlow>
              </ReactFlowProvider>

              {graph?.partial_load ? (
                <div className="partial-banner">
                  <CircleAlert size={14} className="text-warning shrink-0" />
                  <span>
                    Partial graph loaded ({filteredNodes.length} of {graph.summary.nodes_total} nodes).
                    'DOT (Slice)' exports loaded page; 'DOT (Complete)' exports full graph.
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={paging || !graph.page?.next_cursor}
                    onClick={() => void loadMore()}
                  >
                    {paging ? "Loading…" : "Load more"}
                  </Button>
                </div>
              ) : null}

              <div className="graph-legend">
                <span className="section-label">Legend</span>
                {Object.entries(kindMeta).map(([kind, meta]) => (
                  <span key={kind} className="legend-item">
                    <span className={cn("kind-dot", `dot-${kind}`)} />
                    {meta.label}
                  </span>
                ))}
                <span className="legend-edge">
                  <span />
                  defines
                </span>
              </div>
            </div>
          ) : (
            <div className="table-stage">
              <div className="table-header">
                <div>
                  <p className="eyebrow">Synchronized alternative</p>
                  <h2>Graph elements</h2>
                </div>
                <Badge variant="outline">
                  <ArrowDownUp size={12} />
                  Keyboard navigable
                </Badge>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Kind</th>
                      <th>Source</th>
                      <th>Coordinates</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredNodes.map((node) => (
                      <tr
                        key={node.id}
                        tabIndex={0}
                        onClick={() => {
                          setSelectedNode(node);
                          setSelectedEdge(null);
                          setRightOpen(true);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            setSelectedNode(node);
                            setRightOpen(true);
                          }
                        }}
                      >
                        <td>
                          <span className="table-symbol">
                            <span className={cn("kind-dot", `dot-${node.kind}`)} />{" "}
                            <span>
                              <strong>{node.name}</strong>
                              <small>{node.qualified_name}</small>
                            </span>
                          </span>
                        </td>
                        <td>
                          <Badge variant="secondary">{node.kind}</Badge>
                        </td>
                        <td>
                          <code>{node.location?.path ?? "Unavailable"}</code>
                        </td>
                        <td>
                          <code>
                            {node.location?.start_line
                              ? `${node.location.start_line}:${node.location.start_column}`
                              : "Unavailable"}
                          </code>
                        </td>
                        <td>
                          {graph?.evidence.filter(
                            (item) =>
                              node.location?.path === item.location?.path &&
                              (item.location?.start_line ?? 0) >= (node.location?.start_line ?? 0) &&
                              (item.location?.start_line ?? 0) <=
                                (node.location?.end_line ?? node.location?.start_line ?? 0)
                          ).length ?? 0}{" "}
                          records
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>

        {rightOpen ? (
          <Inspector
            node={selectedNode}
            edge={selectedEdge}
            graph={
              graph ?? {
                nodes: [],
                edges: [],
                evidence: [],
                diagnostics: [],
                partial_load: false,
                graph_id: "",
                schema_version: "",
                summary: {
                  source_units_total: 0,
                  nodes_total: 0,
                  edges_total: 0,
                  evidence_total: 0,
                  diagnostics_total: 0,
                  nodes_by_kind: {},
                  edges_by_kind: {},
                  edges_by_resolution: {},
                  edges_by_confidence: {},
                },
              }
            }
            onSelectNode={(n) => {
              setSelectedNode(n);
              setSelectedEdge(null);
            }}
            onSelectEdge={(e) => {
              setSelectedEdge(e);
              setSelectedNode(null);
            }}
            editorAvailable={Boolean(session) || transport.mode === "demo"}
            onClose={() => setRightOpen(false)}
            onExplain={() => void onExplain()}
            explanation={explanation}
            onNavigate={(node) => void openEditor(node)}
          />
        ) : null}
      </div>

      <section className={cn("diagnostics-tray", !diagnosticsOpen && "tray-collapsed")}>
        <div className="diagnostics-bar">
          <button
            type="button"
            className="diagnostics-title"
            onClick={() => setDiagnosticsOpen((value) => !value)}
          >
            <ChevronRight className={cn(diagnosticsOpen && "rotate-90")} size={15} />
            <CircleAlert size={15} />
            <span>Diagnostics</span>
            <Badge variant={diagnostics.length ? "destructive" : "secondary"}>
              {diagnostics.length}
            </Badge>
          </button>
          <div className="diagnostic-tabs">
            {(["all", "error", "warning"] as const).map((severity) => (
              <button
                type="button"
                key={severity}
                onClick={() => setActiveDiag(severity)}
                className={cn(activeDiag === severity && "active")}
              >
                {severity === "all" ? "All" : severity === "error" ? "Errors" : "Warnings"}{" "}
                {severity === "error"
                  ? diagnostics.filter((item) => item.severity === "error").length
                  : severity === "warning"
                  ? diagnostics.filter((item) => item.severity === "warning").length
                  : diagnostics.length}
              </button>
            ))}
          </div>
          <span className="diagnostic-note">
            {transport.mode === "demo"
              ? "Synthetic fixture · no local files accessed"
              : "Connected to local adapter"}
          </span>
        </div>
        {diagnosticsOpen ? (
          <div className="diagnostics-content">
            {shownDiagnostics.map((item) => (
              <div className="diagnostic-item" key={item.id}>
                <span className={cn("severity-mark", `severity-${item.severity}`)} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <code>{item.code}</code>
                    <Badge variant={item.severity === "error" ? "destructive" : "outline"}>
                      {item.severity}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{item.phase}</span>
                  </div>
                  <p>{item.message}</p>
                  <span className="diagnostic-location">
                    {item.location
                      ? `${item.location?.path}:${item.location?.start_line}`
                      : "Location unavailable"}{" "}
                    · {item.consequence}
                  </span>
                </div>
              </div>
            ))}
            {shownDiagnostics.length === 0 ? (
              <p className="empty-diagnostics">No diagnostics in this filter.</p>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
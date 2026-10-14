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
  Copy,
  Download,
  ExternalLink,
  FileCode2,
  FolderOpen,
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

function GraphNodeCard({
  data,
}: {
  data: {
    node: GraphNode;
    selected: boolean;
    onSelect: () => void;
  };
}) {
  const { node, selected, onSelect } = data;
  const kind = (node.kind || "").toLowerCase();

  if (kind === "class") {
    return (
      <div
        onClick={onSelect}
        className={cn(
          "w-60 bg-white border-2 border-green-600 rounded-md shadow-xs p-3 text-left select-none transition-all cursor-pointer hover:shadow-md",
          selected && "bg-teal-50/50 ring-2 ring-green-400/40 shadow-md"
        )}
      >
        <Handle type="target" position={Position.Top} className="opacity-0" />
        <Handle type="source" position={Position.Bottom} className="opacity-0" />
        <div className="flex items-center justify-between pb-1.5 border-b border-green-200 mb-1.5">
          <div className="flex items-center gap-1.5">
            <span className="px-1 py-0.2 bg-green-600 text-white font-mono text-[9px] font-bold rounded">
              C
            </span>
            <span className="text-[10px] uppercase font-bold text-green-800 tracking-wider">
              Class
            </span>
          </div>
          <span className="text-[9px] font-mono text-gray-500">
            {node.location
              ? `L${node.location.start_line}${
                  node.location.end_line ? `-L${node.location.end_line}` : ""
                }`
              : ""}
          </span>
        </div>
        <div className="font-bold text-xs text-green-950 flex items-center justify-between">
          <span className="truncate font-mono">{node.name}</span>
          {selected ? <span className="text-xs text-green-600">★</span> : null}
        </div>
        {node.attributes && Object.keys(node.attributes).length > 0 ? (
          <div className="mt-2 text-[10px] font-mono bg-white/80 p-1.5 rounded border border-green-200 text-gray-700 space-y-0.5">
            {Object.entries(node.attributes)
              .slice(0, 3)
              .map(([k, v]) => (
                <div key={k} className="truncate">
                  + {k}: {String(v)}
                </div>
              ))}
          </div>
        ) : null}
      </div>
    );
  }

  if (kind === "function") {
    return (
      <div
        onClick={onSelect}
        className={cn(
          "w-48 bg-white border border-amber-500 rounded-md shadow-xs p-2.5 text-left select-none transition-all cursor-pointer hover:border-amber-600",
          selected && "ring-2 ring-amber-400/40 shadow-md bg-amber-50/20"
        )}
      >
        <Handle type="target" position={Position.Top} className="opacity-0" />
        <Handle type="source" position={Position.Bottom} className="opacity-0" />
        <div className="flex items-center justify-between pb-1.5 border-b border-gray-100 mb-1">
          <div className="flex items-center gap-1.5">
            <span className="px-1 py-0.2 bg-amber-500 text-white font-mono text-[9px] font-bold rounded">
              F
            </span>
            <span className="text-[10px] uppercase font-bold text-amber-700 tracking-wider">
              Function
            </span>
          </div>
          <span className="text-[9px] font-mono text-gray-400">
            {node.location?.start_line ? `L${node.location.start_line}` : ""}
          </span>
        </div>
        <div className="font-bold text-xs text-gray-900 truncate font-mono">
          {node.name}()
        </div>
        <div className="text-[10px] text-gray-500 mt-1 truncate font-mono">
          {node.qualified_name}
        </div>
      </div>
    );
  }

  if (kind === "method") {
    return (
      <div
        onClick={onSelect}
        className={cn(
          "w-44 bg-white border border-sky-400 rounded-md shadow-xs p-2 text-left select-none transition-all cursor-pointer hover:border-sky-600",
          selected && "ring-2 ring-sky-400/40 shadow-sm bg-sky-50/20"
        )}
      >
        <Handle type="target" position={Position.Top} className="opacity-0" />
        <Handle type="source" position={Position.Bottom} className="opacity-0" />
        <div className="flex items-center gap-1 mb-1">
          <span className="text-[9px] font-bold text-sky-700 font-mono">M</span>
          <span className="text-[10px] font-medium text-sky-800 truncate font-mono">
            {node.name}()
          </span>
        </div>
        <div className="text-[9px] text-gray-500 font-mono truncate">
          {node.location?.start_line
            ? `L${node.location.start_line}`
            : node.qualified_name}
        </div>
      </div>
    );
  }

  if (kind === "project" || kind === "package" || kind === "directory") {
    return (
      <div
        onClick={onSelect}
        className={cn(
          "w-52 bg-white border-2 border-cyan-600 rounded-md shadow-xs p-2.5 text-left select-none transition-all cursor-pointer hover:shadow-md",
          selected && "ring-2 ring-cyan-400/50 shadow-md bg-cyan-50/20"
        )}
      >
        <Handle type="target" position={Position.Top} className="opacity-0" />
        <Handle type="source" position={Position.Bottom} className="opacity-0" />
        <div className="flex items-center gap-1.5 pb-1 border-b border-gray-100 mb-1">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-600 inline-block" />
          <span className="text-[10px] uppercase font-bold text-cyan-800 tracking-wider">
            {kind === "project" ? "Project" : "Package"}
          </span>
        </div>
        <div className="font-bold text-xs text-gray-900 truncate font-mono">
          {node.name}
        </div>
      </div>
    );
  }

  // Default: module / file
  return (
    <div
      onClick={onSelect}
      className={cn(
        "w-56 bg-white border-2 border-teal-600 rounded-md shadow-xs p-2.5 text-left select-none transition-all cursor-pointer hover:shadow-md",
        selected && "ring-2 ring-teal-400/60 shadow-md bg-teal-50/30"
      )}
    >
      <Handle type="target" position={Position.Top} className="opacity-0" />
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
      <div className="flex items-center justify-between pb-1.5 border-b border-gray-100 mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-teal-600 inline-block" />
          <span className="text-[10px] uppercase font-bold text-teal-800 tracking-wider">
            Module
          </span>
        </div>
        <span className="text-[10px] text-gray-400 font-mono">Python</span>
      </div>
      <div className="font-bold text-xs text-gray-900 truncate font-mono">
        {node.name}
      </div>
      <div className="text-[10px] text-gray-500 mt-0.5 truncate font-mono">
        {node.qualified_name}
      </div>
    </div>
  );
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
    .map((edge) => {
      const isDefines = edge.kind === "defines";
      return {
        id: edge.id,
        source: edge.source_id,
        target: edge.target_id!,
        label: edge.kind,
        type: "smoothstep",
        markerEnd: { type: MarkerType.ArrowClosed },
        style: {
          stroke: isDefines ? "#0d9488" : "#64748b",
          strokeWidth: isDefines ? 1.8 : 1.5,
          strokeDasharray:
            isDefines && edge.resolution_status === "resolved" ? undefined : "4 4",
        },
        labelStyle: {
          fill: isDefines ? "#0d9488" : "#64748b",
          fontSize: 10,
          fontWeight: 600,
          fontFamily: "Consolas, monospace",
        },
        labelBgStyle: { fill: "#ffffff", fillOpacity: 0.9 },
      };
    });

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
}) {
  const definedMembers = useMemo(() => {
    if (!node) return [];
    return graph.nodes.filter(
      (n) =>
        n.parent_id === node.id ||
        (n.location?.path === node.location?.path &&
          (n.location?.start_line ?? 0) > (node.location?.start_line ?? 0) &&
          (n.location?.end_line ?? 999999) <= (node.location?.end_line ?? 999999) &&
          n.id !== node.id)
    );
  }, [node, graph.nodes]);

  const definedByNode = useMemo(() => {
    if (!node) return null;
    if (node.parent_id) {
      return graph.nodes.find((n) => n.id === node.parent_id) || null;
    }
    const defEdge = graph.edges.find((e) => e.target_id === node.id && e.kind === "defines");
    if (defEdge) {
      return graph.nodes.find((n) => n.id === defEdge.source_id) || null;
    }
    return null;
  }, [node, graph]);

  const connectedEdges = useMemo(() => {
    if (!node) return [];
    return graph.edges.filter((e) => e.source_id === node.id || e.target_id === node.id);
  }, [node, graph.edges]);

  const evidence = useMemo(() => {
    if (node) {
      return graph.evidence.filter(
        (item) =>
          node.location?.path === item.location?.path &&
          (item.location?.start_line ?? 0) >= (node.location?.start_line ?? 0) &&
          (item.location?.start_line ?? 0) <=
            (node.location?.end_line ?? node.location?.start_line ?? 0)
      );
    }
    if (edge) {
      return graph.evidence.filter((item) => edge.evidence_ids.includes(item.evidence_id));
    }
    return [];
  }, [node, edge, graph.evidence]);

  return (
    <aside
      className="w-72 border-l border-gray-300 flex flex-col bg-gray-50 shrink-0 h-full"
      data-purpose="right-panel-inspector"
      aria-label="Selection inspector"
    >
      <div className="h-8 border-b border-gray-200 px-3 flex items-center justify-between text-xs font-semibold text-gray-700 bg-gray-100 shrink-0">
        <div className="flex items-center space-x-1.5">
          <svg
            className="w-3.5 h-3.5 text-teal-700"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" x2="12" y1="16" y2="12" />
            <line x1="12" x2="12.01" y1="8" y2="8" />
          </svg>
          <span className="uppercase tracking-wider text-[11px] font-bold text-gray-600">
            Inspector
          </span>
        </div>
        <div className="flex items-center space-x-1">
          <span className="text-[10px] font-normal text-teal-700 bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
            {node ? "Active Node" : edge ? "Active Edge" : "Overview"}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-0.5"
            title="Collapse inspector"
            aria-label="Close inspector"
          >
            <PanelRightClose size={14} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 text-xs space-y-3.5">
        {node ? (
          <>
            {/* Target Symbol Header Card */}
            <div className="bg-white border border-gray-200 rounded p-3 shadow-xs">
              <div className="flex items-center gap-1.5 text-green-700 text-[11px] font-semibold uppercase">
                <span className="px-1 py-0.2 bg-green-600 text-white rounded font-mono text-[9px]">
                  {node.kind}
                </span>
                <span>Node Detail</span>
              </div>
              <h3 className="text-sm font-bold text-gray-900 mt-1 font-mono break-all">
                {node.name}
              </h3>
              <p className="text-[11px] text-gray-500 mt-0.5 break-all font-mono">
                {node.qualified_name}
              </p>
              <div className="mt-3 pt-2 border-t border-gray-100 flex items-center justify-between text-[11px]">
                <span className="text-gray-500">Source:</span>
                <span className="font-mono text-teal-700 font-medium truncate max-w-[170px]" title={node.location?.path}>
                  {node.location
                    ? `${node.location.path}:${node.location.start_line}`
                    : "No source coordinates"}
                </span>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="space-y-1.5">
              <button
                type="button"
                className="w-full text-center py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded font-medium text-xs shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                disabled={!editorAvailable || !node.location?.path}
                onClick={() => onNavigate(node)}
                title={
                  editorAvailable
                    ? "Open in editor"
                    : "Launch from Thonny or IDE to authorize editor navigation"
                }
              >
                Jump to Source in Editor
              </button>
              <button
                type="button"
                className="w-full text-center py-1.5 bg-white border border-gray-300 hover:bg-gray-100 text-gray-700 rounded text-xs transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                onClick={onExplain}
              >
                <Zap size={13} className="text-teal-600" />
                <span>
                  {explanation ? "Re-evaluate Explanation" : "Request Explanation"}
                </span>
              </button>
            </div>

            {/* Architectural Explanation Card */}
            {explanation ? (
              <div className="bg-white p-3 rounded border border-gray-200 shadow-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-gray-500 tracking-wider">
                    Architectural Explanation
                  </span>
                  <span className="text-[9px] bg-teal-50 text-teal-800 border border-teal-200 px-1 rounded font-mono">
                    {explanation.provider}
                  </span>
                </div>
                <p className="font-semibold text-gray-900 text-xs">{explanation.role}</p>
                <p className="text-xs text-gray-600 leading-relaxed">
                  {explanation.summary}
                </p>
                {explanation.dependencies_summary ? (
                  <p className="text-[11px] text-gray-500 font-mono bg-gray-50 p-1.5 rounded border border-gray-100">
                    {explanation.dependencies_summary}
                  </p>
                ) : null}
                {explanation.metrics_summary ? (
                  <p className="text-[10px] text-gray-400 font-mono">
                    {explanation.metrics_summary}
                  </p>
                ) : null}
              </div>
            ) : null}

            {/* Defined Members / Sub-elements */}
            {definedMembers.length > 0 ? (
              <div>
                <h4 className="text-[11px] font-bold uppercase text-gray-500 mb-1.5 tracking-wide">
                  Defined Symbols ({definedMembers.length})
                </h4>
                <div className="bg-white border border-gray-200 rounded divide-y divide-gray-100 font-mono text-[11px]">
                  {definedMembers.map((m) => (
                    <div
                      key={m.id}
                      className="p-2 flex items-center justify-between hover:bg-gray-50 cursor-pointer"
                      onClick={() => onSelectNode(m)}
                    >
                      <div className="flex items-center gap-1.5">
                        <span
                          className={cn(
                            "font-bold",
                            m.kind === "class"
                              ? "text-green-700"
                              : m.kind === "function"
                              ? "text-amber-600"
                              : "text-sky-600"
                          )}
                        >
                          {m.kind === "class" ? "C" : m.kind === "function" ? "f" : "m"}
                        </span>
                        <span className="text-gray-800">{m.name}()</span>
                      </div>
                      <span className="text-gray-400 text-[10px]">
                        L{m.location?.start_line}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Inbound / Outbound Relations */}
            <div>
              <h4 className="text-[11px] font-bold uppercase text-gray-500 mb-1.5 tracking-wide">
                Relationships
              </h4>
              <div className="space-y-1.5 text-[11px]">
                {definedByNode ? (
                  <div
                    className="bg-white p-2 rounded border border-gray-200 cursor-pointer hover:bg-teal-50/50 transition-colors"
                    onClick={() => onSelectNode(definedByNode)}
                  >
                    <div className="text-gray-500 text-[10px]">Defined By:</div>
                    <div className="font-medium text-teal-800 flex items-center gap-1.5 mt-0.5">
                      <span className="w-2 h-2 rounded bg-teal-500 shrink-0" />
                      <span className="truncate">{definedByNode.name}</span>
                    </div>
                  </div>
                ) : null}

                {connectedEdges.map((e) => {
                  const isSource = e.source_id === node.id;
                  const otherId = isSource ? e.target_id : e.source_id;
                  const otherNode = otherId
                    ? graph.nodes.find((n) => n.id === otherId)
                    : null;
                  return (
                    <div
                      key={e.id}
                      className="bg-white p-2 rounded border border-gray-200 cursor-pointer hover:bg-teal-50/50 transition-colors"
                      onClick={() => {
                        if (otherNode) onSelectNode(otherNode);
                      }}
                    >
                      <div className="text-gray-500 text-[10px] flex items-center justify-between">
                        <span>{isSource ? "Calls / References:" : "Referenced By:"}</span>
                        <span className="font-mono text-[9px] text-teal-700">{e.kind}</span>
                      </div>
                      <div className="font-medium text-gray-900 flex items-center gap-1.5 mt-0.5">
                        <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                        <span className="truncate">{otherNode ? otherNode.name : otherId}</span>
                      </div>
                    </div>
                  );
                })}

                {!definedByNode && connectedEdges.length === 0 ? (
                  <p className="text-[11px] text-gray-400 py-1">
                    No connected relationships for this symbol.
                  </p>
                ) : null}
              </div>
            </div>

            {/* Observed Evidence */}
            {evidence.length > 0 ? (
              <div>
                <h4 className="text-[11px] font-bold uppercase text-gray-500 mb-1.5 tracking-wide">
                  Observed Evidence ({evidence.length})
                </h4>
                <div className="space-y-1.5">
                  {evidence.map((item) => (
                    <div
                      key={item.evidence_id}
                      className="bg-white p-2 rounded border border-gray-200 text-[11px]"
                    >
                      <div className="flex items-center justify-between text-[10px] text-gray-500">
                        <span>{item.origin}</span>
                        <span>line {item.location?.start_line}</span>
                      </div>
                      <code className="block mt-1 text-[10px] text-teal-700 font-mono">
                        {item.excerpt ?? "Excerpt unavailable"}
                      </code>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Copy Actions */}
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                className="flex-1 py-1 px-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 flex items-center justify-center gap-1 text-[11px] cursor-pointer"
                onClick={() => navigator.clipboard?.writeText(node.qualified_name)}
              >
                <Copy size={11} />
                <span>Copy symbol</span>
              </button>
              <button
                type="button"
                className="flex-1 py-1 px-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 flex items-center justify-center gap-1 text-[11px] cursor-pointer"
                onClick={() =>
                  navigator.clipboard?.writeText(node.location?.path ?? "")
                }
              >
                <Copy size={11} />
                <span>Copy path</span>
              </button>
            </div>
          </>
        ) : edge ? (
          <div className="bg-white border border-gray-200 rounded p-3 shadow-xs space-y-2">
            <div className="text-[10px] uppercase font-bold text-teal-800 tracking-wider">
              Relationship Details
            </div>
            <div className="font-mono text-xs text-gray-900">{edge.kind}</div>
            <div className="text-[11px] text-gray-600">
              Status: <span className="font-mono font-medium">{edge.resolution_status}</span>
            </div>
          </div>
        ) : (
          <div className="p-4 text-center text-gray-500">
            <p className="font-medium text-gray-700">No symbol selected</p>
            <p className="mt-1 text-[11px]">
              Select a node in the graph or a symbol in the Project Explorer to inspect details.
            </p>
          </div>
        )}
      </div>
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
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [view, setView] = useState<"graph" | "table">("graph");
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [dockOpen, setDockOpen] = useState(true);
  const [dockTab, setDockTab] = useState<"shell" | "diagnostics">("shell");
  const [activeDiag, setActiveDiag] = useState<"all" | "error" | "warning">("all");

  activeSelection.current = `${analysisId}:${selectedNode?.id ?? ""}`;

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
        const matchesKind =
          kindFilter === "all" ||
          (node.kind || "").toLowerCase() === kindFilter.toLowerCase();
        return matchesSearch && matchesKind;
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
      edges: full.edges.filter(
        (e) => visible.has(e.source) && visible.has(e.target)
      ),
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
      await transport.navigate(
        node.location.path,
        node.location.start_line,
        node.location.start_column ?? undefined,
        session ?? undefined
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
    "my_project";

  const activeFileTab = useMemo(() => {
    if (selectedNode?.location?.path) {
      return selectedNode.location.path.split(/[\\/]/).pop() || "project.py";
    }
    return "project.py";
  }, [selectedNode]);

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-[#f0f0f0] text-gray-800 select-none">
      {error ? (
        <div role="alert" className="integration-alert">
          {error}
        </div>
      ) : null}
      <span className="sr-only" role="status">
        {status}
      </span>

      {/* BEGIN: OS Window Titlebar */}
      <header
        className="h-8 bg-white border-b border-gray-300 flex items-center justify-between px-3 text-xs select-none shrink-0"
        data-purpose="window-titlebar"
      >
        <div className="flex items-center space-x-2">
          <svg
            className="w-4 h-4 text-teal-600"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2.2"
            viewBox="0 0 24 24"
          >
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          <span className="font-medium text-gray-700 tracking-tight">
            Thonny - {currentProjectTitle}
          </span>
        </div>
        <div className="flex items-center space-x-3 text-gray-500">
          <button
            type="button"
            className="hover:text-black p-1 hover:bg-gray-100 transition-colors"
            title="Minimize"
          >
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 16 16">
              <path d="M2 8h12v1H2z" />
            </svg>
          </button>
          <button
            type="button"
            className="hover:text-black p-1 hover:bg-gray-100 transition-colors"
            title="Maximize"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.2"
              viewBox="0 0 16 16"
            >
              <rect height="11" width="11" x="2.5" y="2.5" />
            </svg>
          </button>
          <button
            type="button"
            className="hover:bg-red-500 hover:text-white p-1 transition-colors"
            title="Close"
          >
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 16 16">
              <path d="M3.7 3L3 3.7 7.3 8 3 12.3l.7.7L8 8.7l4.3 4.3.7-.7L8.7 8 13 3.7 12.3 3 8 7.3 3.7 3z" />
            </svg>
          </button>
        </div>
      </header>

      {/* BEGIN: Classic Desktop Menu Bar */}
      <nav
        className="h-6 bg-[#f0f0f0] border-b border-gray-300 flex items-center px-2 space-x-3 text-[12px] text-gray-800 select-none shrink-0"
        data-purpose="menubar"
      >
        <button type="button" className="px-1.5 hover:bg-blue-100 hover:text-blue-900 rounded">
          File
        </button>
        <button type="button" className="px-1.5 hover:bg-blue-100 hover:text-blue-900 rounded">
          Edit
        </button>
        <button type="button" className="px-1.5 hover:bg-blue-100 hover:text-blue-900 rounded">
          View
        </button>
        <button type="button" className="px-1.5 hover:bg-blue-100 hover:text-blue-900 rounded">
          Run
        </button>
        <div className="relative group">
          <button
            type="button"
            className="px-1.5 bg-blue-100 text-blue-900 font-medium rounded flex items-center gap-1"
          >
            Tools
          </button>
        </div>
        <button type="button" className="px-1.5 hover:bg-blue-100 hover:text-blue-900 rounded">
          Help
        </button>
      </nav>

      {/* BEGIN: Thonny Main Toolbar */}
      <div
        className="h-10 bg-[#f0f0f0] border-b border-gray-300 flex items-center px-2 space-x-1 select-none shrink-0"
        data-purpose="toolbar"
      >
        <button
          type="button"
          className="p-1.5 text-gray-600 hover:bg-gray-200 hover:text-gray-900 rounded"
          title="New file (Ctrl+N)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
            <polyline points="13 2 13 9 20 9" />
          </svg>
        </button>
        <button
          type="button"
          className="p-1.5 text-gray-600 hover:bg-gray-200 hover:text-gray-900 rounded"
          title="Open... (Ctrl+O)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
        </button>
        <button
          type="button"
          className="p-1.5 text-gray-600 hover:bg-gray-200 hover:text-gray-900 rounded"
          title="Save (Ctrl+S)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
            <polyline points="17 21 17 13 7 13 7 21" />
            <polyline points="7 3 7 8 15 8" />
          </svg>
        </button>

        <div className="h-5 w-px bg-gray-300 mx-1" />

        <button
          type="button"
          className="p-1.5 text-green-600 hover:bg-green-50 rounded"
          title="Run current script (F5)"
        >
          <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
        </button>
        <button
          type="button"
          className="p-1.5 text-yellow-600 hover:bg-yellow-50 rounded"
          title="Debug current script (Ctrl+F5)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83" />
            <circle cx="12" cy="12" r="5" />
          </svg>
        </button>
        <button
          type="button"
          className="p-1.5 text-red-500 hover:bg-red-50 rounded"
          title="Stop/Restart backend (Ctrl+F2)"
        >
          <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
            <rect height="14" rx="2" width="14" x="5" y="5" />
          </svg>
        </button>

        <div className="h-5 w-px bg-gray-300 mx-1" />

        {/* CodeStruct integrated Workbench Actions */}
        <button
          type="button"
          onClick={() => void openFolder()}
          disabled={busy}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold bg-teal-50 border border-teal-600 text-teal-800 rounded hover:bg-teal-100 shadow-xs transition-all cursor-pointer disabled:opacity-50"
          title="Open project folder in CodeStruct"
        >
          <FolderOpen className="w-3.5 h-3.5 text-teal-700" />
          <span>Open Folder</span>
        </button>

        <button
          type="button"
          onClick={() => void load(true)}
          disabled={busy || !projectId}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50 shadow-xs transition-all cursor-pointer disabled:opacity-50"
          title="Reanalyze project with CodeStruct"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", busy && "animate-spin text-teal-600")} />
          <span>Refresh</span>
        </button>

        {busy && job ? (
          <button
            type="button"
            onClick={() => void cancel()}
            className="px-2 py-1 text-xs font-medium bg-white border border-red-300 text-red-700 rounded hover:bg-red-50 cursor-pointer"
          >
            Cancel
          </button>
        ) : null}

        <div className="ml-auto flex items-center gap-2 px-2 text-xs text-gray-600">
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              busy ? "bg-amber-500 animate-pulse" : "bg-teal-600"
            )}
          />
          <span className="font-sans text-[11px] truncate max-w-[280px]">{status}</span>
        </div>
      </div>

      {/* BEGIN: Editor & Workbench Tab Strip */}
      <div
        className="h-7 bg-[#f0f0f0] flex items-end px-2 space-x-1 border-b border-gray-300 text-xs select-none shrink-0"
        data-purpose="tab-strip"
      >
        <div className="h-6 px-3 bg-gray-200 hover:bg-gray-100 text-gray-700 border-t border-x border-gray-300 rounded-t flex items-center space-x-2 cursor-pointer transition-colors">
          <FileCode2 className="w-3.5 h-3.5 text-gray-500" />
          <span className="font-mono text-[11px]">{activeFileTab}</span>
          <span className="text-gray-400 hover:text-gray-700 font-bold ml-1 text-[11px]">×</span>
        </div>
        <div className="h-7 px-3 bg-white text-teal-800 font-semibold border-t-2 border-t-teal-600 border-x border-gray-300 rounded-t flex items-center space-x-2 shadow-xs cursor-pointer">
          <svg
            className="w-3.5 h-3.5 text-teal-600"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            viewBox="0 0 24 24"
          >
            <rect height="7" width="7" x="3" y="3" />
            <rect height="7" width="7" x="14" y="3" />
            <rect height="7" width="7" x="14" y="14" />
            <rect height="7" width="7" x="3" y="14" />
          </svg>
          <span>CodeStruct Architecture</span>
          <span className="text-gray-400 hover:text-gray-700 font-bold ml-1 text-[11px]">×</span>
        </div>
      </div>

      {/* BEGIN: Main Multi-Panel Workspace */}
      <div className="flex-1 flex overflow-hidden bg-white relative">
        {/* LEFT PANEL: Project Explorer & Kind Filter */}
        <aside
          className={cn(
            "w-64 border-r border-gray-300 flex flex-col bg-gray-50 shrink-0 transition-all duration-150",
            !leftOpen && "hidden"
          )}
          data-purpose="left-panel-explorer"
        >
          {/* Explorer Header */}
          <div className="h-8 border-b border-gray-200 px-3 flex items-center justify-between text-xs font-semibold text-gray-700 bg-gray-100 shrink-0">
            <span className="uppercase tracking-wider text-[11px] font-bold text-gray-600">
              Project Explorer
            </span>
            <button
              type="button"
              className="text-gray-400 hover:text-gray-600 p-0.5 cursor-pointer"
              title="Collapse Explorer"
              aria-label="Collapse project sidebar"
              onClick={() => setLeftOpen(false)}
            >
              <PanelLeftClose size={14} />
            </button>
          </div>

          {/* Search Input */}
          <div className="p-2 border-b border-gray-200 bg-white shrink-0">
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-2 flex items-center pointer-events-none text-gray-400">
                <Search size={13} />
              </span>
              <input
                className="w-full text-xs pl-7 pr-6 py-1 border border-gray-300 rounded bg-gray-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-teal-600 font-sans"
                placeholder="Search files & symbols..."
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              {search ? (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute inset-y-0 right-0 pr-2 flex items-center text-gray-400 hover:text-gray-600"
                >
                  <X size={12} />
                </button>
              ) : null}
            </div>
          </div>

          {/* Symbol Tree */}
          <div
            className="flex-1 overflow-y-auto py-1 text-xs select-none space-y-0.5 font-sans"
            data-purpose="symbol-tree"
          >
            <ProjectExplorerTree
              treeResult={tree}
              search={search}
              kindFilter={kindFilter}
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

          {/* Bottom Kind Filter Bar */}
          <div
            className="border-t border-gray-300 p-2 bg-gray-100 shrink-0"
            data-purpose="kind-filter-bar"
          >
            <div className="text-[10px] uppercase font-bold text-gray-500 mb-1.5 flex items-center justify-between">
              <span>Kind Filter</span>
              {kindFilter !== "all" ? (
                <button
                  type="button"
                  className="text-teal-700 hover:underline normal-case text-[10px] font-normal cursor-pointer"
                  onClick={() => setKindFilter("all")}
                >
                  Reset
                </button>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-1">
              {[
                { id: "all", label: "All kinds" },
                { id: "module", label: "Module" },
                { id: "class", label: "Class" },
                { id: "function", label: "Function" },
                { id: "method", label: "Method" },
              ].map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setKindFilter(item.id)}
                  className={cn(
                    "px-2 py-0.5 rounded text-[11px] font-medium transition-colors cursor-pointer",
                    kindFilter === item.id
                      ? "bg-teal-600 text-white shadow-xs"
                      : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {!leftOpen ? (
          <button
            type="button"
            className="absolute left-2 top-2 z-20 p-1.5 bg-white border border-gray-300 rounded shadow-xs hover:bg-gray-50 text-gray-600 cursor-pointer"
            onClick={() => setLeftOpen(true)}
            aria-label="Open project sidebar"
            title="Open Project Explorer"
          >
            <PanelLeftOpen size={14} />
          </button>
        ) : null}

        {/* CENTER PANEL: Interactive Architecture Graph / Table */}
        <section
          className="flex-1 flex flex-col relative overflow-hidden bg-white"
          data-purpose="center-panel-graph"
        >
          {/* Graph Top Action Bar */}
          <div className="h-8 bg-white border-b border-gray-200 px-3 flex items-center justify-between text-xs select-none shrink-0">
            {/* View Mode Switcher */}
            <div className="flex items-center space-x-1">
              <button
                type="button"
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 text-xs cursor-pointer transition-colors",
                  view === "graph"
                    ? "bg-teal-50 border-b-2 border-teal-600 text-teal-800 font-semibold"
                    : "text-gray-500 hover:text-gray-800"
                )}
                onClick={() => setView("graph")}
              >
                <Network size={13} />
                <span>Graph</span>
              </button>
              <button
                type="button"
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 text-xs cursor-pointer transition-colors",
                  view === "table"
                    ? "bg-teal-50 border-b-2 border-teal-600 text-teal-800 font-semibold"
                    : "text-gray-500 hover:text-gray-800"
                )}
                onClick={() => setView("table")}
              >
                <Table2 size={13} />
                <span>Accessible table</span>
              </button>
            </div>

            {/* Node Status & Export Tooling */}
            <div className="flex items-center space-x-2">
              <span className="text-gray-600 text-[11px] font-medium bg-gray-100 px-2 py-0.5 rounded border border-gray-200">
                <strong className="text-teal-700">{filteredNodes.length}</strong> nodes loaded
              </span>
              <div className="flex items-center space-x-1">
                <button
                  type="button"
                  className="flex items-center gap-1 px-2 py-0.5 border border-gray-300 rounded hover:bg-gray-50 text-[11px] font-medium text-gray-700 cursor-pointer disabled:opacity-50"
                  disabled={!graph}
                  onClick={() => downloadSliceDot()}
                  title="Export currently loaded nodes and edges as DOT"
                  aria-label="Export DOT (Loaded Slice)"
                >
                  <Download size={11} className="text-gray-500" />
                  <span>DOT (Slice)</span>
                </button>
                <button
                  type="button"
                  className="flex items-center gap-1 px-2 py-0.5 border border-gray-300 rounded hover:bg-gray-50 text-[11px] font-medium text-gray-700 cursor-pointer disabled:opacity-50"
                  disabled={!graph || !analysisId}
                  onClick={() => void downloadCompleteDot()}
                  title="Export complete server-side graph as DOT"
                  aria-label="Export DOT (Complete Graph)"
                >
                  <Download size={11} className="text-gray-500" />
                  <span>DOT (Complete)</span>
                </button>
                <button
                  type="button"
                  className="p-1 border border-gray-300 rounded hover:bg-gray-50 text-gray-600 cursor-pointer"
                  title="Toggle Fullscreen"
                  aria-label="Toggle Fullscreen"
                  onClick={() => {
                    const action = document.fullscreenElement
                      ? document.exitFullscreen?.()
                      : document.documentElement.requestFullscreen?.();
                    void action?.catch((err) => setError(err.message));
                  }}
                >
                  <Maximize2 size={13} />
                </button>
                {!rightOpen ? (
                  <button
                    type="button"
                    className="p-1 border border-gray-300 rounded hover:bg-gray-50 text-gray-600 cursor-pointer"
                    title="Open Inspector"
                    aria-label="Open Inspector"
                    onClick={() => setRightOpen(true)}
                  >
                    <PanelRightOpen size={13} />
                  </button>
                ) : null}
              </div>
            </div>
          </div>

          {/* Canvas Viewport */}
          {view === "graph" ? (
            <div
              className="flex-1 graph-grid-bg relative overflow-hidden flex items-center justify-center"
              data-purpose="graph-viewport"
            >
              {!graph ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center z-10">
                  <div className="p-3 bg-white border border-gray-300 rounded-lg shadow-xs max-w-sm">
                    <FolderOpen className="w-8 h-8 text-teal-600 mx-auto mb-2" />
                    <p className="font-semibold text-gray-800 text-sm">No Architecture Loaded</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {busy
                        ? status
                        : "Click 'Open Folder' in the top toolbar to open and analyze a Python project."}
                    </p>
                  </div>
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
                  fitViewOptions={{ padding: 0.2 }}
                  minZoom={0.25}
                  maxZoom={1.5}
                  proOptions={{ hideAttribution: true }}
                >
                  <Background color="#d1d5db" gap={20} size={1} />
                  <Controls showInteractive={false} />
                  <MiniMap
                    nodeColor={(node) => {
                      const k = (
                        node.data?.node as GraphNode | undefined
                      )?.kind?.toLowerCase();
                      if (k === "class") return "#16a34a";
                      if (k === "function") return "#d97706";
                      if (k === "method") return "#0284c7";
                      return "#0d9488";
                    }}
                    maskColor="rgba(240, 240, 240, 0.7)"
                  />
                </ReactFlow>
              </ReactFlowProvider>

              {graph?.partial_load ? (
                <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-white border border-amber-300 rounded shadow-md px-3 py-1.5 flex items-center gap-2 z-20 text-xs">
                  <span className="text-amber-800">
                    Partial graph loaded ({filteredNodes.length} of {graph.summary.nodes_total}{" "}
                    nodes).
                  </span>
                  <button
                    type="button"
                    className="px-2 py-0.5 bg-teal-600 text-white rounded text-[11px] font-medium"
                    disabled={paging || !graph.page?.next_cursor}
                    onClick={() => void loadMore()}
                  >
                    {paging ? "Loading…" : "Load more"}
                  </button>
                </div>
              ) : null}

              {/* Bottom Integrated Legend */}
              <div
                className="absolute bottom-2 left-3 bg-white/95 backdrop-blur-xs border border-gray-300 shadow-sm px-3 py-1.5 rounded-full flex items-center space-x-3 text-[11px] text-gray-700 z-30"
                data-purpose="graph-legend"
              >
                <span className="font-bold text-[10px] uppercase text-gray-400 tracking-wider">
                  Legend
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-700 inline-block" />
                  <span>Project</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-cyan-600 inline-block" />
                  <span>Package</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm bg-teal-600 inline-block" />
                  <span>Module</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm bg-green-600 inline-block" />
                  <span>Class</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />
                  <span>Function</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-sky-500 inline-block" />
                  <span>Method</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-4 h-0.5 bg-teal-600 inline-block" />
                  <span className="text-teal-700 font-medium">defines</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-auto p-4 bg-white">
              <div className="border border-gray-200 rounded overflow-hidden">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-gray-100 border-b border-gray-200 text-gray-600 uppercase text-[10px] font-bold">
                      <th className="p-2">Symbol</th>
                      <th className="p-2">Kind</th>
                      <th className="p-2">Source</th>
                      <th className="p-2">Coordinates</th>
                      <th className="p-2">Evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 font-mono">
                    {filteredNodes.map((node) => (
                      <tr
                        key={node.id}
                        tabIndex={0}
                        className={cn(
                          "hover:bg-teal-50/50 cursor-pointer transition-colors",
                          selectedNode?.id === node.id && "bg-teal-50 font-semibold"
                        )}
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
                        <td className="p-2 font-medium text-gray-900">
                          <span className="flex items-center gap-1.5">
                            <span
                              className={cn(
                                "w-2 h-2 rounded-full",
                                node.kind === "class"
                                  ? "bg-green-600"
                                  : node.kind === "function"
                                  ? "bg-amber-500"
                                  : node.kind === "method"
                                  ? "bg-sky-500"
                                  : "bg-teal-600"
                              )}
                            />
                            <span>{node.name}</span>
                          </span>
                        </td>
                        <td className="p-2 text-gray-600 capitalize">{node.kind}</td>
                        <td className="p-2 text-gray-500 truncate max-w-[200px]">
                          {node.location?.path ?? "Unavailable"}
                        </td>
                        <td className="p-2 text-gray-500">
                          {node.location?.start_line
                            ? `${node.location.start_line}:${node.location.start_column ?? 0}`
                            : "Unavailable"}
                        </td>
                        <td className="p-2 text-gray-500">
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
        </section>

        {/* RIGHT PANEL: Inspector */}
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
            editorAvailable={Boolean(session) || transport.mode === "demo"}
            onClose={() => setRightOpen(false)}
            onExplain={() => void onExplain()}
            explanation={explanation}
            onNavigate={(node) => void openEditor(node)}
          />
        ) : null}
      </div>

      {/* BEGIN: Bottom Thonny Docked Panels (Shell & Diagnostics) */}
      <section
        className={cn(
          "border-t-2 border-gray-300 bg-white flex flex-col shrink-0 transition-all duration-150",
          dockOpen ? "h-36" : "h-7"
        )}
        data-purpose="docked-bottom-panels"
      >
        {/* Dock Panel Tabs */}
        <div className="h-6.5 bg-[#f0f0f0] flex items-center justify-between px-2 border-b border-gray-300 text-xs shrink-0 select-none">
          <div className="flex items-center space-x-1 h-full">
            <button
              type="button"
              onClick={() => {
                setDockTab("shell");
                setDockOpen(true);
              }}
              className={cn(
                "px-3 h-full flex items-center gap-1 cursor-pointer font-medium text-xs border-x",
                dockTab === "shell" && dockOpen
                  ? "bg-white border-t-2 border-t-teal-700 border-x-gray-300 font-semibold text-gray-800"
                  : "text-gray-600 hover:text-gray-900 border-transparent"
              )}
            >
              <span>Shell</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setDockTab("diagnostics");
                setDockOpen(true);
              }}
              className={cn(
                "px-3 h-full flex items-center gap-1.5 cursor-pointer font-medium text-xs border-x",
                dockTab === "diagnostics" && dockOpen
                  ? "bg-white border-t-2 border-t-teal-700 border-x-gray-300 font-semibold text-gray-800"
                  : "text-gray-600 hover:text-gray-900 border-transparent"
              )}
            >
              <span>Diagnostics</span>
              <span className="bg-teal-100 text-teal-800 text-[10px] font-bold px-1.5 py-0.2 rounded-full">
                {diagnostics.length}
              </span>
            </button>
          </div>

          <button
            type="button"
            className="text-gray-500 hover:text-gray-800 text-[11px] px-1 cursor-pointer"
            onClick={() => setDockOpen((v) => !v)}
            title={dockOpen ? "Minimize Panel" : "Restore Panel"}
          >
            {dockOpen ? "▼ Minimize" : "▲ Restore"}
          </button>
        </div>

        {/* Panel Content */}
        {dockOpen ? (
          dockTab === "shell" ? (
            <div
              className="flex-1 p-2 font-mono text-xs overflow-y-auto leading-relaxed bg-white text-gray-900 select-text"
              data-purpose="thonny-shell-output"
            >
              <div className="text-purple-700 font-semibold tracking-tight">
                &gt;&gt;&gt; %Run -c $CODESTRUCT_WORKBENCH
              </div>
              <div className="text-gray-700 pl-4 py-0.5">
                <div>[Thonny] Initializing local Python 3 interpreter environment...</div>
                <div>[CodeStruct] Initialized Architecture Analyzer adapter v2.4</div>
              </div>
              {graph ? (
                <>
                  <div className="text-purple-700 font-semibold tracking-tight mt-1">
                    &gt;&gt;&gt; Analyze with CodeStruct: Processed {graph.nodes.length} symbols
                  </div>
                  <div className="text-teal-800 font-semibold pl-4">
                    <div>
                      ✓ AST parse complete: {graph.nodes.filter((n) => n.kind === "module").length}{" "}
                      Module(s), {graph.nodes.filter((n) => n.kind === "class").length} Class(es),{" "}
                      {graph.nodes.filter((n) => n.kind === "function").length} Function(s),{" "}
                      {graph.nodes.filter((n) => n.kind === "method").length} Method(s) discovered.
                    </div>
                    <div>
                      ✓ CodeStruct architecture graph generated successfully. Workbench synchronized.
                    </div>
                  </div>
                </>
              ) : null}
              <div className="flex items-center text-purple-700 font-semibold mt-1">
                <span>&gt;&gt;&gt;&nbsp;</span>
                <span className="w-2 h-3.5 bg-gray-800 inline-block animate-pulse" />
              </div>
            </div>
          ) : (
            <div className="flex-1 p-2 overflow-y-auto text-xs bg-white space-y-2">
              <div className="flex items-center gap-2 pb-1 border-b border-gray-200">
                {(["all", "error", "warning"] as const).map((sev) => (
                  <button
                    key={sev}
                    type="button"
                    onClick={() => setActiveDiag(sev)}
                    className={cn(
                      "px-2 py-0.5 rounded text-[11px] cursor-pointer",
                      activeDiag === sev
                        ? "bg-teal-600 text-white font-medium"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    {sev === "all" ? "All" : sev === "error" ? "Errors" : "Warnings"} (
                    {sev === "all"
                      ? diagnostics.length
                      : diagnostics.filter((d) => d.severity === sev).length}
                    )
                  </button>
                ))}
              </div>
              {shownDiagnostics.length > 0 ? (
                <div className="space-y-1">
                  {shownDiagnostics.map((d) => (
                    <div
                      key={d.id}
                      className="p-1.5 rounded border border-gray-200 bg-gray-50 flex items-start gap-2"
                    >
                      <span
                        className={cn(
                          "w-2 h-2 rounded-full mt-1 shrink-0",
                          d.severity === "error" ? "bg-red-500" : "bg-amber-500"
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <code className="font-bold text-gray-900">{d.code}</code>
                          <span className="text-[10px] text-gray-500 font-mono">
                            {d.location ? `${d.location.path}:${d.location.start_line}` : "global"}
                          </span>
                        </div>
                        <p className="text-gray-700 mt-0.5">{d.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400 py-2">No diagnostics in this filter.</p>
              )}
            </div>
          )
        ) : null}
      </section>

      {/* BEGIN: Status Bar */}
      <footer
        className="h-6 bg-[#f0f0f0] border-t border-gray-300 px-3 flex items-center justify-between text-[11px] text-gray-600 select-none shrink-0"
        data-purpose="system-statusbar"
      >
        <div className="flex items-center space-x-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span>Local Python 3 • Connected to local adapter</span>
          </span>
          <span className="text-gray-400">|</span>
          <span>
            Encoding: <strong className="text-gray-700">UTF-8</strong>
          </span>
        </div>
        <div className="flex items-center space-x-4">
          <span>
            {selectedNode?.location?.start_line
              ? `Line ${selectedNode.location.start_line}, Col ${
                  selectedNode.location.start_column ?? 1
                }`
              : "Line 1, Col 1"}
          </span>
          <span className="text-gray-400">|</span>
          <span className="text-teal-700 font-medium">CodeStruct Workbench Active</span>
        </div>
      </footer>
    </div>
  );
}
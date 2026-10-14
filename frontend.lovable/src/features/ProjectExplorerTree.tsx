import { useState, useMemo } from "react";
import { ChevronDown, ChevronRight, Folder, FolderOpen, AlertTriangle } from "lucide-react";
import type { TreeNode, TreeResult } from "./types";
import { cn } from "@/lib/utils";

interface ProjectExplorerTreeProps {
  treeResult: TreeResult | null;
  search: string;
  selectedNodeId: string | null;
  kindFilter?: string;
  onSelectSymbol: (symbolId: string, qname: string) => void;
}

function matchesSearch(node: TreeNode, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  if (
    node.name.toLowerCase().includes(q) ||
    (node.qualified_name && node.qualified_name.toLowerCase().includes(q))
  ) {
    return true;
  }
  if (node.children?.some((c) => matchesSearch(c, query))) return true;
  if (node.symbols?.some((s) => matchesSearch(s, query))) return true;
  return false;
}

function matchesKind(node: TreeNode, filter: string | undefined): boolean {
  if (!filter || filter === "all") return true;
  const target = filter.toLowerCase();
  const k = (node.kind || "").toLowerCase();
  if (k === target) return true;
  if (node.children?.some((c) => matchesKind(c, filter))) return true;
  if (node.symbols?.some((s) => matchesKind(s, filter))) return true;
  return false;
}

function SymbolBadge({ kind }: { kind: string }) {
  const k = kind.toLowerCase();
  if (k === "class") {
    return (
      <span className="text-[10px] font-bold text-green-700 font-mono bg-green-100 px-1 rounded shrink-0">
        C
      </span>
    );
  }
  if (k === "method") {
    return (
      <span className="text-[10px] font-bold text-blue-600 font-mono px-0.5 shrink-0">
        m
      </span>
    );
  }
  if (k === "function") {
    return (
      <span className="text-[10px] font-bold text-amber-600 font-mono bg-amber-100 px-1 rounded shrink-0">
        f
      </span>
    );
  }
  return (
    <span className="w-2 h-2 rounded-sm bg-teal-600 inline-block shrink-0" />
  );
}

function SymbolItem({
  symbol,
  search,
  kindFilter,
  selectedNodeId,
  onSelectSymbol,
}: {
  symbol: TreeNode;
  search: string;
  kindFilter?: string;
  selectedNodeId: string | null;
  onSelectSymbol: (symbolId: string, qname: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const hasChildren = Boolean(symbol.children && symbol.children.length > 0);
  const isSelected = selectedNodeId === symbol.id;

  if (kindFilter && kindFilter !== "all" && !matchesKind(symbol, kindFilter)) {
    return null;
  }

  return (
    <div className="pl-3">
      <div
        className={cn(
          "flex items-center gap-1.5 py-0.5 px-1.5 rounded cursor-pointer text-xs select-none hover:bg-gray-100 transition-colors text-gray-700",
          isSelected &&
            "bg-teal-50 text-teal-900 font-semibold border-l-2 border-teal-600 pl-1"
        )}
        onClick={() =>
          onSelectSymbol(symbol.id, symbol.qualified_name || symbol.name)
        }
      >
        {hasChildren ? (
          <button
            type="button"
            className="p-0.5 hover:bg-gray-200 rounded text-gray-500"
            onClick={(e) => {
              e.stopPropagation();
              setOpen((v) => !v);
            }}
            aria-label={open ? "Collapse symbol" : "Expand symbol"}
          >
            {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </button>
        ) : (
          <span className="w-3" />
        )}
        <SymbolBadge kind={symbol.kind} />
        <span className="truncate flex-1 font-mono">{symbol.name}</span>
        {symbol.line ? (
          <span className="text-[10px] text-gray-400 font-mono ml-auto">
            L{symbol.line}
          </span>
        ) : null}
      </div>

      {hasChildren && open ? (
        <div className="border-l border-gray-200 ml-2">
          {symbol.children
            ?.filter((c) => matchesSearch(c, search))
            .filter((c) => matchesKind(c, kindFilter))
            .map((child) => (
              <SymbolItem
                key={child.id}
                symbol={child}
                search={search}
                kindFilter={kindFilter}
                selectedNodeId={selectedNodeId}
                onSelectSymbol={onSelectSymbol}
              />
            ))}
        </div>
      ) : null}
    </div>
  );
}

function TreeDirectoryItem({
  node,
  search,
  kindFilter,
  selectedNodeId,
  onSelectSymbol,
  depth = 0,
}: {
  node: TreeNode;
  search: string;
  kindFilter?: string;
  selectedNodeId: string | null;
  onSelectSymbol: (symbolId: string, qname: string) => void;
  depth?: number;
}) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = node.kind === "directory";

  if (search && !matchesSearch(node, search)) {
    return null;
  }
  if (kindFilter && kindFilter !== "all" && !matchesKind(node, kindFilter)) {
    return null;
  }

  if (isDir) {
    return (
      <div className={depth > 0 ? "pl-2" : ""}>
        <div
          className="flex items-center gap-1.5 py-0.5 px-1.5 rounded cursor-pointer text-xs font-medium select-none hover:bg-gray-100 text-gray-800"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          {open ? (
            <ChevronDown size={12} className="text-gray-500 shrink-0" />
          ) : (
            <ChevronRight size={12} className="text-gray-500 shrink-0" />
          )}
          {open ? (
            <FolderOpen size={13} className="text-amber-500 shrink-0" />
          ) : (
            <Folder size={13} className="text-amber-500 shrink-0" />
          )}
          <span className="truncate">{node.name}</span>
        </div>

        {open && node.children ? (
          <div className="border-l border-gray-200 ml-2">
            {node.children
              .filter((child) => matchesSearch(child, search))
              .filter((child) => matchesKind(child, kindFilter))
              .map((child) => (
                <TreeDirectoryItem
                  key={child.id}
                  node={child}
                  search={search}
                  kindFilter={kindFilter}
                  selectedNodeId={selectedNodeId}
                  onSelectSymbol={onSelectSymbol}
                  depth={depth + 1}
                />
              ))}
          </div>
        ) : null}
      </div>
    );
  }

  // File item
  const hasSymbols = Boolean(node.symbols && node.symbols.length > 0);
  const isSelected = selectedNodeId === node.id;

  return (
    <div className="pl-2">
      <div
        className={cn(
          "flex items-center gap-1.5 py-0.5 px-1.5 rounded cursor-pointer text-xs select-none hover:bg-gray-100 text-gray-700 transition-colors",
          isSelected &&
            "bg-teal-50 text-teal-900 font-semibold border-l-2 border-teal-600 pl-1"
        )}
        onClick={() => onSelectSymbol(node.id, node.name)}
      >
        <span className="w-2.5 h-2.5 rounded-sm bg-teal-600 inline-block shrink-0" />
        <span className="truncate font-mono">{node.name}</span>
      </div>

      {hasSymbols ? (
        <div className="border-l border-gray-200 ml-2">
          {node.symbols
            ?.filter((s) => matchesSearch(s, search))
            .filter((s) => matchesKind(s, kindFilter))
            .map((sym) => (
              <SymbolItem
                key={sym.id}
                symbol={sym}
                search={search}
                kindFilter={kindFilter}
                selectedNodeId={selectedNodeId}
                onSelectSymbol={onSelectSymbol}
              />
            ))}
        </div>
      ) : null}
    </div>
  );
}

export function ProjectExplorerTree({
  treeResult,
  search,
  kindFilter,
  selectedNodeId,
  onSelectSymbol,
}: ProjectExplorerTreeProps) {
  const root = treeResult?.tree;
  const excluded = useMemo(() => treeResult?.excluded ?? [], [treeResult]);

  if (!root) {
    return (
      <div className="p-4 text-xs text-gray-500">
        <p className="font-medium text-gray-700">No project tree loaded.</p>
        <p className="mt-1 text-[11px] text-gray-500">
          Click "Open Folder" in the toolbar to open and analyze a local Python project.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-0.5 py-1 text-xs select-none font-sans">
      <TreeDirectoryItem
        node={root}
        search={search}
        kindFilter={kindFilter}
        selectedNodeId={selectedNodeId}
        onSelectSymbol={onSelectSymbol}
      />

      {excluded.length > 0 ? (
        <div className="mt-4 pt-3 border-t border-gray-200 px-2">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-gray-600 mb-1.5">
            <AlertTriangle size={12} className="text-amber-500" />
            <span>Policy Exclusions ({excluded.length})</span>
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {excluded.map((exc) => (
              <div
                key={exc.path}
                className="text-[10px] text-gray-500 leading-tight"
                title={exc.reason}
              >
                <span className="font-mono text-gray-700">{exc.path}</span>: {exc.reason}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

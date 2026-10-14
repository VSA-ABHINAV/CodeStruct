import { useState, useMemo } from "react";
import { ChevronDown, ChevronRight, FileCode2, Folder, FolderOpen, Box, Code2, AlertTriangle } from "lucide-react";
import type { TreeNode, TreeResult } from "./types";
import { cn } from "@/lib/utils";

interface ProjectExplorerTreeProps {
  treeResult: TreeResult | null;
  search: string;
  selectedNodeId: string | null;
  onSelectSymbol: (symbolId: string, qname: string) => void;
}

function matchesSearch(node: TreeNode, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  if (node.name.toLowerCase().includes(q) || (node.qualified_name && node.qualified_name.toLowerCase().includes(q))) {
    return true;
  }
  if (node.children?.some((c) => matchesSearch(c, query))) return true;
  if (node.symbols?.some((s) => matchesSearch(s, query))) return true;
  return false;
}

function SymbolItem({
  symbol,
  search,
  selectedNodeId,
  onSelectSymbol,
}: {
  symbol: TreeNode;
  search: string;
  selectedNodeId: string | null;
  onSelectSymbol: (symbolId: string, qname: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const hasChildren = Boolean(symbol.children && symbol.children.length > 0);
  const isSelected = selectedNodeId === symbol.id;

  const Icon = symbol.kind === "class" ? Box : symbol.kind === "module" ? FileCode2 : Code2;

  return (
    <div className="pl-3">
      <div
        className={cn(
          "flex items-center gap-1.5 py-1 px-1.5 rounded cursor-pointer text-xs font-mono select-none hover:bg-accent/50",
          isSelected && "bg-accent font-semibold text-accent-foreground"
        )}
        onClick={() => onSelectSymbol(symbol.id, symbol.qualified_name || symbol.name)}
      >
        {hasChildren ? (
          <button
            type="button"
            className="p-0.5 hover:bg-muted rounded"
            onClick={(e) => {
              e.stopPropagation();
              setOpen((v) => !v);
            }}
            aria-label={open ? "Collapse symbol" : "Expand symbol"}
          >
            {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </button>
        ) : (
          <span className="w-3" />
        )}
        <Icon size={13} className={cn("shrink-0", symbol.kind === "class" ? "text-blue-400" : symbol.kind === "method" ? "text-amber-300" : "text-emerald-400")} />
        <span className="truncate flex-1">{symbol.name}</span>
        {symbol.line ? <span className="text-[10px] text-muted-foreground ml-auto">:{symbol.line}</span> : null}
      </div>

      {hasChildren && open ? (
        <div className="border-l border-border/40 ml-2">
          {symbol.children?.filter((c) => matchesSearch(c, search)).map((child) => (
            <SymbolItem
              key={child.id}
              symbol={child}
              search={search}
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
  selectedNodeId,
  onSelectSymbol,
  depth = 0,
}: {
  node: TreeNode;
  search: string;
  selectedNodeId: string | null;
  onSelectSymbol: (symbolId: string, qname: string) => void;
  depth?: number;
}) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = node.kind === "directory";

  if (search && !matchesSearch(node, search)) {
    return null;
  }

  if (isDir) {
    return (
      <div className={depth > 0 ? "pl-2" : ""}>
        <div
          className="flex items-center gap-1.5 py-1 px-1.5 rounded cursor-pointer text-xs font-medium select-none hover:bg-accent/40 text-foreground"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          {open ? <ChevronDown size={13} className="text-muted-foreground shrink-0" /> : <ChevronRight size={13} className="text-muted-foreground shrink-0" />}
          {open ? <FolderOpen size={14} className="text-amber-400 shrink-0" /> : <Folder size={14} className="text-amber-400 shrink-0" />}
          <span className="truncate font-sans">{node.name}</span>
        </div>

        {open && node.children ? (
          <div className="border-l border-border/40 ml-2">
            {node.children.map((child) => (
              <TreeDirectoryItem
                key={child.id}
                node={child}
                search={search}
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
  const isPython = node.extension === ".py" || node.extension === ".pyi";
  const hasSymbols = Boolean(node.symbols && node.symbols.length > 0);

  return (
    <div className="pl-2">
      <div
        className="flex items-center gap-1.5 py-1 px-1.5 rounded cursor-pointer text-xs font-mono select-none hover:bg-accent/40 text-muted-foreground hover:text-foreground"
        onClick={() => onSelectSymbol(node.id, node.name)}
      >
        <span className="w-3" />
        <FileCode2 size={13} className={isPython ? "text-cyan-400 shrink-0" : "text-muted-foreground shrink-0"} />
        <span className="truncate">{node.name}</span>
      </div>

      {hasSymbols ? (
        <div className="border-l border-border/30 ml-2">
          {node.symbols?.filter((s) => matchesSearch(s, search)).map((sym) => (
            <SymbolItem
              key={sym.id}
              symbol={sym}
              search={search}
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
  selectedNodeId,
  onSelectSymbol,
}: ProjectExplorerTreeProps) {
  const root = treeResult?.tree;
  const excluded = useMemo(() => treeResult?.excluded ?? [], [treeResult]);

  if (!root) {
    return (
      <div className="p-4 text-xs text-muted-foreground">
        <p>No project tree loaded.</p>
        <p className="mt-1 text-[11px]">Click "Open Folder" to open a local project.</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <TreeDirectoryItem
        node={root}
        search={search}
        selectedNodeId={selectedNodeId}
        onSelectSymbol={onSelectSymbol}
      />

      {excluded.length > 0 ? (
        <div className="mt-4 pt-3 border-t border-border/40 px-2">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground mb-1.5">
            <AlertTriangle size={12} className="text-amber-500" />
            <span>Policy Exclusions ({excluded.length})</span>
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {excluded.map((exc) => (
              <div key={exc.path} className="text-[10px] text-muted-foreground leading-tight" title={exc.reason}>
                <span className="font-mono text-foreground/80">{exc.path}</span>: {exc.reason}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

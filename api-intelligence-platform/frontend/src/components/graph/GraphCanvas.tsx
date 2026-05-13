"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import type { GraphData, GraphNode } from "@/types";

interface GraphCanvasProps {
  data: GraphData;
  onNodeSelect?: (node: GraphNode) => void;
  fitViewTrigger?: number;
}

const TYPE_COLORS: Record<string, string> = {
  api: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300",
  auth: "border-rose-500/30 bg-rose-500/10 text-rose-300",
  bank: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  psp: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  flow: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  gateway: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  external: "border-slate-500/30 bg-slate-500/10 text-slate-300",
};

export default function GraphCanvas({
  data,
  onNodeSelect,
}: GraphCanvasProps) {
  const edgesByNode = useMemo(() => {
    const map = new Map<string, number>();
    for (const edge of data.edges) {
      map.set(edge.source, (map.get(edge.source) ?? 0) + 1);
      map.set(edge.target, (map.get(edge.target) ?? 0) + 1);
    }
    return map;
  }, [data.edges]);

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">
            Dependency Overview
          </h2>
          <p className="text-xs text-slate-500">
            {data.nodes.length} nodes and {data.edges.length} relationships
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {data.nodes.map((node) => (
          <button
            key={node.id}
            type="button"
            onClick={() => onNodeSelect?.(node)}
            className={cn(
              "rounded-xl border p-4 text-left transition-colors hover:border-slate-600",
              TYPE_COLORS[node.type] ??
                "border-slate-700 bg-slate-900 text-slate-200"
            )}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold">{node.label}</p>
                <p className="mt-1 text-xs capitalize opacity-80">
                  {node.type}
                </p>
              </div>
              <span className="rounded-full bg-slate-950/40 px-2 py-1 text-xs text-slate-300">
                {edgesByNode.get(node.id) ?? 0} links
              </span>
            </div>
          </button>
        ))}
      </div>

      <div className="mt-6 rounded-xl border border-slate-800 bg-slate-950 p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-200">
          Relationships
        </h3>
        <div className="space-y-2">
          {data.edges.map((edge) => (
            <div
              key={edge.id}
              className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-400"
            >
              <span className="truncate">
                {edge.source}
                {" -> "}
                {edge.target}
              </span>
              <span className="ml-3 rounded bg-slate-800 px-2 py-0.5 text-slate-300">
                {edge.label ?? edge.relationship_type}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

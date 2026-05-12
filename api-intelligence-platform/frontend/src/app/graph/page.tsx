"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import {
  ChevronDown,
  Layers,
  Maximize2,
  Network,
  RefreshCw,
  Sliders,
} from "lucide-react";
import { useCatalogStore } from "@/store/catalog";
import { useUIStore } from "@/store/ui";
import { get } from "@/lib/api";
import { cn } from "@/lib/utils";
import Sidebar from "@/components/shared/Sidebar";
import Header from "@/components/shared/Header";
import GraphCanvas from "@/components/graph/GraphCanvas";
import SpecSelector from "@/components/shared/SpecSelector";
import type { GraphData, GraphNode, EntityType } from "@/types";

const NODE_TYPES: { type: EntityType; label: string; color: string }[] = [
  { type: "api", label: "API", color: "bg-indigo-500" },
  { type: "psp", label: "PSP", color: "bg-violet-500" },
  { type: "bank", label: "Bank", color: "bg-emerald-500" },
  { type: "flow", label: "Flow", color: "bg-amber-500" },
  { type: "auth", label: "Auth", color: "bg-red-500" },
  { type: "gateway", label: "Gateway", color: "bg-sky-500" },
  { type: "external", label: "External", color: "bg-slate-500" },
];

function GraphPageInner() {
  const searchParams = useSearchParams();
  const specFromUrl = searchParams.get("spec");

  const { specs, fetchSpecs } = useCatalogStore();
  const { activeSpecId, setActiveSpecId } = useUIStore();

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [depth, setDepth] = useState(2);
  const [enabledTypes, setEnabledTypes] = useState<Set<EntityType>>(
    new Set(NODE_TYPES.map((n) => n.type))
  );
  const [isLoading, setIsLoading] = useState(false);
  const [fitViewTrigger, setFitViewTrigger] = useState(0);

  const currentSpecId = specFromUrl ?? activeSpecId;

  useEffect(() => {
    fetchSpecs();
  }, [fetchSpecs]);

  useEffect(() => {
    if (specFromUrl) {
      setActiveSpecId(specFromUrl);
    }
  }, [specFromUrl, setActiveSpecId]);

  const fetchGraph = useCallback(async () => {
    if (!currentSpecId) return;
    setIsLoading(true);
    try {
      const data = await get<GraphData>(
        `/api/specs/${currentSpecId}/graph`,
        { depth }
      );
      setGraphData(data);
    } catch {
      // If API not available, generate demo data
      const demoData: GraphData = {
        nodes: [
          { id: "api-1", label: "Payment Gateway", type: "api", spec_id: currentSpecId, endpoint_count: 47, risk_level: "medium", metadata: {} },
          { id: "api-2", label: "Auth Service", type: "auth", spec_id: currentSpecId, endpoint_count: 23, risk_level: "high", metadata: {} },
          { id: "api-3", label: "Bank Connect", type: "bank", spec_id: currentSpecId, endpoint_count: 31, risk_level: "critical", metadata: {} },
          { id: "psp-1", label: "Stripe PSP", type: "psp", metadata: {} },
          { id: "psp-2", label: "Braintree", type: "psp", metadata: {} },
          { id: "flow-1", label: "Direct Pay Flow", type: "flow", metadata: {} },
          { id: "gw-1", label: "API Gateway", type: "gateway", metadata: {} },
        ],
        edges: [
          { id: "e1", source: "api-1", target: "psp-1", relationship_type: "CALLS", label: "CALLS", animated: true },
          { id: "e2", source: "api-1", target: "psp-2", relationship_type: "CALLS", label: "CALLS", animated: true },
          { id: "e3", source: "api-1", target: "api-2", relationship_type: "AUTHENTICATES_VIA", label: "AUTH" },
          { id: "e4", source: "api-1", target: "api-3", relationship_type: "DEPENDS_ON", label: "DEPENDS_ON" },
          { id: "e5", source: "flow-1", target: "api-1", relationship_type: "USES", label: "USES" },
          { id: "e6", source: "gw-1", target: "api-1", relationship_type: "ROUTES_TO", label: "ROUTES_TO" },
          { id: "e7", source: "gw-1", target: "api-2", relationship_type: "ROUTES_TO", label: "ROUTES_TO" },
        ],
        spec_id: currentSpecId,
        depth,
      };
      setGraphData(demoData);
    } finally {
      setIsLoading(false);
    }
  }, [currentSpecId, depth]);

  useEffect(() => {
    if (currentSpecId) {
      fetchGraph();
    }
  }, [currentSpecId, fetchGraph]);

  const toggleNodeType = (type: EntityType) => {
    setEnabledTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const filteredData: GraphData | null = graphData
    ? {
        ...graphData,
        nodes: graphData.nodes.filter((n) => enabledTypes.has(n.type)),
        edges: graphData.edges.filter((e) => {
          const sourceNode = graphData.nodes.find((n) => n.id === e.source);
          const targetNode = graphData.nodes.find((n) => n.id === e.target);
          return (
            sourceNode && targetNode &&
            enabledTypes.has(sourceNode.type) &&
            enabledTypes.has(targetNode.type)
          );
        }),
      }
    : null;

  return (
    <div className="flex h-screen bg-[#080d1a] overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Dependency Graph" />
        <div className="flex-1 flex overflow-hidden">
          {/* Left Control Panel */}
          <div className="w-60 border-r border-slate-800 bg-slate-900/50 flex flex-col overflow-y-auto">
            <div className="p-4 space-y-5">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  API Spec
                </label>
                <SpecSelector
                  specs={specs}
                  value={currentSpecId}
                  onChange={setActiveSpecId}
                />
              </div>

              {/* Depth Slider */}
              <div>
                <label className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  <span>Graph Depth</span>
                  <span className="text-indigo-400 font-mono">{depth}</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={5}
                  value={depth}
                  onChange={(e) => setDepth(Number(e.target.value))}
                  className="w-full h-1 bg-slate-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-indigo-500"
                />
                <div className="flex justify-between text-xs text-slate-600 mt-1">
                  <span>1</span>
                  <span>5</span>
                </div>
              </div>

              {/* Node Type Filters */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Node Types
                </label>
                <div className="space-y-1.5">
                  {NODE_TYPES.map((nt) => (
                    <button
                      key={nt.type}
                      onClick={() => toggleNodeType(nt.type)}
                      className={cn(
                        "w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs transition-colors",
                        enabledTypes.has(nt.type)
                          ? "bg-slate-800 text-slate-300"
                          : "text-slate-600 hover:bg-slate-800/50"
                      )}
                    >
                      <span
                        className={cn(
                          "w-2.5 h-2.5 rounded-full flex-shrink-0",
                          enabledTypes.has(nt.type) ? nt.color : "bg-slate-700"
                        )}
                      />
                      <span>{nt.label}</span>
                      {!enabledTypes.has(nt.type) && (
                        <span className="ml-auto text-slate-700 text-xs">hidden</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="space-y-2">
                <button
                  onClick={fetchGraph}
                  disabled={isLoading || !currentSpecId}
                  className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50"
                >
                  <RefreshCw
                    className={cn("w-3.5 h-3.5", isLoading && "animate-spin")}
                  />
                  {isLoading ? "Loading..." : "Refresh Graph"}
                </button>
                <button
                  onClick={() => setFitViewTrigger((v) => v + 1)}
                  className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs border border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300 transition-colors"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                  Fit View
                </button>
              </div>

              {/* Legend */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Edge Types
                </label>
                <div className="space-y-1.5">
                  {[
                    { label: "CALLS", style: "border-dashed border-indigo-500", animated: true },
                    { label: "DEPENDS_ON", style: "border-solid border-slate-500" },
                    { label: "AUTHENTICATES_VIA", style: "border-solid border-red-500" },
                    { label: "ROUTES_TO", style: "border-solid border-sky-500" },
                  ].map((et) => (
                    <div key={et.label} className="flex items-center gap-2">
                      <div className={cn("w-8 border-t-2", et.style)} />
                      <span className="text-xs text-slate-500">{et.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Graph Canvas */}
          <div className="flex-1 relative">
            {!currentSpecId ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <Network className="w-16 h-16 text-slate-700 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-slate-400">
                    Select a Spec
                  </h3>
                  <p className="text-slate-600 text-sm mt-1">
                    Choose an API spec to visualize its dependency graph
                  </p>
                </div>
              </div>
            ) : isLoading ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <RefreshCw className="w-10 h-10 text-indigo-400 animate-spin mx-auto mb-3" />
                  <p className="text-slate-400 text-sm">
                    Building dependency graph...
                  </p>
                </div>
              </div>
            ) : filteredData ? (
              <GraphCanvas
                data={filteredData}
                onNodeSelect={setSelectedNode}
                fitViewTrigger={fitViewTrigger}
              />
            ) : null}
          </div>

          {/* Right Panel — Selected Node Details */}
          {selectedNode && (
            <div className="w-72 border-l border-slate-800 bg-slate-900/50 overflow-y-auto">
              <div className="p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-slate-200">
                    Node Details
                  </h3>
                  <button
                    onClick={() => setSelectedNode(null)}
                    className="text-slate-500 hover:text-slate-400 text-xs"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-slate-500 mb-1">Name</p>
                    <p className="text-sm font-medium text-slate-200">
                      {selectedNode.label}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 mb-1">Type</p>
                    <span className="px-2 py-0.5 rounded text-xs capitalize bg-slate-800 text-slate-300 border border-slate-700">
                      {selectedNode.type}
                    </span>
                  </div>
                  {selectedNode.endpoint_count !== undefined && (
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Endpoints</p>
                      <p className="text-sm text-slate-300">
                        {selectedNode.endpoint_count}
                      </p>
                    </div>
                  )}
                  {selectedNode.risk_level && (
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Risk Level</p>
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-xs capitalize border",
                          selectedNode.risk_level === "critical"
                            ? "text-red-400 bg-red-400/10 border-red-400/20"
                            : selectedNode.risk_level === "high"
                            ? "text-orange-400 bg-orange-400/10 border-orange-400/20"
                            : selectedNode.risk_level === "medium"
                            ? "text-amber-400 bg-amber-400/10 border-amber-400/20"
                            : "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
                        )}
                      >
                        {selectedNode.risk_level}
                      </span>
                    </div>
                  )}
                  {selectedNode.spec_id && (
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Spec ID</p>
                      <p className="text-xs font-mono text-slate-400 break-all">
                        {selectedNode.spec_id}
                      </p>
                    </div>
                  )}
                  {Object.keys(selectedNode.metadata).length > 0 && (
                    <div>
                      <p className="text-xs text-slate-500 mb-2">Metadata</p>
                      <pre className="text-xs font-mono text-slate-400 bg-slate-950 border border-slate-800 rounded p-3 overflow-x-auto">
                        {JSON.stringify(selectedNode.metadata, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function GraphPage() {
  return (
    <Suspense fallback={
      <div className="flex h-screen bg-[#080d1a] items-center justify-center">
        <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin" />
      </div>
    }>
      <GraphPageInner />
    </Suspense>
  );
}

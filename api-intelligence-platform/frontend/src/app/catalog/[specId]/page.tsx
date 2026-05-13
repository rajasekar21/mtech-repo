"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  ExternalLink,
  GitBranch,
  Globe,
  Network,
  RefreshCw,
  Shield,
  Tag,
} from "lucide-react";
import { useCatalogStore } from "@/store/catalog";
import { cn, formatDate, getRiskColor, formatScore } from "@/lib/utils";
import Sidebar from "@/components/shared/Sidebar";
import Header from "@/components/shared/Header";
import EndpointCard from "@/components/catalog/EndpointCard";
import EndpointDetail from "@/components/catalog/EndpointDetail";
import type { ApiEndpoint } from "@/types";

type TabId = "endpoints" | "flows" | "schemas" | "security" | "governance";

const TABS: { id: TabId; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "endpoints", label: "Endpoints", icon: GitBranch },
  { id: "flows", label: "Flows", icon: Network },
  { id: "schemas", label: "Schemas", icon: Globe },
  { id: "security", label: "Security", icon: Shield },
  { id: "governance", label: "Governance", icon: Tag },
];

export default function SpecDetailPage() {
  const params = useParams<{ specId: string }>();
  const specId = params.specId;

  const { currentSpec, endpoints, flows, fetchSpec, fetchEndpoints, fetchFlows, isLoading } =
    useCatalogStore();
  const [activeTab, setActiveTab] = useState<TabId>("endpoints");
  const [selectedEndpoint, setSelectedEndpoint] = useState<ApiEndpoint | null>(null);
  const [endpointSearch, setEndpointSearch] = useState("");

  useEffect(() => {
    if (specId) {
      fetchSpec(specId);
      fetchEndpoints(specId);
      fetchFlows(specId);
    }
  }, [specId, fetchSpec, fetchEndpoints, fetchFlows]);

  const filteredEndpoints = endpoints.filter(
    (ep) =>
      !endpointSearch ||
      ep.path.toLowerCase().includes(endpointSearch.toLowerCase()) ||
      ep.summary.toLowerCase().includes(endpointSearch.toLowerCase())
  );

  const handleExportJson = () => {
    const data = JSON.stringify({ spec: currentSpec, endpoints }, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${currentSpec?.name ?? "spec"}-${currentSpec?.version ?? "v1"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading && !currentSpec) {
    return (
      <div className="flex h-screen bg-[#080d1a]">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#080d1a] overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title={currentSpec?.name ?? "Spec Details"} />
        <div className="flex-1 overflow-y-auto">
          {/* Spec Header */}
          {currentSpec && (
            <div className="px-6 pt-4 pb-0 border-b border-slate-800">
              <Link
                href="/catalog"
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-400 mb-4"
              >
                <ArrowLeft className="w-3 h-3" />
                Back to Catalog
              </Link>

              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                    <Globe className="w-6 h-6 text-indigo-400" />
                  </div>
                  <div>
                    <div className="flex items-center gap-3">
                      <h1 className="text-xl font-bold text-white">
                        {currentSpec.name}
                      </h1>
                      <span className="font-mono text-sm text-slate-500">
                        v{currentSpec.version}
                      </span>
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded-full text-xs border capitalize",
                          currentSpec.status === "active"
                            ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
                            : currentSpec.status === "deprecated"
                            ? "text-red-400 bg-red-400/10 border-red-400/20"
                            : "text-slate-400 bg-slate-400/10 border-slate-400/20"
                        )}
                      >
                        {currentSpec.status}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400 mt-1">
                      {currentSpec.description}
                    </p>
                    <div className="flex items-center gap-4 mt-2">
                      <span className="text-xs text-slate-500">
                        {currentSpec.endpoints_count} endpoints
                      </span>
                      <span className="text-xs text-slate-500">
                        {currentSpec.flows_count} flows
                      </span>
                      <span className="text-xs text-slate-500">
                        {currentSpec.dependencies_count} dependencies
                      </span>
                      <span className="text-xs text-slate-500">
                        Updated {formatDate(currentSpec.updated_at)}
                      </span>
                    </div>
                    {currentSpec.tags.length > 0 && (
                      <div className="flex items-center gap-1.5 mt-2">
                        {currentSpec.tags.map((tag) => (
                          <span
                            key={tag}
                            className="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-400 border border-slate-700"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {currentSpec.governance_score && (
                    <div className="text-center px-4 py-2 rounded-lg bg-slate-800 border border-slate-700">
                      <p className="text-xs text-slate-500">Governance</p>
                      <p
                        className={cn(
                          "text-lg font-bold",
                          formatScore(currentSpec.governance_score).color
                        )}
                      >
                        {currentSpec.governance_score}
                      </p>
                    </div>
                  )}
                  <div className="text-center px-4 py-2 rounded-lg bg-slate-800 border border-slate-700">
                    <p className="text-xs text-slate-500">Risk</p>
                    <p
                      className={cn(
                        "text-sm font-semibold capitalize",
                        getRiskColor(currentSpec.risk_level)
                          .split(" ")[0]
                      )}
                    >
                      {currentSpec.risk_level}
                    </p>
                  </div>
                  <button
                    onClick={handleExportJson}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs border border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Export JSON
                  </button>
                  <Link
                    href={`/graph?spec=${specId}`}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 hover:bg-indigo-600/30 transition-colors"
                  >
                    <Network className="w-3.5 h-3.5" />
                    View Graph
                  </Link>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex items-center gap-1">
                {TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
                      activeTab === tab.id
                        ? "border-indigo-500 text-indigo-400"
                        : "border-transparent text-slate-500 hover:text-slate-300"
                    )}
                  >
                    <tab.icon className="w-3.5 h-3.5" />
                    {tab.label}
                    {tab.id === "endpoints" && (
                      <span className="ml-1 px-1.5 py-0.5 rounded text-xs bg-slate-800 text-slate-400">
                        {filteredEndpoints.length}
                      </span>
                    )}
                    {tab.id === "flows" && (
                      <span className="ml-1 px-1.5 py-0.5 rounded text-xs bg-slate-800 text-slate-400">
                        {flows.length}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Tab Content */}
          <div className="p-6">
            {activeTab === "endpoints" && (
              <div>
                <div className="mb-4">
                  <input
                    value={endpointSearch}
                    onChange={(e) => setEndpointSearch(e.target.value)}
                    placeholder="Filter endpoints..."
                    className="w-full max-w-sm px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
                  />
                </div>
                {isLoading ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {Array.from({ length: 6 }).map((_, i) => (
                      <div
                        key={i}
                        className="enterprise-card animate-pulse h-40 bg-slate-800/50"
                      />
                    ))}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {filteredEndpoints.map((ep) => (
                      <EndpointCard
                        key={ep.id}
                        endpoint={ep}
                        onClick={() => setSelectedEndpoint(ep)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "flows" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {flows.map((flow) => (
                  <Link
                    key={flow.id}
                    href={`/flow?spec=${specId}&flow=${flow.id}`}
                    className="enterprise-card-hover"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-sm font-semibold text-slate-200">
                          {flow.name}
                        </p>
                        <p className="text-xs text-slate-500 mt-1 capitalize">
                          {flow.type.replace("_", " ")}
                        </p>
                        <p className="text-xs text-slate-400 mt-2 line-clamp-2">
                          {flow.description}
                        </p>
                      </div>
                      <ExternalLink className="w-3.5 h-3.5 text-slate-600 flex-shrink-0 ml-2" />
                    </div>
                    <div className="flex items-center gap-3 mt-3 pt-3 border-t border-slate-800">
                      <span className="text-xs text-slate-500">
                        {flow.steps.length} steps
                      </span>
                      <span className="text-xs text-slate-500">
                        {flow.involved_apis.length} APIs
                      </span>
                    </div>
                  </Link>
                ))}
                {flows.length === 0 && (
                  <div className="col-span-2 flex items-center justify-center h-48 text-slate-500">
                    No flows found for this spec
                  </div>
                )}
              </div>
            )}

            {activeTab === "schemas" && (
              <div className="enterprise-card">
                <p className="text-slate-400 text-sm">
                  Schema viewer coming soon. Use the endpoint detail panel to
                  inspect individual request/response schemas.
                </p>
              </div>
            )}

            {activeTab === "security" && (
              <div className="text-center py-12">
                <Shield className="w-12 h-12 text-slate-700 mx-auto mb-3" />
                <p className="text-slate-400">
                  View security findings in the{" "}
                  <Link
                    href={`/security?spec=${specId}`}
                    className="text-indigo-400 hover:underline"
                  >
                    Security Intelligence
                  </Link>{" "}
                  module
                </p>
              </div>
            )}

            {activeTab === "governance" && (
              <div className="text-center py-12">
                <Tag className="w-12 h-12 text-slate-700 mx-auto mb-3" />
                <p className="text-slate-400">
                  View governance reports in the{" "}
                  <Link
                    href={`/governance?spec=${specId}`}
                    className="text-indigo-400 hover:underline"
                  >
                    Governance Dashboard
                  </Link>
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedEndpoint && (
        <EndpointDetail
          endpoint={selectedEndpoint}
          onClose={() => setSelectedEndpoint(null)}
        />
      )}
    </div>
  );
}

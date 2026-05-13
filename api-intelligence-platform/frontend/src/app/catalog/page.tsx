"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, Filter, Upload, ChevronDown, Tag, X, RefreshCw } from "lucide-react";
import { useCatalogStore } from "@/store/catalog";
import { useUIStore } from "@/store/ui";
import { cn } from "@/lib/utils";
import Sidebar from "@/components/shared/Sidebar";
import Header from "@/components/shared/Header";
import EndpointCard from "@/components/catalog/EndpointCard";
import EndpointDetail from "@/components/catalog/EndpointDetail";
import SpecSelector from "@/components/shared/SpecSelector";
import UploadSpec from "@/components/shared/UploadSpec";
import type { ApiEndpoint, RiskLevel, AuthMethod } from "@/types";

const RISK_LEVELS: RiskLevel[] = ["critical", "high", "medium", "low", "none"];
const AUTH_METHODS: AuthMethod[] = ["oauth2", "api_key", "basic", "jwt", "none"];

export default function CatalogPage() {
  const { specs, endpoints, fetchSpecs, fetchEndpoints, isLoading } = useCatalogStore();
  const { activeSpecId, setActiveSpecId } = useUIStore();

  const [search, setSearch] = useState("");
  const [selectedRisk, setSelectedRisk] = useState<RiskLevel | "">("");
  const [selectedAuth, setSelectedAuth] = useState<AuthMethod | "">("");
  const [showDeprecated, setShowDeprecated] = useState(false);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selectedEndpoint, setSelectedEndpoint] = useState<ApiEndpoint | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [showUpload, setShowUpload] = useState(false);

  const allTags = [...new Set(endpoints.flatMap((e) => e.tags))];

  const filtered = endpoints.filter((ep) => {
    const matchesSearch =
      !search ||
      ep.path.toLowerCase().includes(search.toLowerCase()) ||
      ep.summary.toLowerCase().includes(search.toLowerCase()) ||
      ep.description.toLowerCase().includes(search.toLowerCase());
    const matchesRisk = !selectedRisk || ep.risk_level === selectedRisk;
    const matchesAuth = !selectedAuth || ep.auth_method === selectedAuth;
    const matchesDeprecated = showDeprecated || !ep.deprecated;
    const matchesTags =
      selectedTags.length === 0 ||
      selectedTags.some((tag) => ep.tags.includes(tag));
    return matchesSearch && matchesRisk && matchesAuth && matchesDeprecated && matchesTags;
  });

  useEffect(() => {
    fetchSpecs();
  }, [fetchSpecs]);

  useEffect(() => {
    if (activeSpecId) {
      fetchEndpoints(activeSpecId);
    }
  }, [activeSpecId, fetchEndpoints]);

  const handleSpecChange = useCallback(
    (specId: string | null) => {
      setActiveSpecId(specId);
    },
    [setActiveSpecId]
  );

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const clearFilters = () => {
    setSearch("");
    setSelectedRisk("");
    setSelectedAuth("");
    setShowDeprecated(false);
    setSelectedTags([]);
  };

  const hasActiveFilters =
    search || selectedRisk || selectedAuth || showDeprecated || selectedTags.length > 0;

  return (
    <div className="flex h-screen bg-[#080d1a] overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="API Catalog" />
        <div className="flex-1 flex overflow-hidden">
          {/* Filter Sidebar */}
          <div
            className={cn(
              "w-64 border-r border-slate-800 bg-slate-900/50 flex-shrink-0 overflow-y-auto transition-all duration-200",
              showFilters ? "block" : "hidden lg:block"
            )}
          >
            <div className="p-4 space-y-5">
              {/* Spec Selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  API Spec
                </label>
                <SpecSelector
                  specs={specs}
                  value={activeSpecId}
                  onChange={handleSpecChange}
                />
              </div>

              {/* Search */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Search
                </label>
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Path, summary..."
                    className="w-full pl-8 pr-3 py-2 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-300 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 focus:border-indigo-500/50"
                  />
                </div>
              </div>

              {/* Risk Level */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Risk Level
                </label>
                <div className="space-y-1">
                  {RISK_LEVELS.map((risk) => (
                    <button
                      key={risk}
                      onClick={() =>
                        setSelectedRisk(selectedRisk === risk ? "" : risk)
                      }
                      className={cn(
                        "w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs capitalize transition-colors",
                        selectedRisk === risk
                          ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                          : "text-slate-400 hover:bg-slate-800 hover:text-slate-300"
                      )}
                    >
                      <span>{risk}</span>
                      {selectedRisk === risk && (
                        <X className="w-3 h-3" />
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Auth Method */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Auth Method
                </label>
                <div className="space-y-1">
                  {AUTH_METHODS.map((auth) => (
                    <button
                      key={auth}
                      onClick={() =>
                        setSelectedAuth(selectedAuth === auth ? "" : auth)
                      }
                      className={cn(
                        "w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs capitalize transition-colors",
                        selectedAuth === auth
                          ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                          : "text-slate-400 hover:bg-slate-800 hover:text-slate-300"
                      )}
                    >
                      <span>{auth.replace("_", " ")}</span>
                      {selectedAuth === auth && <X className="w-3 h-3" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* Deprecated Toggle */}
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Show Deprecated
                </label>
                <button
                  onClick={() => setShowDeprecated(!showDeprecated)}
                  className={cn(
                    "w-10 h-5 rounded-full transition-colors relative",
                    showDeprecated ? "bg-indigo-600" : "bg-slate-700"
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform",
                      showDeprecated ? "translate-x-5" : "translate-x-0.5"
                    )}
                  />
                </button>
              </div>

              {/* Tags */}
              {allTags.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Tags
                  </label>
                  <div className="flex flex-wrap gap-1">
                    {allTags.map((tag) => (
                      <button
                        key={tag}
                        onClick={() => toggleTag(tag)}
                        className={cn(
                          "px-2 py-0.5 rounded text-xs transition-colors",
                          selectedTags.includes(tag)
                            ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/30"
                            : "bg-slate-800 text-slate-500 hover:text-slate-300 border border-transparent"
                        )}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Clear Filters */}
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="w-full py-2 text-xs text-slate-400 hover:text-slate-300 border border-slate-700 rounded-lg hover:border-slate-600 transition-colors flex items-center justify-center gap-1"
                >
                  <X className="w-3 h-3" />
                  Clear all filters
                </button>
              )}
            </div>
          </div>

          {/* Main Content */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Toolbar */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-slate-900/30">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={cn(
                    "lg:hidden flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border transition-colors",
                    showFilters
                      ? "bg-indigo-600/20 border-indigo-500/30 text-indigo-400"
                      : "border-slate-700 text-slate-400 hover:border-slate-600"
                  )}
                >
                  <Filter className="w-3.5 h-3.5" />
                  Filters
                </button>
                <span className="text-sm text-slate-400">
                  <span className="text-slate-200 font-medium">
                    {filtered.length}
                  </span>{" "}
                  endpoints
                  {activeSpecId && (
                    <span className="text-slate-500"> in spec</span>
                  )}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {activeSpecId && (
                  <button
                    onClick={() => fetchEndpoints(activeSpecId)}
                    disabled={isLoading}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-slate-400 hover:bg-slate-800 transition-colors"
                  >
                    <RefreshCw
                      className={cn("w-3.5 h-3.5", isLoading && "animate-spin")}
                    />
                  </button>
                )}
                <button
                  onClick={() => setShowUpload(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
                >
                  <Upload className="w-3.5 h-3.5" />
                  Upload Spec
                </button>
              </div>
            </div>

            {/* Endpoint Grid */}
            <div className="flex-1 overflow-y-auto p-6">
              {!activeSpecId ? (
                <div className="flex flex-col items-center justify-center h-64 text-center">
                  <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mb-4">
                    <Tag className="w-8 h-8 text-slate-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-300 mb-2">
                    Select an API Spec
                  </h3>
                  <p className="text-slate-500 text-sm max-w-sm">
                    Choose a spec from the filter panel or upload a new OpenAPI
                    specification to explore endpoints.
                  </p>
                  <button
                    onClick={() => setShowUpload(true)}
                    className="mt-4 flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
                  >
                    <Upload className="w-4 h-4" />
                    Upload Spec
                  </button>
                </div>
              ) : isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {Array.from({ length: 9 }).map((_, i) => (
                    <div
                      key={i}
                      className="enterprise-card animate-pulse h-40 bg-slate-800/50"
                    />
                  ))}
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-64 text-center">
                  <Search className="w-12 h-12 text-slate-700 mb-3" />
                  <h3 className="text-slate-400 font-medium">
                    No endpoints found
                  </h3>
                  <p className="text-slate-600 text-sm mt-1">
                    Try adjusting your filters
                  </p>
                  {hasActiveFilters && (
                    <button
                      onClick={clearFilters}
                      className="mt-3 text-xs text-indigo-400 hover:text-indigo-300"
                    >
                      Clear filters
                    </button>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {filtered.map((endpoint) => (
                    <EndpointCard
                      key={endpoint.id}
                      endpoint={endpoint}
                      onClick={() => setSelectedEndpoint(endpoint)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Endpoint Detail Sheet */}
      {selectedEndpoint && (
        <EndpointDetail
          endpoint={selectedEndpoint}
          onClose={() => setSelectedEndpoint(null)}
        />
      )}

      {/* Upload Modal */}
      {showUpload && (
        <UploadSpec onClose={() => setShowUpload(false)} />
      )}
    </div>
  );
}

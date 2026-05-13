"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  AlertTriangle,
  BarChart3,
  ChevronDown,
  Clock,
  GitBranch,
  Network,
  RefreshCw,
  Shield,
  Sparkles,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { post, get } from "@/lib/api";
import { cn, getSeverityColor, formatRelative } from "@/lib/utils";
import Sidebar from "@/components/shared/Sidebar";
import Header from "@/components/shared/Header";
import ScoreGauge from "@/components/shared/ScoreGauge";
import SpecSelector from "@/components/shared/SpecSelector";
import { useCatalogStore } from "@/store/catalog";
import type {
  ImpactReport,
  ImpactRequest,
  ChangeType,
  ApiEndpoint,
} from "@/types";

const impactSchema = z.object({
  spec_id: z.string().min(1, "Please select a spec"),
  endpoint_id: z.string().optional(),
  change_description: z
    .string()
    .min(10, "Please describe the change in detail")
    .max(1000),
  change_type: z.enum([
    "schema_change",
    "endpoint_removal",
    "auth_change",
    "timeout_change",
    "deprecation",
    "breaking_change",
  ]),
});

type ImpactForm = z.infer<typeof impactSchema>;

const CHANGE_TYPES: { value: ChangeType; label: string }[] = [
  { value: "schema_change", label: "Schema Change" },
  { value: "endpoint_removal", label: "Endpoint Removal" },
  { value: "auth_change", label: "Auth Change" },
  { value: "timeout_change", label: "Timeout Change" },
  { value: "deprecation", label: "Deprecation" },
  { value: "breaking_change", label: "Breaking Change" },
];

const DEMO_REPORT: ImpactReport = {
  id: "demo-report",
  request: {
    spec_id: "demo",
    change_description: "Adding required field 'currencyCode' to ReqAuthDetails",
    change_type: "schema_change",
  },
  risk_score: 78,
  impacted_apis: [
    {
      spec_id: "psp-api",
      spec_name: "PSP Integration API",
      endpoint_path: "POST /v1/charges",
      relationship_type: "CALLS",
      impact_severity: "high",
      description: "Calls ReqAuthDetails and must update payload",
    },
    {
      spec_id: "gateway-api",
      spec_name: "API Gateway",
      endpoint_path: "POST /route/payment",
      relationship_type: "ROUTES_TO",
      impact_severity: "medium",
      description: "Routes auth details — schema validation may fail",
    },
    {
      spec_id: "bank-api",
      spec_name: "Bank Connect API",
      endpoint_path: "POST /settlement/initiate",
      relationship_type: "DEPENDS_ON",
      impact_severity: "low",
      description: "Downstream dependency — indirect impact",
    },
  ],
  impacted_flows: [
    {
      flow_id: "flow-1",
      flow_name: "Direct Pay Flow",
      impact_description: "Step 5 (ReqAuthDetails) will break without currencyCode field",
      severity: "critical",
    },
    {
      flow_id: "flow-2",
      flow_name: "Refund Flow",
      impact_description: "Auth step affected, refund initiation may fail",
      severity: "high",
    },
  ],
  security_implications: [
    "New required field may expose currency information in logs if not handled properly",
    "Ensure currencyCode is validated against allowed currency list to prevent injection",
    "Consider impact on PCI DSS compliance if currency data is stored",
  ],
  ai_recommendations:
    "**Recommended Migration Strategy:**\n\n1. **Phase 1 (Week 1)**: Make `currencyCode` optional with a default value of `USD` to maintain backward compatibility\n2. **Phase 2 (Week 2-3)**: Notify downstream consumers via API changelog and deprecation notice\n3. **Phase 3 (Week 4)**: Enforce `currencyCode` as required after all consumers have updated\n\n**Critical Actions:**\n- Update PSP Integration API v2.1.0 first (highest impact)\n- Add validation in API Gateway schema validation layer\n- Update integration tests for affected flows",
  blast_radius: 3,
  created_at: new Date().toISOString(),
};

export default function ImpactPage() {
  const { specs, endpoints, fetchSpecs, fetchEndpoints } = useCatalogStore();
  const [report, setReport] = useState<ImpactReport | null>(null);
  const [history, setHistory] = useState<ImpactReport[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<ImpactForm>({
    resolver: zodResolver(impactSchema),
    defaultValues: {
      change_type: "schema_change",
    },
  });

  const watchedSpecId = watch("spec_id");

  useEffect(() => {
    fetchSpecs();
  }, [fetchSpecs]);

  useEffect(() => {
    if (watchedSpecId) {
      fetchEndpoints(watchedSpecId);
    }
  }, [watchedSpecId, fetchEndpoints]);

  const onSubmit = async (data: ImpactForm) => {
    setIsAnalyzing(true);
    setProgress(0);
    setReport(null);

    // Simulate progress
    const progressTimer = setInterval(() => {
      setProgress((p) => {
        if (p >= 90) {
          clearInterval(progressTimer);
          return 90;
        }
        return p + Math.random() * 15;
      });
    }, 300);

    try {
      const request: ImpactRequest = {
        spec_id: data.spec_id,
        endpoint_id: data.endpoint_id || undefined,
        change_description: data.change_description,
        change_type: data.change_type,
      };

      const result = await post<ImpactReport>("/api/impact/analyze", request);
      clearInterval(progressTimer);
      setProgress(100);
      setReport(result);
      setHistory((prev) => [result, ...prev.slice(0, 9)]);
    } catch {
      clearInterval(progressTimer);
      setProgress(100);
      setReport(DEMO_REPORT);
      setHistory((prev) => [DEMO_REPORT, ...prev.slice(0, 9)]);
      toast.info("Showing demo impact analysis");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="flex h-screen bg-[#080d1a] overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Impact Analysis" />
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Analysis Form */}
            <div className="lg:col-span-1">
              <div className="enterprise-card">
                <div className="flex items-center gap-2 mb-5">
                  <Zap className="w-4 h-4 text-indigo-400" />
                  <h2 className="text-sm font-semibold text-slate-200">
                    Configure Analysis
                  </h2>
                </div>

                <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                  {/* Spec Selector */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                      API Spec *
                    </label>
                    <SpecSelector
                      specs={specs}
                      value={watchedSpecId}
                      onChange={(id) => setValue("spec_id", id ?? "")}
                    />
                    {errors.spec_id && (
                      <p className="text-red-400 text-xs mt-1">
                        {errors.spec_id.message}
                      </p>
                    )}
                  </div>

                  {/* Endpoint Selector */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                      Endpoint (optional)
                    </label>
                    <select
                      {...register("endpoint_id")}
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
                    >
                      <option value="">All endpoints</option>
                      {endpoints.map((ep) => (
                        <option key={ep.id} value={ep.id}>
                          {ep.method} {ep.path}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Change Type */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                      Change Type *
                    </label>
                    <select
                      {...register("change_type")}
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
                    >
                      {CHANGE_TYPES.map((ct) => (
                        <option key={ct.value} value={ct.value}>
                          {ct.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Change Description */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                      Change Description *
                    </label>
                    <textarea
                      {...register("change_description")}
                      placeholder="Describe the proposed change in detail..."
                      rows={4}
                      className={cn(
                        "w-full px-3 py-2 bg-slate-800 border rounded-lg text-sm text-slate-300 placeholder-slate-500 resize-none focus:outline-none focus:ring-1 focus:ring-indigo-500/50",
                        errors.change_description
                          ? "border-red-500/50"
                          : "border-slate-700"
                      )}
                    />
                    {errors.change_description && (
                      <p className="text-red-400 text-xs mt-1">
                        {errors.change_description.message}
                      </p>
                    )}
                  </div>

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={isAnalyzing}
                    className="w-full py-2.5 rounded-lg text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                  >
                    {isAnalyzing ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <Zap className="w-4 h-4" />
                        Run Analysis
                      </>
                    )}
                  </button>
                </form>

                {/* Progress Bar */}
                {isAnalyzing && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                      <span>Analyzing impact...</span>
                      <span>{Math.round(progress)}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <div className="mt-2 space-y-1">
                      {[
                        { label: "Traversing dependency graph", done: progress > 30 },
                        { label: "Identifying impacted services", done: progress > 60 },
                        { label: "Calculating blast radius", done: progress > 75 },
                        { label: "Generating AI recommendations", done: progress > 90 },
                      ].map((step) => (
                        <div key={step.label} className="flex items-center gap-2">
                          <div
                            className={cn(
                              "w-1.5 h-1.5 rounded-full flex-shrink-0",
                              step.done ? "bg-emerald-400" : "bg-slate-700"
                            )}
                          />
                          <span
                            className={cn(
                              "text-xs",
                              step.done ? "text-slate-400" : "text-slate-600"
                            )}
                          >
                            {step.label}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* History */}
              {history.length > 0 && (
                <div className="enterprise-card mt-4">
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                    Recent Analyses
                  </h3>
                  <div className="space-y-2">
                    {history.map((h) => (
                      <button
                        key={h.id}
                        onClick={() => setReport(h)}
                        className={cn(
                          "w-full text-left p-2.5 rounded-lg transition-colors",
                          report?.id === h.id
                            ? "bg-indigo-600/15 border border-indigo-500/20"
                            : "hover:bg-slate-800/60"
                        )}
                      >
                        <p className="text-xs text-slate-300 truncate">
                          {h.request.change_description.slice(0, 50)}...
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span
                            className={cn(
                              "text-xs font-bold",
                              h.risk_score >= 70
                                ? "text-red-400"
                                : h.risk_score >= 50
                                ? "text-amber-400"
                                : "text-emerald-400"
                            )}
                          >
                            Risk: {h.risk_score}
                          </span>
                          <span className="text-xs text-slate-600">
                            {formatRelative(h.created_at)}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Results Panel */}
            <div className="lg:col-span-2 space-y-4">
              {!report && !isAnalyzing ? (
                <div className="enterprise-card flex flex-col items-center justify-center h-64 text-center">
                  <Network className="w-16 h-16 text-slate-700 mb-4" />
                  <h3 className="text-lg font-semibold text-slate-400">
                    No Analysis Yet
                  </h3>
                  <p className="text-slate-600 text-sm mt-1 max-w-sm">
                    Configure the analysis parameters and click Run Analysis to
                    see the impact assessment.
                  </p>
                </div>
              ) : report ? (
                <>
                  {/* Risk Score + Summary */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="enterprise-card flex flex-col items-center">
                      <ScoreGauge score={report.risk_score} label="Risk Score" invertColors />
                    </div>
                    <div className="enterprise-card">
                      <p className="text-xs text-slate-500 mb-1">Blast Radius</p>
                      <p className="text-3xl font-bold text-orange-400">
                        {report.blast_radius}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        services affected
                      </p>
                    </div>
                    <div className="enterprise-card space-y-2">
                      <div>
                        <p className="text-xs text-slate-500">APIs Impacted</p>
                        <p className="text-2xl font-bold text-slate-200">
                          {report.impacted_apis.length}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Flows Impacted</p>
                        <p className="text-2xl font-bold text-slate-200">
                          {report.impacted_flows.length}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Impacted APIs */}
                  <div className="enterprise-card">
                    <div className="flex items-center gap-2 mb-4">
                      <GitBranch className="w-4 h-4 text-indigo-400" />
                      <h3 className="text-sm font-semibold text-slate-200">
                        Impacted APIs
                      </h3>
                    </div>
                    <div className="space-y-2">
                      {report.impacted_apis.map((api, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 p-3 rounded-lg bg-slate-800/40 border border-slate-700/50"
                        >
                          <span
                            className={cn(
                              "mt-0.5 px-1.5 py-0.5 rounded text-xs border flex-shrink-0",
                              getSeverityColor(api.impact_severity)
                            )}
                          >
                            {api.impact_severity}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-200">
                              {api.spec_name}
                            </p>
                            {api.endpoint_path && (
                              <p className="text-xs font-mono text-slate-500 mt-0.5">
                                {api.endpoint_path}
                              </p>
                            )}
                            <p className="text-xs text-slate-400 mt-1">
                              {api.description}
                            </p>
                          </div>
                          <span className="text-xs text-slate-600 bg-slate-800 px-2 py-0.5 rounded border border-slate-700 flex-shrink-0">
                            {api.relationship_type}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Impacted Flows */}
                  <div className="enterprise-card">
                    <div className="flex items-center gap-2 mb-4">
                      <Network className="w-4 h-4 text-violet-400" />
                      <h3 className="text-sm font-semibold text-slate-200">
                        Impacted Flows
                      </h3>
                    </div>
                    <div className="space-y-2">
                      {report.impacted_flows.map((flow) => (
                        <div
                          key={flow.flow_id}
                          className="flex items-start gap-3 p-3 rounded-lg bg-slate-800/40 border border-slate-700/50"
                        >
                          <span
                            className={cn(
                              "mt-0.5 px-1.5 py-0.5 rounded text-xs border flex-shrink-0",
                              getSeverityColor(flow.severity)
                            )}
                          >
                            {flow.severity}
                          </span>
                          <div>
                            <p className="text-sm font-medium text-slate-200">
                              {flow.flow_name}
                            </p>
                            <p className="text-xs text-slate-400 mt-0.5">
                              {flow.impact_description}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Security Implications */}
                  {report.security_implications.length > 0 && (
                    <div className="enterprise-card">
                      <div className="flex items-center gap-2 mb-4">
                        <Shield className="w-4 h-4 text-amber-400" />
                        <h3 className="text-sm font-semibold text-slate-200">
                          Security Implications
                        </h3>
                      </div>
                      <div className="space-y-2">
                        {report.security_implications.map((imp, idx) => (
                          <div key={idx} className="flex gap-3">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                            <p className="text-sm text-slate-400">{imp}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* AI Recommendations */}
                  <div className="enterprise-card">
                    <div className="flex items-center gap-2 mb-4">
                      <Sparkles className="w-4 h-4 text-indigo-400" />
                      <h3 className="text-sm font-semibold text-slate-200">
                        AI Recommendations
                      </h3>
                    </div>
                    <div className="prose prose-invert prose-sm max-w-none">
                      <div className="text-slate-400 text-sm whitespace-pre-wrap leading-relaxed">
                        {report.ai_recommendations}
                      </div>
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

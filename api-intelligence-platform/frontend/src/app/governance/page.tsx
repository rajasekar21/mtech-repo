"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Download,
  RefreshCw,
  Shield,
  Sparkles,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { post, get } from "@/lib/api";
import { cn, getSeverityColor, formatRelative } from "@/lib/utils";
import Sidebar from "@/components/shared/Sidebar";
import Header from "@/components/shared/Header";
import ScoreGauge from "@/components/shared/ScoreGauge";
import SpecSelector from "@/components/shared/SpecSelector";
import { useCatalogStore } from "@/store/catalog";
import type { GovernanceReport, GovernanceRuleResult, RuleStatus } from "@/types";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const DEMO_REPORT: GovernanceReport = {
  id: "gov-demo",
  spec_id: "demo",
  overall_score: 76,
  passed: 18,
  failed: 4,
  warnings: 3,
  skipped: 1,
  rule_results: [
    {
      rule: { id: "r1", name: "Endpoint Documentation", description: "All endpoints must have summary and description", category: "documentation", severity: "medium" },
      status: "pass",
      details: "All 47 endpoints have documentation",
    },
    {
      rule: { id: "r2", name: "Auth Required", description: "All write endpoints must require authentication", category: "security", severity: "high" },
      status: "fail",
      affected_endpoints: ["POST /v1/webhooks/register", "PUT /v1/settings/update"],
      details: "2 write endpoints found without auth requirement",
      fix_suggestion: "Add 'security' field with OAuth2 scheme to these endpoints",
    },
    {
      rule: { id: "r3", name: "Rate Limiting Headers", description: "Responses should include rate limit headers", category: "performance", severity: "medium" },
      status: "warning",
      details: "Rate limit headers missing in 8 endpoints",
      fix_suggestion: "Add X-RateLimit-Limit and X-RateLimit-Remaining response headers",
    },
    {
      rule: { id: "r4", name: "Deprecation Notice", description: "Deprecated endpoints must have x-deprecated info", category: "deprecation", severity: "medium" },
      status: "fail",
      affected_endpoints: ["GET /v1/payments/legacy"],
      details: "Deprecated endpoint missing x-deprecated metadata",
      fix_suggestion: "Add x-deprecated: true and x-sunset-date to deprecated endpoints",
    },
    {
      rule: { id: "r5", name: "Semantic Versioning", description: "API version must follow semver", category: "versioning", severity: "low" },
      status: "pass",
      details: "Version 3.2.1 follows semantic versioning",
    },
    {
      rule: { id: "r6", name: "Response Schema", description: "All responses must have defined schemas", category: "schema", severity: "high" },
      status: "fail",
      affected_endpoints: ["DELETE /v1/transactions/{id}", "DELETE /v1/subscriptions/{id}"],
      details: "DELETE endpoints missing response schema definition",
      fix_suggestion: "Add 204 or 200 response schema with appropriate content type",
    },
    {
      rule: { id: "r7", name: "Tag Grouping", description: "Endpoints should be grouped with tags", category: "naming", severity: "low" },
      status: "warning",
      details: "12 endpoints have no tags assigned",
    },
    {
      rule: { id: "r8", name: "HTTPS Only", description: "All server URLs must use HTTPS", category: "security", severity: "critical" },
      status: "pass",
      details: "All server URLs use HTTPS",
    },
    {
      rule: { id: "r9", name: "Input Validation", description: "Request bodies must have maxLength/pattern for strings", category: "schema", severity: "high" },
      status: "fail",
      affected_endpoints: ["POST /v1/customers", "PUT /v1/customers/{id}"],
      details: "String fields missing maxLength constraints",
      fix_suggestion: "Add maxLength constraints to all string fields in request schemas",
    },
    {
      rule: { id: "r10", name: "Error Responses", description: "All endpoints must define 400, 401, 500 responses", category: "documentation", severity: "medium" },
      status: "warning",
      details: "Some endpoints missing standard error responses",
    },
  ],
  ai_recommendations: "Focus on fixing the 2 unauthenticated write endpoints immediately as they pose a significant security risk. The missing response schemas on DELETE endpoints should also be addressed in the next sprint. Consider implementing a pre-commit hook to enforce governance rules before API changes are merged.",
  created_at: new Date().toISOString(),
};

const TREND_DATA = [
  { date: "Nov", score: 58 },
  { date: "Dec", score: 63 },
  { date: "Jan", score: 71 },
  { date: "Feb", score: 68 },
  { date: "Mar", score: 74 },
  { date: "Apr", score: 76 },
];

function StatusIcon({ status }: { status: RuleStatus }) {
  switch (status) {
    case "pass":
      return <CheckCircle className="w-4 h-4 text-emerald-400" />;
    case "fail":
      return <XCircle className="w-4 h-4 text-red-400" />;
    case "warning":
      return <AlertTriangle className="w-4 h-4 text-amber-400" />;
    default:
      return <div className="w-4 h-4 rounded-full bg-slate-700" />;
  }
}

function StatusBadge({ status }: { status: RuleStatus }) {
  const styles: Record<RuleStatus, string> = {
    pass: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
    fail: "text-red-400 bg-red-400/10 border-red-400/20",
    warning: "text-amber-400 bg-amber-400/10 border-amber-400/20",
    skipped: "text-slate-400 bg-slate-400/10 border-slate-400/20",
  };
  return (
    <span
      className={cn(
        "px-2 py-0.5 rounded-full text-xs border capitalize",
        styles[status]
      )}
    >
      {status}
    </span>
  );
}

export default function GovernancePage() {
  const { specs, fetchSpecs } = useCatalogStore();
  const [selectedSpecId, setSelectedSpecId] = useState<string | null>(null);
  const [report, setReport] = useState<GovernanceReport | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [filterStatus, setFilterStatus] = useState<RuleStatus | "all">("all");

  useEffect(() => {
    fetchSpecs();
  }, [fetchSpecs]);

  const runCheck = async () => {
    if (!selectedSpecId) {
      toast.error("Please select a spec first");
      return;
    }
    setIsRunning(true);
    try {
      const result = await post<GovernanceReport>(
        `/api/specs/${selectedSpecId}/governance`,
        {}
      );
      setReport(result);
      toast.success("Governance check complete");
    } catch {
      setReport(DEMO_REPORT);
      toast.info("Showing demo governance report");
    } finally {
      setIsRunning(false);
    }
  };

  const exportReport = () => {
    if (!report) return;
    const data = JSON.stringify(report, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `governance-report-${report.spec_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredRules = report?.rule_results.filter(
    (r) => filterStatus === "all" || r.status === filterStatus
  ) ?? [];

  return (
    <div className="flex h-screen bg-[#080d1a] overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Governance Dashboard" />
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Controls */}
          <div className="flex items-center gap-3">
            <div className="w-64">
              <SpecSelector
                specs={specs}
                value={selectedSpecId}
                onChange={setSelectedSpecId}
              />
            </div>
            <button
              onClick={runCheck}
              disabled={isRunning || !selectedSpecId}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 transition-colors"
            >
              {isRunning ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Shield className="w-4 h-4" />
              )}
              {isRunning ? "Running check..." : "Run Governance Check"}
            </button>
            {report && (
              <button
                onClick={exportReport}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm border border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300 transition-colors"
              >
                <Download className="w-4 h-4" />
                Export Report
              </button>
            )}
          </div>

          {!report ? (
            <div className="enterprise-card flex flex-col items-center justify-center h-64 text-center">
              <Shield className="w-16 h-16 text-slate-700 mb-4" />
              <h3 className="text-lg font-semibold text-slate-400">
                No Governance Report
              </h3>
              <p className="text-slate-600 text-sm mt-1">
                Select a spec and run a governance check to see results
              </p>
            </div>
          ) : (
            <>
              {/* Score Overview */}
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="enterprise-card flex flex-col items-center">
                  <ScoreGauge score={report.overall_score} label="Overall Score" />
                </div>
                {[
                  { label: "Passed", value: report.passed, color: "text-emerald-400", icon: CheckCircle },
                  { label: "Failed", value: report.failed, color: "text-red-400", icon: XCircle },
                  { label: "Warnings", value: report.warnings, color: "text-amber-400", icon: AlertTriangle },
                ].map((stat) => (
                  <div key={stat.label} className="enterprise-card flex items-center gap-4">
                    <div className={cn("p-3 rounded-xl bg-current/10", stat.color.replace("text-", "bg-").replace("400", "400/10"))}>
                      <stat.icon className={cn("w-6 h-6", stat.color)} />
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{stat.label}</p>
                      <p className={cn("text-3xl font-bold", stat.color)}>
                        {stat.value}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Rule Breakdown */}
                <div className="lg:col-span-2 enterprise-card">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-semibold text-slate-200">
                      Rule Breakdown
                    </h2>
                    {/* Filter Tabs */}
                    <div className="flex items-center gap-1">
                      {(["all", "fail", "warning", "pass", "skipped"] as const).map((s) => (
                        <button
                          key={s}
                          onClick={() => setFilterStatus(s)}
                          className={cn(
                            "px-2.5 py-1 rounded text-xs capitalize transition-colors",
                            filterStatus === s
                              ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                              : "text-slate-500 hover:text-slate-400"
                          )}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    {filteredRules.map((result) => (
                      <div
                        key={result.rule.id}
                        className={cn(
                          "p-3 rounded-lg border",
                          result.status === "fail"
                            ? "bg-red-400/5 border-red-400/15"
                            : result.status === "warning"
                            ? "bg-amber-400/5 border-amber-400/15"
                            : "bg-slate-800/30 border-slate-700/50"
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <StatusIcon status={result.status} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="text-sm font-medium text-slate-200">
                                {result.rule.name}
                              </p>
                              <StatusBadge status={result.status} />
                              <span
                                className={cn(
                                  "text-xs px-1.5 py-0.5 rounded border",
                                  getSeverityColor(result.rule.severity)
                                )}
                              >
                                {result.rule.severity}
                              </span>
                              <span className="text-xs text-slate-600 capitalize">
                                {result.rule.category}
                              </span>
                            </div>
                            <p className="text-xs text-slate-500 mt-1">
                              {result.details ?? result.rule.description}
                            </p>
                            {result.affected_endpoints && result.affected_endpoints.length > 0 && (
                              <div className="mt-1.5 flex flex-wrap gap-1">
                                {result.affected_endpoints.map((ep) => (
                                  <span
                                    key={ep}
                                    className="text-xs font-mono text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700"
                                  >
                                    {ep}
                                  </span>
                                ))}
                              </div>
                            )}
                            {result.fix_suggestion && result.status !== "pass" && (
                              <div className="mt-2 p-2 rounded bg-indigo-500/5 border border-indigo-500/15">
                                <p className="text-xs text-indigo-300">
                                  <span className="font-semibold">Fix: </span>
                                  {result.fix_suggestion}
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Sidebar: Trends + AI Recommendations */}
                <div className="space-y-4">
                  {/* Trends Chart */}
                  <div className="enterprise-card">
                    <div className="flex items-center gap-2 mb-4">
                      <TrendingUp className="w-4 h-4 text-indigo-400" />
                      <h3 className="text-sm font-semibold text-slate-200">
                        Score Trend
                      </h3>
                    </div>
                    <ResponsiveContainer width="100%" height={140}>
                      <LineChart data={TREND_DATA}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 10, fill: "#64748b" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          domain={[0, 100]}
                          tick={{ fontSize: 10, fill: "#64748b" }}
                          axisLine={false}
                          tickLine={false}
                          width={25}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#0f172a",
                            border: "1px solid #1e293b",
                            borderRadius: "8px",
                            fontSize: "12px",
                            color: "#e2e8f0",
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="score"
                          stroke="#6366f1"
                          strokeWidth={2}
                          dot={{ r: 3, fill: "#6366f1" }}
                          activeDot={{ r: 5 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* AI Recommendations */}
                  {report.ai_recommendations && (
                    <div className="enterprise-card">
                      <div className="flex items-center gap-2 mb-3">
                        <Sparkles className="w-4 h-4 text-indigo-400" />
                        <h3 className="text-sm font-semibold text-slate-200">
                          AI Recommendations
                        </h3>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        {report.ai_recommendations}
                      </p>
                    </div>
                  )}

                  {/* Category Summary */}
                  <div className="enterprise-card">
                    <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                      By Category
                    </h3>
                    <div className="space-y-2">
                      {Object.entries(
                        report.rule_results.reduce(
                          (acc, r) => {
                            const cat = r.rule.category;
                            if (!acc[cat]) acc[cat] = { pass: 0, fail: 0, warning: 0 };
                            acc[cat][r.status as "pass" | "fail" | "warning"] =
                              (acc[cat][r.status as "pass" | "fail" | "warning"] ?? 0) + 1;
                            return acc;
                          },
                          {} as Record<string, { pass: number; fail: number; warning: number }>
                        )
                      ).map(([cat, counts]) => (
                        <div key={cat} className="flex items-center justify-between">
                          <span className="text-xs text-slate-400 capitalize">
                            {cat}
                          </span>
                          <div className="flex items-center gap-1">
                            {counts.pass > 0 && (
                              <span className="text-xs text-emerald-400">
                                {counts.pass}✓
                              </span>
                            )}
                            {counts.fail > 0 && (
                              <span className="text-xs text-red-400">
                                {counts.fail}✗
                              </span>
                            )}
                            {counts.warning > 0 && (
                              <span className="text-xs text-amber-400">
                                {counts.warning}⚠
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

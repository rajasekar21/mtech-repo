"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle,
  Clock,
  GitBranch,
  Globe,
  MessageSquare,
  Network,
  Plus,
  Search,
  Shield,
  TrendingUp,
  Upload,
  Zap,
} from "lucide-react";
import { cn, formatRelative, getRiskColor } from "@/lib/utils";
import type { DashboardStats, RecentActivity, ApiSpec } from "@/types";
import Sidebar from "@/components/shared/Sidebar";
import Header from "@/components/shared/Header";

// Mock data for demonstration — in production, fetched from API
const MOCK_STATS: DashboardStats = {
  total_specs: 12,
  total_endpoints: 347,
  total_flows: 28,
  total_dependencies: 89,
  avg_governance_score: 76,
  critical_findings: 3,
  high_findings: 11,
  recent_uploads: 2,
};

const MOCK_RECENT_SPECS: ApiSpec[] = [
  {
    id: "spec-1",
    name: "Payment Gateway API",
    version: "3.2.1",
    description: "Core payment processing endpoints for PSP integration",
    status: "active",
    tags: ["payments", "psp", "core"],
    endpoints_count: 47,
    flows_count: 8,
    dependencies_count: 12,
    governance_score: 84,
    risk_level: "medium",
    auth_methods: ["oauth2"],
    uploaded_by: "system",
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "spec-2",
    name: "Auth Service API",
    version: "2.0.0",
    description: "Authentication and authorization service",
    status: "active",
    tags: ["auth", "security", "identity"],
    endpoints_count: 23,
    flows_count: 5,
    dependencies_count: 7,
    governance_score: 91,
    risk_level: "high",
    auth_methods: ["jwt", "oauth2"],
    uploaded_by: "system",
    created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "spec-3",
    name: "Bank Connect API",
    version: "1.4.2",
    description: "Bank account connectivity and open banking flows",
    status: "active",
    tags: ["banking", "open-banking", "accounts"],
    endpoints_count: 31,
    flows_count: 6,
    dependencies_count: 15,
    governance_score: 68,
    risk_level: "critical",
    auth_methods: ["oauth2", "api_key"],
    uploaded_by: "system",
    created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
  },
];

const MOCK_ACTIVITY: RecentActivity[] = [
  {
    id: "act-1",
    type: "upload",
    description: "Uploaded Payment Gateway API v3.2.1",
    spec_name: "Payment Gateway API",
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "act-2",
    type: "governance",
    description: "Governance check completed — score 84/100",
    spec_name: "Payment Gateway API",
    created_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "act-3",
    type: "chat",
    description: "AI Chat: 'Explain direct pay flow'",
    created_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "act-4",
    type: "impact",
    description: "Impact analysis on ReqAuthDetails schema change",
    spec_name: "Auth Service API",
    created_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "act-5",
    type: "analysis",
    description: "Security scan found 3 critical findings",
    spec_name: "Bank Connect API",
    created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
  },
];

const QUICK_ACTIONS = [
  {
    label: "Upload Spec",
    description: "Import OpenAPI/Swagger",
    icon: Upload,
    href: "/catalog",
    color: "from-indigo-600 to-indigo-500",
  },
  {
    label: "AI Search",
    description: "Semantic endpoint search",
    icon: Search,
    href: "/catalog",
    color: "from-violet-600 to-violet-500",
  },
  {
    label: "View Graph",
    description: "Dependency visualization",
    icon: Network,
    href: "/graph",
    color: "from-sky-600 to-sky-500",
  },
  {
    label: "AI Chat",
    description: "Ask about your APIs",
    icon: MessageSquare,
    href: "/chat",
    color: "from-emerald-600 to-emerald-500",
  },
];

function StatCard({
  label,
  value,
  icon: Icon,
  change,
  color,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  change?: string;
  color: string;
}) {
  return (
    <div className="enterprise-card-hover group cursor-default">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-400 font-medium">{label}</p>
          <p className="text-3xl font-bold text-slate-100 mt-1">
            {value.toLocaleString()}
          </p>
          {change && (
            <p className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              {change}
            </p>
          )}
        </div>
        <div className={cn("p-3 rounded-xl bg-gradient-to-br", color, "opacity-90")}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  );
}

function ActivityIcon({ type }: { type: RecentActivity["type"] }) {
  switch (type) {
    case "upload":
      return <Upload className="w-3.5 h-3.5" />;
    case "governance":
      return <Shield className="w-3.5 h-3.5" />;
    case "chat":
      return <Bot className="w-3.5 h-3.5" />;
    case "impact":
      return <Zap className="w-3.5 h-3.5" />;
    case "analysis":
      return <Activity className="w-3.5 h-3.5" />;
    default:
      return <Clock className="w-3.5 h-3.5" />;
  }
}

function ActivityColor(type: RecentActivity["type"]): string {
  switch (type) {
    case "upload":
      return "bg-indigo-400/10 text-indigo-400";
    case "governance":
      return "bg-emerald-400/10 text-emerald-400";
    case "chat":
      return "bg-violet-400/10 text-violet-400";
    case "impact":
      return "bg-amber-400/10 text-amber-400";
    case "analysis":
      return "bg-red-400/10 text-red-400";
    default:
      return "bg-slate-400/10 text-slate-400";
  }
}

export default function DashboardPage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <div className="flex h-screen bg-[#080d1a] overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Dashboard" />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Hero area */}
          <div className="relative rounded-2xl overflow-hidden bg-gradient-to-br from-indigo-950/60 via-slate-900 to-violet-950/40 border border-indigo-800/30 p-6">
            <div className="absolute inset-0 enterprise-grid-bg opacity-30" />
            <div className="relative">
              <div className="flex items-center gap-2 mb-2">
                <div className="status-dot-active" />
                <span className="text-xs text-emerald-400 font-medium uppercase tracking-wider">
                  System Operational
                </span>
              </div>
              <h1 className="text-2xl font-bold text-white">
                API Intelligence Platform
              </h1>
              <p className="text-slate-400 mt-1 max-w-2xl">
                Enterprise API discovery, semantic search, dependency analysis, and AI-powered governance across your entire API ecosystem.
              </p>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Total APIs"
              value={MOCK_STATS.total_specs}
              icon={Globe}
              change="+2 this week"
              color="from-indigo-600 to-indigo-700"
            />
            <StatCard
              label="Endpoints"
              value={MOCK_STATS.total_endpoints}
              icon={GitBranch}
              change="+24 this week"
              color="from-violet-600 to-violet-700"
            />
            <StatCard
              label="Flows"
              value={MOCK_STATS.total_flows}
              icon={Network}
              color="from-sky-600 to-sky-700"
            />
            <StatCard
              label="Governance Score"
              value={`${MOCK_STATS.avg_governance_score}/100`}
              icon={BarChart3}
              change="↑ 4 points"
              color="from-emerald-600 to-emerald-700"
            />
          </div>

          {/* Quick Actions */}
          <div>
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
              Quick Actions
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {QUICK_ACTIONS.map((action) => (
                <Link
                  key={action.label}
                  href={action.href}
                  className="group enterprise-card-hover flex items-center gap-3 p-4"
                >
                  <div
                    className={cn(
                      "p-2 rounded-lg bg-gradient-to-br",
                      action.color,
                      "opacity-90 group-hover:opacity-100 transition-opacity"
                    )}
                  >
                    <action.icon className="w-4 h-4 text-white" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-200">
                      {action.label}
                    </p>
                    <p className="text-xs text-slate-500 truncate">
                      {action.description}
                    </p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 ml-auto flex-shrink-0 transition-colors" />
                </Link>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Recent Specs */}
            <div className="lg:col-span-2 enterprise-card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-slate-300">
                  Recent API Specs
                </h2>
                <Link
                  href="/catalog"
                  className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                >
                  View all
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
              <div className="space-y-2">
                {MOCK_RECENT_SPECS.map((spec) => (
                  <Link
                    key={spec.id}
                    href={`/catalog/${spec.id}`}
                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800/60 transition-colors group"
                  >
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
                      <Globe className="w-4 h-4 text-indigo-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-200 truncate">
                          {spec.name}
                        </span>
                        <span className="text-xs text-slate-500 font-mono">
                          v{spec.version}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-xs text-slate-500">
                          {spec.endpoints_count} endpoints
                        </span>
                        <span className="text-xs text-slate-500">
                          {spec.flows_count} flows
                        </span>
                        {spec.governance_score && (
                          <span
                            className={cn(
                              "text-xs",
                              spec.governance_score >= 80
                                ? "text-emerald-400"
                                : spec.governance_score >= 60
                                ? "text-amber-400"
                                : "text-red-400"
                            )}
                          >
                            {spec.governance_score}/100
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span
                        className={cn(
                          "text-xs px-2 py-0.5 rounded-full border capitalize",
                          getRiskColor(spec.risk_level)
                        )}
                      >
                        {spec.risk_level}
                      </span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                    </div>
                  </Link>
                ))}
              </div>
            </div>

            {/* Activity Feed */}
            <div className="enterprise-card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-slate-300">
                  Recent Activity
                </h2>
                <Activity className="w-4 h-4 text-slate-500" />
              </div>
              <div className="space-y-3">
                {MOCK_ACTIVITY.map((item) => (
                  <div key={item.id} className="flex gap-3">
                    <div
                      className={cn(
                        "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
                        ActivityColor(item.type)
                      )}
                    >
                      <ActivityIcon type={item.type} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {item.description}
                      </p>
                      {item.spec_name && (
                        <p className="text-xs text-indigo-400 mt-0.5">
                          {item.spec_name}
                        </p>
                      )}
                      <p className="text-xs text-slate-600 mt-0.5">
                        {formatRelative(item.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* AI Health Indicators */}
          <div className="enterprise-card">
            <h2 className="text-sm font-semibold text-slate-300 mb-4">
              AI System Health
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                {
                  label: "Vector Search",
                  status: "operational",
                  latency: "42ms",
                  icon: Search,
                },
                {
                  label: "AI Chat Engine",
                  status: "operational",
                  latency: "1.2s",
                  icon: Bot,
                },
                {
                  label: "Graph Engine",
                  status: "operational",
                  latency: "85ms",
                  icon: Network,
                },
                {
                  label: "Governance Rules",
                  status: "operational",
                  latency: "210ms",
                  icon: CheckCircle,
                },
              ].map((system) => (
                <div
                  key={system.label}
                  className="flex items-center gap-3 p-3 rounded-lg bg-slate-800/40 border border-slate-700/50"
                >
                  <div className="p-1.5 rounded-lg bg-slate-700/50">
                    <system.icon className="w-4 h-4 text-slate-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-slate-300 truncate">
                      {system.label}
                    </p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <div className="status-dot-active" />
                      <span className="text-xs text-slate-500">
                        {system.latency}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Security Summary */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="enterprise-card">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-semibold text-slate-300">
                  Security Overview
                </h2>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  {
                    label: "Critical",
                    count: MOCK_STATS.critical_findings,
                    color: "text-red-400 bg-red-400/10 border-red-400/20",
                  },
                  {
                    label: "High",
                    count: MOCK_STATS.high_findings,
                    color: "text-orange-400 bg-orange-400/10 border-orange-400/20",
                  },
                  { label: "Medium", count: 24, color: "text-amber-400 bg-amber-400/10 border-amber-400/20" },
                  { label: "Low", count: 41, color: "text-sky-400 bg-sky-400/10 border-sky-400/20" },
                ].map((item) => (
                  <Link
                    key={item.label}
                    href="/security"
                    className={cn(
                      "flex items-center justify-between p-3 rounded-lg border",
                      item.color,
                      "hover:opacity-80 transition-opacity"
                    )}
                  >
                    <span className="text-xs font-medium">{item.label}</span>
                    <span className="text-lg font-bold">{item.count}</span>
                  </Link>
                ))}
              </div>
            </div>

            <div className="enterprise-card">
              <div className="flex items-center gap-2 mb-4">
                <Plus className="w-4 h-4 text-indigo-400" />
                <h2 className="text-sm font-semibold text-slate-300">
                  Get Started
                </h2>
              </div>
              <div className="space-y-2">
                {[
                  {
                    text: "Upload your first OpenAPI spec",
                    done: true,
                    href: "/catalog",
                  },
                  {
                    text: "Run governance analysis",
                    done: true,
                    href: "/governance",
                  },
                  {
                    text: "Explore dependency graph",
                    done: false,
                    href: "/graph",
                  },
                  {
                    text: "Chat with AI about your APIs",
                    done: false,
                    href: "/chat",
                  },
                ].map((item) => (
                  <Link
                    key={item.text}
                    href={item.href}
                    className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-800/50 transition-colors"
                  >
                    <div
                      className={cn(
                        "w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0",
                        item.done
                          ? "bg-emerald-400/20 text-emerald-400"
                          : "bg-slate-700 text-slate-600"
                      )}
                    >
                      {item.done ? (
                        <CheckCircle className="w-3 h-3" />
                      ) : (
                        <div className="w-2 h-2 rounded-full bg-slate-500" />
                      )}
                    </div>
                    <span
                      className={cn(
                        "text-sm",
                        item.done
                          ? "line-through text-slate-500"
                          : "text-slate-300"
                      )}
                    >
                      {item.text}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

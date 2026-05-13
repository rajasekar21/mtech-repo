"use client";

import { ChevronRight } from "lucide-react";
import { getMethodColor, getRiskColor } from "@/lib/utils";
import type { ApiEndpoint } from "@/types";

interface EndpointCardProps {
  endpoint: ApiEndpoint;
  onClick?: () => void;
}

export default function EndpointCard({
  endpoint,
  onClick,
}: EndpointCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="enterprise-card-hover w-full text-left"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-center gap-2">
            <span className={`method-badge ${getMethodColor(endpoint.method)}`}>
              {endpoint.method}
            </span>
            <span
              className={`rounded-full border px-2 py-0.5 text-xs capitalize ${getRiskColor(endpoint.risk_level)}`}
            >
              {endpoint.risk_level}
            </span>
          </div>

          <p className="truncate font-mono text-sm text-slate-100">
            {endpoint.path}
          </p>
          <p className="mt-2 text-sm font-medium text-slate-200">
            {endpoint.summary}
          </p>
          <p className="mt-1 line-clamp-2 text-xs text-slate-500">
            {endpoint.description || "No description available."}
          </p>
        </div>

        <ChevronRight className="mt-1 h-4 w-4 flex-shrink-0 text-slate-600" />
      </div>
    </button>
  );
}

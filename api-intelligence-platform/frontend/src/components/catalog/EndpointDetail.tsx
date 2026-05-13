"use client";

import { X } from "lucide-react";
import { getMethodColor, getRiskColor } from "@/lib/utils";
import type { ApiEndpoint } from "@/types";

interface EndpointDetailProps {
  endpoint: ApiEndpoint;
  onClose: () => void;
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="code-block text-xs text-slate-300">
      {JSON.stringify(value ?? {}, null, 2)}
    </pre>
  );
}

export default function EndpointDetail({
  endpoint,
  onClose,
}: EndpointDetailProps) {
  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl border-l border-slate-800 bg-slate-950/95 shadow-2xl">
      <div className="flex h-full flex-col">
        <div className="flex items-start justify-between border-b border-slate-800 p-5">
          <div className="min-w-0">
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
            <h2 className="truncate font-mono text-lg text-slate-100">
              {endpoint.path}
            </h2>
            <p className="mt-1 text-sm text-slate-400">{endpoint.summary}</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <section>
            <h3 className="mb-2 text-sm font-semibold text-slate-200">
              Description
            </h3>
            <p className="text-sm text-slate-400">
              {endpoint.description || "No description available."}
            </p>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold text-slate-200">
              Parameters
            </h3>
            <JsonBlock value={endpoint.parameters} />
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold text-slate-200">
              Request Body
            </h3>
            <JsonBlock value={endpoint.request_body} />
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold text-slate-200">
              Responses
            </h3>
            <JsonBlock value={endpoint.responses} />
          </section>
        </div>
      </div>
    </div>
  );
}

"use client";

import type { ApiSpec } from "@/types";

interface SpecSelectorProps {
  specs: ApiSpec[];
  value?: string | null;
  onChange: (value: string | null) => void;
}

export default function SpecSelector({
  specs,
  value,
  onChange,
}: SpecSelectorProps) {
  return (
    <select
      value={value ?? ""}
      onChange={(event) => onChange(event.target.value || null)}
      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500/60"
    >
      <option value="">Select a spec</option>
      {specs.map((spec) => (
        <option key={spec.id} value={spec.id}>
          {spec.name} {spec.version ? `v${spec.version}` : ""}
        </option>
      ))}
    </select>
  );
}

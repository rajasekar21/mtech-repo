"use client";

interface MermaidViewerProps {
  diagram: string;
  currentStep: number;
  totalSteps: number;
}

export default function MermaidViewer({
  diagram,
  currentStep,
  totalSteps,
}: MermaidViewerProps) {
  return (
    <div className="mermaid-container h-full overflow-y-auto p-6">
      <div className="enterprise-card mb-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">
              Sequence Diagram
            </h3>
            <p className="text-xs text-slate-500">
              Step {Math.max(currentStep + 1, 0)} of {totalSteps}
            </p>
          </div>
        </div>
      </div>

      <pre className="code-block whitespace-pre-wrap text-slate-300">
        {diagram}
      </pre>
    </div>
  );
}

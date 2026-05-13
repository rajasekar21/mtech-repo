"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Pause,
  Play,
  RefreshCw,
  Share2,
} from "lucide-react";
import { useCatalogStore } from "@/store/catalog";
import { useUIStore } from "@/store/ui";
import { cn } from "@/lib/utils";
import Sidebar from "@/components/shared/Sidebar";
import Header from "@/components/shared/Header";
import MermaidViewer from "@/components/flow/MermaidViewer";
import SpecSelector from "@/components/shared/SpecSelector";
import type { Flow } from "@/types";

const DEMO_FLOW: Flow = {
  id: "flow-demo",
  spec_id: "demo",
  name: "Direct Pay Flow",
  description: "End-to-end payment processing flow from merchant to PSP and bank settlement",
  type: "payment",
  mermaid_diagram: `sequenceDiagram
    participant M as Merchant
    participant GW as API Gateway
    participant PG as Payment Gateway
    participant Auth as Auth Service
    participant PSP as PSP (Stripe)
    participant Bank as Bank

    M->>GW: POST /v1/payments
    GW->>Auth: Validate JWT Token
    Auth-->>GW: Token Valid
    GW->>PG: Route Payment Request
    PG->>Auth: ReqAuthDetails
    Auth-->>PG: AuthDetails Confirmed
    PG->>PSP: Charge Card
    PSP->>Bank: Initiate Transfer
    Bank-->>PSP: Transfer Confirmed
    PSP-->>PG: Charge Success
    PG-->>GW: Payment Created
    GW-->>M: 201 Payment Created`,
  steps: [
    { step_number: 1, from: "Merchant", to: "API Gateway", action: "POST /v1/payments" },
    { step_number: 2, from: "API Gateway", to: "Auth Service", action: "Validate JWT Token" },
    { step_number: 3, from: "Auth Service", to: "API Gateway", action: "Token Valid" },
    { step_number: 4, from: "API Gateway", to: "Payment Gateway", action: "Route Payment Request" },
    { step_number: 5, from: "Payment Gateway", to: "Auth Service", action: "ReqAuthDetails" },
    { step_number: 6, from: "Auth Service", to: "Payment Gateway", action: "AuthDetails Confirmed" },
    { step_number: 7, from: "Payment Gateway", to: "PSP", action: "Charge Card" },
    { step_number: 8, from: "PSP", to: "Bank", action: "Initiate Transfer" },
    { step_number: 9, from: "Bank", to: "PSP", action: "Transfer Confirmed" },
    { step_number: 10, from: "PSP", to: "Payment Gateway", action: "Charge Success" },
    { step_number: 11, from: "Payment Gateway", to: "API Gateway", action: "Payment Created" },
    { step_number: 12, from: "API Gateway", to: "Merchant", action: "201 Payment Created" },
  ],
  involved_apis: ["Payment Gateway API", "Auth Service API"],
  involved_endpoints: ["POST /v1/payments", "POST /auth/validate"],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

function FlowPageInner() {
  const searchParams = useSearchParams();
  const specFromUrl = searchParams.get("spec");
  const flowFromUrl = searchParams.get("flow");

  const { specs, flows, fetchSpecs, fetchFlows, isLoading } = useCatalogStore();
  const { activeSpecId, setActiveSpecId } = useUIStore();

  const [selectedFlow, setSelectedFlow] = useState<Flow | null>(null);
  const [currentStep, setCurrentStep] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(1500);

  const currentSpecId = specFromUrl ?? activeSpecId;

  useEffect(() => {
    fetchSpecs();
  }, [fetchSpecs]);

  useEffect(() => {
    if (currentSpecId) {
      fetchFlows(currentSpecId).then(() => {
        if (flowFromUrl && flows.length > 0) {
          const flow = flows.find((f) => f.id === flowFromUrl);
          if (flow) setSelectedFlow(flow);
        }
      });
    }
  }, [currentSpecId, flowFromUrl, fetchFlows]);

  // Auto-play
  useEffect(() => {
    if (!isPlaying || !selectedFlow) return;
    const maxStep = selectedFlow.steps.length - 1;
    const timer = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev >= maxStep) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, playSpeed);
    return () => clearInterval(timer);
  }, [isPlaying, selectedFlow, playSpeed]);

  const handlePlayPause = () => {
    if (!selectedFlow) return;
    if (currentStep >= selectedFlow.steps.length - 1) {
      setCurrentStep(-1);
    }
    setIsPlaying(!isPlaying);
  };

  const handleStepBack = () => {
    setCurrentStep((prev) => Math.max(-1, prev - 1));
    setIsPlaying(false);
  };

  const handleStepForward = () => {
    if (!selectedFlow) return;
    setCurrentStep((prev) =>
      Math.min(selectedFlow.steps.length - 1, prev + 1)
    );
    setIsPlaying(false);
  };

  const handleReset = () => {
    setCurrentStep(-1);
    setIsPlaying(false);
  };

  const displayFlow = selectedFlow ?? (flows.length === 0 ? DEMO_FLOW : null);

  const exportSvg = () => {
    const svgEl = document.querySelector(".mermaid-container svg");
    if (!svgEl) return;
    const svgData = new XMLSerializer().serializeToString(svgEl);
    const blob = new Blob([svgData], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${displayFlow?.name ?? "flow"}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-screen bg-[#080d1a] overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Flow Visualizer" />
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel */}
          <div className="w-64 border-r border-slate-800 bg-slate-900/50 flex flex-col overflow-y-auto">
            <div className="p-4 space-y-5">
              {/* Spec Selector */}
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

              {/* Flow Selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Flow
                </label>
                {flows.length > 0 ? (
                  <div className="space-y-1">
                    {flows.map((flow) => (
                      <button
                        key={flow.id}
                        onClick={() => {
                          setSelectedFlow(flow);
                          handleReset();
                        }}
                        className={cn(
                          "w-full text-left px-3 py-2 rounded-lg text-xs transition-colors",
                          selectedFlow?.id === flow.id
                            ? "bg-indigo-600/20 border border-indigo-500/30 text-indigo-300"
                            : "text-slate-400 hover:bg-slate-800 hover:text-slate-300"
                        )}
                      >
                        <p className="font-medium truncate">{flow.name}</p>
                        <p className="text-slate-500 capitalize mt-0.5">
                          {flow.type.replace("_", " ")} · {flow.steps.length} steps
                        </p>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                    <p className="text-xs text-slate-500">
                      {currentSpecId
                        ? isLoading
                          ? "Loading flows..."
                          : "No flows found. Showing demo."
                        : "Select a spec to see flows"}
                    </p>
                  </div>
                )}
              </div>

              {/* Flow Metadata */}
              {displayFlow && (
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Flow Info
                  </label>
                  <div className="space-y-2">
                    <div>
                      <p className="text-xs text-slate-500">Type</p>
                      <p className="text-xs text-slate-300 capitalize">
                        {displayFlow.type.replace("_", " ")}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Steps</p>
                      <p className="text-xs text-slate-300">
                        {displayFlow.steps.length}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Involved APIs</p>
                      <div className="space-y-0.5 mt-1">
                        {displayFlow.involved_apis.map((api) => (
                          <p key={api} className="text-xs text-indigo-400 truncate">
                            {api}
                          </p>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Play Speed */}
              <div>
                <label className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  <span>Step Speed</span>
                  <span className="text-indigo-400">{playSpeed}ms</span>
                </label>
                <input
                  type="range"
                  min={500}
                  max={3000}
                  step={500}
                  value={playSpeed}
                  onChange={(e) => setPlaySpeed(Number(e.target.value))}
                  className="w-full h-1 bg-slate-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-indigo-500"
                />
              </div>

              {/* Export */}
              <button
                onClick={exportSvg}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs border border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                Export SVG
              </button>
            </div>
          </div>

          {/* Main Content */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Playback Controls */}
            {displayFlow && (
              <div className="flex items-center gap-3 px-6 py-3 border-b border-slate-800 bg-slate-900/30">
                <div className="flex items-center gap-1">
                  <button
                    onClick={handleReset}
                    title="Reset"
                    className="p-1.5 rounded-lg text-slate-500 hover:text-slate-400 hover:bg-slate-800 transition-colors"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleStepBack}
                    disabled={currentStep < 0}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-slate-400 hover:bg-slate-800 transition-colors disabled:opacity-30"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handlePlayPause}
                    className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
                  >
                    {isPlaying ? (
                      <Pause className="w-4 h-4" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={handleStepForward}
                    disabled={currentStep >= displayFlow.steps.length - 1}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-slate-400 hover:bg-slate-800 transition-colors disabled:opacity-30"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>

                {/* Step progress */}
                <div className="flex-1 flex items-center gap-2">
                  <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 transition-all duration-300"
                      style={{
                        width:
                          currentStep < 0
                            ? "0%"
                            : `${((currentStep + 1) / displayFlow.steps.length) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="text-xs text-slate-500 w-16 text-right">
                    {currentStep < 0
                      ? "Ready"
                      : `Step ${currentStep + 1}/${displayFlow.steps.length}`}
                  </span>
                </div>

                {/* Current step description */}
                {currentStep >= 0 && displayFlow.steps[currentStep] && (
                  <div className="text-xs text-slate-400 max-w-xs truncate">
                    <span className="text-indigo-400">
                      {displayFlow.steps[currentStep].from}
                    </span>
                    {" → "}
                    <span className="text-violet-400">
                      {displayFlow.steps[currentStep].to}
                    </span>
                    {": "}
                    {displayFlow.steps[currentStep].action}
                  </div>
                )}
              </div>
            )}

            {/* Mermaid Diagram */}
            <div className="flex-1 overflow-hidden">
              {displayFlow ? (
                <MermaidViewer
                  diagram={displayFlow.mermaid_diagram}
                  currentStep={currentStep}
                  totalSteps={displayFlow.steps.length}
                />
              ) : (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Share2 className="w-16 h-16 text-slate-700 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-slate-400">
                      Select a Flow
                    </h3>
                    <p className="text-slate-600 text-sm mt-1">
                      Choose a spec and flow to visualize the sequence diagram
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Step List */}
            {displayFlow && displayFlow.steps.length > 0 && (
              <div className="border-t border-slate-800 bg-slate-900/30 p-4">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Steps
                </p>
                <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                  {displayFlow.steps.map((step, idx) => (
                    <button
                      key={step.step_number}
                      onClick={() => {
                        setCurrentStep(idx);
                        setIsPlaying(false);
                      }}
                      className={cn(
                        "flex-shrink-0 px-3 py-1.5 rounded-lg text-xs border transition-colors",
                        idx === currentStep
                          ? "bg-indigo-600/20 border-indigo-500/30 text-indigo-400"
                          : idx < currentStep
                          ? "bg-slate-800/50 border-slate-700/50 text-slate-500"
                          : "border-slate-800 text-slate-600 hover:border-slate-700 hover:text-slate-500"
                      )}
                    >
                      <span className="font-mono">{step.step_number}</span>
                      <span className="ml-1.5 max-w-[100px] truncate inline-block align-bottom">
                        {step.action}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function FlowPage() {
  return (
    <Suspense fallback={
      <div className="flex h-screen bg-[#080d1a] items-center justify-center">
        <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin" />
      </div>
    }>
      <FlowPageInner />
    </Suspense>
  );
}

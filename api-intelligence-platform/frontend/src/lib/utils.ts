import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistance, format, parseISO } from "date-fns";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return format(d, "MMM dd, yyyy");
}

export function formatDateTime(date: string | Date): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return format(d, "MMM dd, yyyy HH:mm");
}

export function formatRelative(date: string | Date): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return formatDistance(d, new Date(), { addSuffix: true });
}

export function truncate(text: string, length: number): string {
  if (text.length <= length) return text;
  return text.slice(0, length) + "…";
}

type RiskLevel = "critical" | "high" | "medium" | "low" | "none" | string;
type Severity = "critical" | "high" | "medium" | "low" | "info" | string;

export function getRiskColor(riskLevel: RiskLevel): string {
  const level = riskLevel?.toLowerCase();
  switch (level) {
    case "critical":
      return "text-red-400 bg-red-400/10 border-red-400/20";
    case "high":
      return "text-orange-400 bg-orange-400/10 border-orange-400/20";
    case "medium":
      return "text-amber-400 bg-amber-400/10 border-amber-400/20";
    case "low":
      return "text-emerald-400 bg-emerald-400/10 border-emerald-400/20";
    case "none":
    default:
      return "text-slate-400 bg-slate-400/10 border-slate-400/20";
  }
}

export function getSeverityColor(severity: Severity): string {
  const s = severity?.toLowerCase();
  switch (s) {
    case "critical":
      return "text-red-400 bg-red-400/10 border-red-400/20";
    case "high":
      return "text-orange-400 bg-orange-400/10 border-orange-400/20";
    case "medium":
      return "text-amber-400 bg-amber-400/10 border-amber-400/20";
    case "low":
      return "text-sky-400 bg-sky-400/10 border-sky-400/20";
    case "info":
    default:
      return "text-slate-400 bg-slate-400/10 border-slate-400/20";
  }
}

export function getMethodColor(method: string): string {
  switch (method?.toUpperCase()) {
    case "GET":
      return "text-emerald-400 bg-emerald-400/10 border-emerald-400/30";
    case "POST":
      return "text-indigo-400 bg-indigo-400/10 border-indigo-400/30";
    case "PUT":
      return "text-amber-400 bg-amber-400/10 border-amber-400/30";
    case "DELETE":
      return "text-red-400 bg-red-400/10 border-red-400/30";
    case "PATCH":
      return "text-violet-400 bg-violet-400/10 border-violet-400/30";
    case "OPTIONS":
      return "text-cyan-400 bg-cyan-400/10 border-cyan-400/30";
    case "HEAD":
      return "text-pink-400 bg-pink-400/10 border-pink-400/30";
    default:
      return "text-slate-400 bg-slate-400/10 border-slate-400/30";
  }
}

export function formatScore(score: number): { label: string; color: string } {
  if (score >= 90)
    return { label: `${score}`, color: "text-emerald-400" };
  if (score >= 75)
    return { label: `${score}`, color: "text-yellow-400" };
  if (score >= 50)
    return { label: `${score}`, color: "text-orange-400" };
  return { label: `${score}`, color: "text-red-400" };
}

export function getScoreGradient(score: number): string {
  if (score >= 90) return "#10b981";
  if (score >= 75) return "#f59e0b";
  if (score >= 50) return "#f97316";
  return "#ef4444";
}

export function copyToClipboard(text: string): Promise<void> {
  return navigator.clipboard.writeText(text);
}

export function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

export function groupBy<T>(
  array: T[],
  keyFn: (item: T) => string
): Record<string, T[]> {
  return array.reduce(
    (groups, item) => {
      const key = keyFn(item);
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
      return groups;
    },
    {} as Record<string, T[]>
  );
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^\w-]+/g, "")
    .replace(/--+/g, "-")
    .trim();
}

export function parseJson(json: string): unknown {
  try {
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

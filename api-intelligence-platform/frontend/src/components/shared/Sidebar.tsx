"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Blocks, GitBranch, LayoutDashboard, LogIn, Network, Share2 } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/catalog", label: "Catalog", icon: GitBranch },
  { href: "/graph", label: "Graph", icon: Network },
  { href: "/flow", label: "Flow", icon: Share2 },
  { href: "/auth/login", label: "Login", icon: LogIn },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 flex-shrink-0 border-r border-slate-800 bg-slate-950/90 lg:flex lg:flex-col">
      <div className="flex h-16 items-center gap-3 border-b border-slate-800 px-5">
        <div className="rounded-xl bg-indigo-500/15 p-2 text-indigo-400">
          <Blocks className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-100">API Intelligence</p>
          <p className="text-xs text-slate-500">Developer Portal</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {NAV_ITEMS.map((item) => {
          const active =
            item.href === "/"
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-indigo-600/15 text-indigo-300"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              )}
            >
              <item.icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

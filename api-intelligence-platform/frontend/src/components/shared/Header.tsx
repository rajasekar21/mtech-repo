"use client";

interface HeaderProps {
  title: string;
}

export default function Header({ title }: HeaderProps) {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="flex h-16 items-center justify-between px-6">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">{title}</h1>
          <p className="text-xs text-slate-500">
            API Intelligence Platform
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="status-dot-active" />
          <span className="text-xs text-slate-400">Local dev</span>
        </div>
      </div>
    </header>
  );
}

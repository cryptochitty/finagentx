"use client";
import { Zap, ZapOff } from "lucide-react";

interface Props {
  value:    boolean;
  onChange: (v: boolean) => void;
}

export default function AutonomousToggle({ value, onChange }: Props) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-all
        ${value
          ? "bg-brand/20 border-brand text-brand animate-pulse-slow"
          : "bg-surface-card border-surface-border text-slate-400 hover:border-slate-500"
        }`}
    >
      {value
        ? <Zap className="w-4 h-4" />
        : <ZapOff className="w-4 h-4" />
      }
      {value ? "Autonomous ON" : "Manual Mode"}
    </button>
  );
}

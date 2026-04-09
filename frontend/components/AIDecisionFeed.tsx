"use client";
import { useEffect, useRef, useState } from "react";
import { Brain, ChevronRight, Loader2 } from "lucide-react";
import { type CycleResult, type CycleDecision, getDecisions } from "@/lib/api";

const AGENT_COLORS: Record<string, string> = {
  MarketIntelligenceAgent: "text-cyan-400",
  StrategyAgent:           "text-purple-400",
  SimulationAgent:         "text-yellow-400",
  RiskAgent:               "text-orange-400",
  ExecutionAgent:          "text-green-400",
  PayFiAgent:              "text-pink-400",
  ExplainerAgent:          "text-blue-400",
};

const AGENT_ICONS: Record<string, string> = {
  MarketIntelligenceAgent: "📡",
  StrategyAgent:           "🧠",
  SimulationAgent:         "🔬",
  RiskAgent:               "🛡️",
  ExecutionAgent:          "⚡",
  PayFiAgent:              "💳",
  ExplainerAgent:          "💬",
};

interface Props {
  wallet:  string;
  cycle:   CycleResult | null;
  loading: boolean;
}

export default function AIDecisionFeed({ wallet, cycle, loading }: Props) {
  const [history, setHistory] = useState<CycleDecision[]>([]);
  const feedRef = useRef<HTMLDivElement>(null);

  // Load historical decisions on mount
  useEffect(() => {
    getDecisions(wallet).then(setHistory).catch(console.error);
  }, [wallet]);

  // Scroll to bottom when new decisions arrive
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [cycle, loading]);

  // Combine history + latest cycle decisions
  const allDecisions: CycleDecision[] = [
    ...history.slice(-20),
    ...(cycle?.decisions ?? []),
  ];

  return (
    <div className="card flex flex-col gap-3 h-full min-h-[520px]">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold flex items-center gap-2 text-slate-200">
          <Brain className="w-4 h-4 text-brand" />
          AI Decision Feed
        </h2>
        <div className="flex items-center gap-2">
          {loading && (
            <span className="flex items-center gap-1 text-xs text-brand animate-pulse">
              <Loader2 className="w-3 h-3 animate-spin" />
              Agents running...
            </span>
          )}
          <span className="text-xs text-slate-500">{allDecisions.length} entries</span>
        </div>
      </div>

      {/* Pipeline visualization */}
      <div className="flex items-center gap-1 text-xs overflow-x-auto pb-1">
        {["Market", "Strategy", "Simulation", "Risk", "Execution"].map((step, i, arr) => (
          <div key={step} className="flex items-center gap-1 flex-shrink-0">
            <span className="bg-surface px-2 py-0.5 rounded border border-surface-border text-slate-400">
              {step}
            </span>
            {i < arr.length - 1 && <ChevronRight className="w-3 h-3 text-slate-600" />}
          </div>
        ))}
      </div>

      {/* Feed */}
      <div
        ref={feedRef}
        className="flex-1 overflow-y-auto space-y-0.5 rounded-lg bg-surface p-3 text-xs font-mono"
        style={{ maxHeight: "380px" }}
      >
        {allDecisions.length === 0 && !loading && (
          <div className="text-slate-500 text-center py-8">
            Click "Run AI Cycle" to start the autonomous decision pipeline
          </div>
        )}

        {loading && (
          <div className="agent-line text-slate-400 animate-pulse">
            <span>⏳</span>
            <span>Initializing agents...</span>
          </div>
        )}

        {allDecisions.map((d, i) => (
          <div key={i} className="agent-line">
            <span>{AGENT_ICONS[d.agent] || "🤖"}</span>
            <div className="flex-1 min-w-0">
              <span className={`font-semibold ${AGENT_COLORS[d.agent] || "text-slate-300"}`}>
                [{d.agent?.replace("Agent", "")}]
              </span>{" "}
              <span className="text-slate-400">{d.decision_type}</span>
              {d.explanation && (
                <p className="text-slate-500 mt-0.5 leading-relaxed break-words">
                  {d.explanation}
                </p>
              )}
            </div>
          </div>
        ))}

        {/* Executed trades highlight */}
        {cycle?.executed?.map((t, i) => (
          <div key={`trade-${i}`} className="agent-line bg-green-500/10 rounded px-2">
            <span>✅</span>
            <div>
              <span className="text-green-400 font-semibold">[EXECUTED]</span>{" "}
              <span className="text-slate-300">{t.message}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Simulation quick stats */}
      {cycle?.simulation && (
        <div className="grid grid-cols-4 gap-2">
          {[
            { label: "ROI",       value: `${cycle.simulation.roi_pct.toFixed(1)}%`,   color: cycle.simulation.roi_pct > 0 ? "text-green-400" : "text-red-400" },
            { label: "Drawdown",  value: `${cycle.simulation.max_drawdown.toFixed(1)}%`, color: "text-orange-400" },
            { label: "Win Rate",  value: `${cycle.simulation.win_rate.toFixed(0)}%`,  color: "text-cyan-400" },
            { label: "Sharpe",    value: cycle.simulation.sharpe_ratio.toFixed(2),    color: "text-purple-400" },
          ].map(stat => (
            <div key={stat.label} className="bg-surface rounded-lg p-2 text-center">
              <p className={`text-base font-bold ${stat.color}`}>{stat.value}</p>
              <p className="text-xs text-slate-500">{stat.label}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

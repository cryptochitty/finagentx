"use client";
import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { FlaskConical, Loader2 } from "lucide-react";
import { runSimulation, type SimulationResult } from "@/lib/api";

const STRATEGIES = ["momentum", "mean_reversion", "default"];
const SYMBOLS    = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"];

export default function TradeSimulation() {
  const [strategy, setStrategy] = useState("momentum");
  const [symbol,   setSymbol]   = useState("BTCUSDT");
  const [days,     setDays]     = useState(30);
  const [capital,  setCapital]  = useState(10_000);
  const [loading,  setLoading]  = useState(false);
  const [result,   setResult]   = useState<SimulationResult | null>(null);

  const handleRun = async () => {
    setLoading(true);
    try {
      const r = await runSimulation({ strategy, symbol, period_days: days, initial_capital: capital });
      setResult(r);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card flex flex-col gap-3">
      <h2 className="font-semibold flex items-center gap-2 text-slate-200">
        <FlaskConical className="w-4 h-4 text-yellow-400" />
        Backtest Simulator
      </h2>

      {/* Controls */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-slate-500 mb-1 block">Strategy</label>
          <select value={strategy} onChange={e => setStrategy(e.target.value)}
            className="w-full bg-surface border border-surface-border text-slate-200 text-xs
                       rounded-lg px-2 py-1.5 focus:outline-none focus:border-brand">
            {STRATEGIES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">Symbol</label>
          <select value={symbol} onChange={e => setSymbol(e.target.value)}
            className="w-full bg-surface border border-surface-border text-slate-200 text-xs
                       rounded-lg px-2 py-1.5 focus:outline-none focus:border-brand">
            {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">Days</label>
          <input type="number" value={days} onChange={e => setDays(+e.target.value)}
            min={7} max={365}
            className="w-full bg-surface border border-surface-border text-slate-200 text-xs
                       rounded-lg px-2 py-1.5 focus:outline-none focus:border-brand" />
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">Capital ($)</label>
          <input type="number" value={capital} onChange={e => setCapital(+e.target.value)}
            className="w-full bg-surface border border-surface-border text-slate-200 text-xs
                       rounded-lg px-2 py-1.5 focus:outline-none focus:border-brand" />
        </div>
      </div>

      <button onClick={handleRun} disabled={loading}
        className="w-full bg-yellow-500/20 border border-yellow-500/40 text-yellow-400
                   hover:bg-yellow-500/30 text-sm py-2 rounded-lg font-medium
                   transition-colors flex items-center justify-center gap-2 disabled:opacity-50">
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FlaskConical className="w-4 h-4" />}
        {loading ? "Running..." : "Run Backtest"}
      </button>

      {/* Results */}
      {result && (
        <div className="space-y-3 animate-fade-in">
          {/* Equity curve */}
          <ResponsiveContainer width="100%" height={100}>
            <AreaChart data={result.equity_curve}>
              <defs>
                <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="value" stroke="#6366f1" fill="url(#eq)"
                    strokeWidth={1.5} dot={false} />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "6px", fontSize: "11px" }}
                formatter={(v: number) => [`$${v.toLocaleString()}`, "Equity"]}
              />
            </AreaChart>
          </ResponsiveContainer>

          {/* Metrics */}
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "ROI",      value: `${result.roi_pct.toFixed(2)}%`,       color: result.roi_pct > 0 ? "text-green-400" : "text-red-400" },
              { label: "Drawdown", value: `${result.max_drawdown.toFixed(2)}%`,  color: "text-orange-400" },
              { label: "Win Rate", value: `${result.win_rate.toFixed(1)}%`,      color: "text-cyan-400" },
              { label: "Sharpe",   value: result.sharpe_ratio.toFixed(2),        color: "text-purple-400" },
              { label: "Trades",   value: result.total_trades.toString(),        color: "text-slate-300" },
            ].map(m => (
              <div key={m.label} className="bg-surface rounded p-2">
                <p className={`text-sm font-bold ${m.color}`}>{m.value}</p>
                <p className="text-xs text-slate-500">{m.label}</p>
              </div>
            ))}
          </div>

          <p className="text-xs text-slate-400 leading-relaxed bg-surface rounded p-2">
            {result.explanation}
          </p>
        </div>
      )}
    </div>
  );
}

"use client";
import { useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { Wallet, TrendingUp, AlertTriangle, Shield } from "lucide-react";
import { deposit, getZKBadge, type PortfolioData, type CycleResult } from "@/lib/api";

const COLORS = ["#6366f1", "#22d3ee", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6"];

interface Props {
  wallet:    string;
  portfolio: PortfolioData | null;
  cycle:     CycleResult   | null;
}

export default function PortfolioPanel({ wallet, portfolio, cycle }: Props) {
  const [depositing,  setDepositing]  = useState(false);
  const [depositAmt,  setDepositAmt]  = useState("1000");
  const [zkBadge,     setZkBadge]     = useState<Record<string, unknown> | null>(null);

  const handleDeposit = async () => {
    setDepositing(true);
    try {
      await deposit(wallet, parseFloat(depositAmt));
      window.location.reload();
    } finally {
      setDepositing(false);
    }
  };

  const handleVerify = async () => {
    const badge = await getZKBadge(wallet);
    setZkBadge(badge as unknown as Record<string, unknown>);
  };

  const riskScore = cycle?.risk?.score ?? portfolio?.risk_score ?? 0;
  const riskLevel = cycle?.risk?.level ?? "low";

  // Build pie data from holdings
  const pieData = portfolio?.holdings
    ? Object.entries(portfolio.holdings).map(([k, v]) => ({ name: k, value: v }))
    : [{ name: "Cash", value: portfolio?.total_value ?? 10_000 }];

  return (
    <div className="card flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold flex items-center gap-2 text-slate-200">
          <Wallet className="w-4 h-4 text-brand" /> Portfolio
        </h2>
        <button
          onClick={handleVerify}
          className="text-xs text-slate-400 hover:text-green-400 flex items-center gap-1 transition-colors"
        >
          <Shield className="w-3 h-3" /> ZK Verify
        </button>
      </div>

      {/* Total value */}
      <div className="text-center py-2">
        <p className="text-3xl font-bold text-white">
          ${(portfolio?.total_value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </p>
        <p className="text-xs text-slate-400 mt-1">Total Value (USDT)</p>
        <p className="text-sm text-slate-300 mt-1">
          Cash: ${(portfolio?.cash_balance ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </p>
      </div>

      {/* Pie chart */}
      <ResponsiveContainer width="100%" height={160}>
        <PieChart>
          <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={70}
               dataKey="value" nameKey="name" paddingAngle={3}>
            {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip
            contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "8px" }}
            labelStyle={{ color: "#f1f5f9" }}
            itemStyle={{ color: "#94a3b8" }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Holdings */}
      {portfolio?.holdings && Object.keys(portfolio.holdings).length > 0 && (
        <div className="space-y-1">
          {Object.entries(portfolio.holdings).map(([asset, amount], i) => (
            <div key={asset} className="flex justify-between text-sm">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                {asset}
              </span>
              <span className="text-slate-300">{amount.toFixed(4)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Risk score */}
      <div className={`flex items-center justify-between p-2.5 rounded-lg
        ${riskLevel === "low" ? "risk-low" : riskLevel === "medium" ? "risk-medium"
        : riskLevel === "high" ? "risk-high" : "risk-extreme"}`}>
        <span className="flex items-center gap-2 text-sm font-medium">
          <AlertTriangle className="w-4 h-4" />
          Risk Score
        </span>
        <span className="font-bold">{riskScore}/100 ({riskLevel})</span>
      </div>

      {/* Signals from latest cycle */}
      {cycle?.signals && cycle.signals.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs text-slate-400 font-medium uppercase tracking-wide">
            Latest Signals
          </p>
          {cycle.signals.map((s, i) => (
            <div key={i} className="flex items-center justify-between text-sm bg-surface rounded p-2">
              <span className={`font-semibold ${s.action === "buy" ? "text-green-400" : "text-red-400"}`}>
                {s.action.toUpperCase()} {s.symbol.replace("USDT", "")}
              </span>
              <span className="text-slate-400 text-xs">
                {(s.confidence * 100).toFixed(0)}% · {s.position_size}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Deposit form */}
      <div className="flex gap-2 mt-1">
        <input
          type="number"
          value={depositAmt}
          onChange={e => setDepositAmt(e.target.value)}
          className="flex-1 bg-surface border border-surface-border rounded-lg px-3 py-1.5 text-sm text-slate-200
                     focus:outline-none focus:border-brand"
          placeholder="Amount USDT"
        />
        <button
          onClick={handleDeposit}
          disabled={depositing}
          className="bg-brand/20 border border-brand text-brand hover:bg-brand hover:text-white
                     px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
        >
          {depositing ? "..." : "Deposit"}
        </button>
      </div>

      {/* ZK Badge */}
      {zkBadge && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 text-xs space-y-1">
          <p className="text-green-400 font-semibold flex items-center gap-1">
            <Shield className="w-3 h-3" /> ZK Identity Verified
          </p>
          <p className="text-slate-400">Scheme: {zkBadge.scheme as string}</p>
          <p className="text-slate-400 font-mono truncate">Proof: {zkBadge.proof_hash as string}</p>
          <div className="flex flex-wrap gap-1 mt-1">
            {(zkBadge.claims as string[]).map((c: string) => (
              <span key={c} className="bg-green-500/20 text-green-300 px-1.5 py-0.5 rounded text-xs">{c}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";
import { useState, useEffect, useCallback } from "react";
import { Brain, Wallet, RefreshCw, Shield } from "lucide-react";
import PortfolioPanel    from "@/components/PortfolioPanel";
import AIDecisionFeed    from "@/components/AIDecisionFeed";
import TradeSimulation   from "@/components/TradeSimulation";
import PaymentPanel      from "@/components/PaymentPanel";
import MarketTicker      from "@/components/MarketTicker";
import AutonomousToggle  from "@/components/AutonomousToggle";
import { runCycle, getPortfolio, type CycleResult, type PortfolioData } from "@/lib/api";

// Demo wallet – in production users connect MetaMask
const DEMO_WALLET = "0xDemoWallet123456789FinAgentX";

export default function Home() {
  const [wallet]      = useState(DEMO_WALLET);
  const [autonomous,  setAutonomous]  = useState(false);
  const [loading,     setLoading]     = useState(false);
  const [cycle,       setCycle]       = useState<CycleResult | null>(null);
  const [portfolio,   setPortfolio]   = useState<PortfolioData | null>(null);
  const [lastRun,     setLastRun]     = useState<string>("");

  // Load portfolio on mount
  useEffect(() => {
    getPortfolio(wallet).then(setPortfolio).catch(console.error);
  }, [wallet]);

  const handleRunCycle = useCallback(async () => {
    setLoading(true);
    try {
      const result = await runCycle(wallet, autonomous);
      setCycle(result);
      setLastRun(new Date().toLocaleTimeString());
      // Refresh portfolio after cycle
      const p = await getPortfolio(wallet);
      setPortfolio(p);
    } catch (err) {
      console.error("Cycle error:", err);
    } finally {
      setLoading(false);
    }
  }, [wallet, autonomous]);

  return (
    <div className="min-h-screen bg-surface">
      {/* ── Header ── */}
      <header className="border-b border-surface-border bg-surface-card/50 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand/20 rounded-lg">
              <Brain className="w-5 h-5 text-brand" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-none">FinAgentX</h1>
              <p className="text-xs text-slate-400">Autonomous On-Chain Financial Brain</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Wallet badge */}
            <div className="flex items-center gap-2 bg-surface-card border border-surface-border rounded-lg px-3 py-1.5 text-sm">
              <Wallet className="w-3.5 h-3.5 text-brand" />
              <span className="text-slate-300 font-mono text-xs">
                {wallet.slice(0, 6)}...{wallet.slice(-4)}
              </span>
              <Shield className="w-3.5 h-3.5 text-green-400" title="ZK Verified" />
            </div>

            {/* Autonomous toggle */}
            <AutonomousToggle value={autonomous} onChange={setAutonomous} />

            {/* Run button */}
            <button
              onClick={handleRunCycle}
              disabled={loading}
              className="flex items-center gap-2 bg-brand hover:bg-brand-dark disabled:opacity-50
                         disabled:cursor-not-allowed text-white text-sm font-medium
                         px-4 py-2 rounded-lg transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              {loading ? "Running..." : "Run AI Cycle"}
            </button>
          </div>
        </div>

        {/* Status bar */}
        {lastRun && (
          <div className="bg-green-500/10 border-t border-green-500/20 px-4 py-1 text-xs text-green-400 text-center">
            Last cycle: {lastRun} · Mode: {autonomous ? "Autonomous" : "Manual"} ·
            {cycle?.executed?.length ? ` ${cycle.executed.length} trade(s) executed` : " No trades executed"}
          </div>
        )}
      </header>

      {/* ── Main grid ── */}
      <main className="max-w-7xl mx-auto px-4 py-6 grid grid-cols-12 gap-4">

        {/* Market ticker – full width */}
        <div className="col-span-12">
          <MarketTicker />
        </div>

        {/* Portfolio – left column */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-4">
          <PortfolioPanel wallet={wallet} portfolio={portfolio} cycle={cycle} />
        </div>

        {/* Center: AI Decision Feed */}
        <div className="col-span-12 lg:col-span-5 flex flex-col gap-4">
          <AIDecisionFeed wallet={wallet} cycle={cycle} loading={loading} />
        </div>

        {/* Right: Simulation + Payments */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4">
          <TradeSimulation />
          <PaymentPanel wallet={wallet} />
        </div>

      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-slate-600 py-6">
        FinAgentX · HashKey Chain · {autonomous ? "Autonomous Mode Active" : "Manual Mode"} ·
        All trades are {autonomous ? "LIVE (simulated)" : "suggestions only"}
      </footer>
    </div>
  );
}

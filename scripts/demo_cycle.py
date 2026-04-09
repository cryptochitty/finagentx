"""
FinAgentX – Standalone demo script
Runs one full autonomous cycle without the HTTP server.
Great for testing agents in isolation and for hackathon live demos.

Usage:
  python scripts/demo_cycle.py

Output: colored terminal logs showing every agent decision step.
"""
import asyncio
import sys
import os
import json

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.orchestrator import AgentOrchestrator
from backend.database import init_db

GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
PURPLE = "\033[95m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

AGENT_COLORS = {
    "MarketIntelligenceAgent": CYAN,
    "StrategyAgent":           PURPLE,
    "SimulationAgent":         YELLOW,
    "RiskAgent":               RED,
    "ExecutionAgent":          GREEN,
    "PayFiAgent":              "\033[95m",
    "ExplainerAgent":          "\033[94m",
}


async def main():
    print(f"\n{BOLD}{'='*60}")
    print("  FinAgentX – Autonomous On-Chain Financial Brain")
    print(f"{'='*60}{RESET}\n")

    init_db()
    orchestrator = AgentOrchestrator()

    # Fix random seed so demo always produces interesting signals
    import random; random.seed(3)

    wallet     = "0xDemoWallet_FinAgentX_Hackathon_2025"
    autonomous = True   # Set to False for manual mode (signals only)

    print(f"{BOLD}Wallet:{RESET}     {wallet}")
    print(f"{BOLD}Mode:{RESET}       {'AUTONOMOUS' if autonomous else 'Manual'}")
    print(f"{BOLD}Simulation:{RESET} ON (no real txs)\n")
    print(f"{'─'*60}\n")

    # Run cycle
    result = await orchestrator.run_autonomous_cycle(
        wallet=wallet,
        autonomous=autonomous,
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    )

    # Print each decision
    print(f"{BOLD}DECISION LOG:{RESET}")
    for d in result.decisions:
        color = AGENT_COLORS.get(d.agent, RESET)
        print(f"\n  {color}{BOLD}[{d.agent}]{RESET}")
        print(f"  Type: {d.decision_type}")
        if d.explanation:
            print(f"  → {d.explanation[:200]}")

    # Market summary
    print(f"\n{BOLD}{'─'*60}")
    print("MARKET SNAPSHOT:")
    for m in result.market_data:
        trend = "↑" if m.change_24h > 0 else "↓"
        print(f"  {m.symbol:<12} ${m.price:>12,.2f}  {trend} {m.change_24h:+.2f}%  RSI={m.rsi}  [{m.sentiment}]")

    # Signals
    print(f"\n{BOLD}SIGNALS:{RESET}")
    if result.signals:
        for s in result.signals:
            action_color = GREEN if s.action == "buy" else RED
            print(f"  {action_color}{s.action.upper()}{RESET} {s.symbol:<12} "
                  f"confidence={s.confidence:.0%}  size={s.position_size}%  → {s.rationale}")
    else:
        print("  No actionable signals this cycle")

    # Risk
    r = result.risk
    risk_color = GREEN if r.level == "low" else YELLOW if r.level == "medium" else RED
    print(f"\n{BOLD}RISK ASSESSMENT:{RESET}")
    print(f"  Score: {risk_color}{r.score}/100 ({r.level}){RESET}  Approved: {'✅' if r.approved else '❌'}")
    for flag in r.flags:
        print(f"  ⚠ {flag}")

    # Simulation
    if result.simulation:
        sim = result.simulation
        roi_color = GREEN if sim['roi_pct'] > 0 else RED
        print(f"\n{BOLD}BACKTEST RESULTS:{RESET}")
        print(f"  ROI:       {roi_color}{sim['roi_pct']:+.2f}%{RESET}")
        print(f"  Drawdown:  {YELLOW}{sim['max_drawdown']:.2f}%{RESET}")
        print(f"  Win Rate:  {sim['win_rate']:.1f}%")
        print(f"  Sharpe:    {sim['sharpe_ratio']:.2f}")
        print(f"  Trades:    {sim['total_trades']}")

    # Executed
    print(f"\n{BOLD}EXECUTION:{RESET}")
    if result.executed:
        for t in result.executed:
            print(f"  {GREEN}✅ {t.message}{RESET}")
            if t.tx_hash:
                print(f"     tx: {t.tx_hash}")
    else:
        print(f"  {'No trades executed (manual mode or risk blocked)' if not autonomous else 'No approved signals'}")

    print(f"\n{BOLD}{'='*60}")
    print("  Cycle complete!")
    print(f"{'='*60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())

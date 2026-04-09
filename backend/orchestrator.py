"""
FinAgentX – Agent Orchestrator
Coordinates the full decision pipeline:
  Market → Strategy → Simulation → Risk → Execution → Explain

Uses shared memory (a list) so every downstream agent has full context
of what prior agents decided. This is the "brain" of the system.
"""
import logging
from typing import List, Optional, Dict

from backend.agents import (
    MarketIntelligenceAgent,
    StrategyAgent,
    SimulationAgent,
    RiskAgent,
    PayFiAgent,
    ExecutionAgent,
    ExplainerAgent,
)
from backend.models import (
    CycleResult, MarketData, StrategySignal, RiskAssessment,
    SimulationRequest, TradeResponse, AgentDecision
)
from backend.config import SIMULATION_MODE

logger = logging.getLogger("finagentx.orchestrator")


class AgentOrchestrator:
    """
    Stateless orchestrator: creates a fresh shared memory list each cycle
    so agents can see each other's decisions, but state doesn't bleed between runs.
    """

    async def run_autonomous_cycle(
        self,
        wallet:     str,
        autonomous: bool = False,
        symbols:    Optional[List[str]] = None,
        portfolio:  Optional[Dict]      = None,
        db=None,
    ) -> CycleResult:
        """
        Full autonomous decision cycle.
        autonomous=True  → executes trades if risk approves
        autonomous=False → generates signals only (manual mode)
        """
        # ── Shared memory across all agents in this cycle ──────────────────
        memory: List[Dict] = []

        logger.info(f"[Cycle] Starting for wallet={wallet[:10]}... autonomous={autonomous}")

        # ── Step 1: Market Intelligence ────────────────────────────────────
        market_agent = MarketIntelligenceAgent(shared_memory=memory)
        market_data  = await market_agent.run(symbols)
        logger.info(f"[Cycle] Market scan complete: {len(market_data)} assets")

        # ── Step 2: Strategy Generation ────────────────────────────────────
        strategy_agent = StrategyAgent(shared_memory=memory)
        signals        = await strategy_agent.run(market_data, portfolio)
        logger.info(f"[Cycle] Signals generated: {len(signals)}")

        if not signals:
            logger.info("[Cycle] No actionable signals – cycle complete")
            return CycleResult(
                wallet=wallet, market_data=market_data,
                signals=[], risk=RiskAssessment(score=0, level="low", approved=False),
                decisions=self._extract_decisions(memory), autonomous=autonomous,
            )

        # ── Step 3: Simulation (backtest preview for top signal) ───────────
        sim_agent  = SimulationAgent(shared_memory=memory)
        top_signal = signals[0]
        sim_req    = SimulationRequest(symbol=top_signal.symbol, period_days=30)
        sim_result = await sim_agent.run(sim_req, signals)
        logger.info(f"[Cycle] Simulation complete: ROI={sim_result.roi_pct:.1f}%")

        # ── Step 4: Risk Assessment ────────────────────────────────────────
        risk_agent = RiskAgent(shared_memory=memory)
        risk       = await risk_agent.run(
            top_signal, market_data, portfolio, sim_result.dict()
        )
        logger.info(f"[Cycle] Risk: {risk.level} ({risk.score}/100) approved={risk.approved}")

        # ── Step 5: Execution (only in autonomous mode with approval) ──────
        executed: List[TradeResponse] = []
        if autonomous and risk.approved:
            exec_agent = ExecutionAgent(shared_memory=memory)
            portfolio_ctx = portfolio or {"wallet": wallet, "total_value": 10_000, "cash_balance": 10_000}
            trade = await exec_agent.execute_trade(top_signal, risk, portfolio_ctx, db)
            executed.append(trade)
            logger.info(f"[Cycle] Trade executed: {trade.status} tx={trade.tx_hash}")

        # ── Step 6: Explainer ──────────────────────────────────────────────
        explainer = ExplainerAgent(shared_memory=memory)
        cycle     = CycleResult(
            wallet      = wallet,
            market_data = market_data,
            signals     = signals,
            risk        = risk,
            simulation  = sim_result.dict(),
            executed    = executed,
            decisions   = self._extract_decisions(memory),
            autonomous  = autonomous,
        )
        await explainer.explain_cycle(cycle)

        logger.info(f"[Cycle] Complete. Decisions logged: {len(memory)}")
        return cycle

    async def run_payfi_cycle(self, wallet: str, db=None) -> Dict:
        """Check and process all due payments for a wallet."""
        memory: List[Dict] = []
        payfi = PayFiAgent(shared_memory=memory)
        due   = await payfi.check_due_payments(wallet, db)
        if due:
            plan = await payfi.optimize_payment_batch(due)
            return {"due_payments": due, "optimization": plan}
        return {"due_payments": [], "message": "No payments due"}

    # ── Helper ─────────────────────────────────────────────────────────────

    def _extract_decisions(self, memory: List[Dict]) -> List[AgentDecision]:
        decisions = []
        for entry in memory:
            try:
                decisions.append(AgentDecision(
                    agent         = entry["agent"],
                    decision_type = entry["decision_type"],
                    payload       = entry["payload"] if isinstance(entry["payload"], dict) else {"data": entry["payload"]},
                    explanation   = entry.get("explanation", ""),
                ))
            except Exception:
                pass
        return decisions

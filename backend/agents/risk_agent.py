"""
FinAgentX – Risk Agent
Evaluates every trade signal before execution.
Applies: position limits, stop-loss, portfolio concentration, volatility checks.
"""
from typing import List, Dict, Optional

from .base_agent import BaseAgent
from backend.config import (
    MAX_TRADE_SIZE_PCT, MAX_DRAWDOWN_PCT,
    STOP_LOSS_PCT, MAX_RISK_SCORE
)
from backend.models import StrategySignal, RiskAssessment, MarketData


class RiskAgent(BaseAgent):
    name = "RiskAgent"

    async def run(
        self,
        signal: StrategySignal,
        market_data: List[MarketData],
        portfolio: Optional[Dict] = None,
        simulation_result: Optional[Dict] = None,
    ) -> RiskAssessment:
        """
        Score the risk of executing a trade signal.
        Returns RiskAssessment with approved flag and optional adjusted position size.
        """
        flags  = []
        score  = 0

        # ── Rule 1: Position size limit ───────────────────────────────────────
        if signal.position_size > MAX_TRADE_SIZE_PCT:
            flags.append(f"Position size {signal.position_size}% exceeds max {MAX_TRADE_SIZE_PCT}%")
            score += 20

        # ── Rule 2: Low confidence signal ─────────────────────────────────────
        if signal.confidence < 0.55:
            flags.append(f"Low confidence signal: {signal.confidence:.2f}")
            score += 15

        # ── Rule 3: Portfolio concentration check ─────────────────────────────
        if portfolio:
            total_value = portfolio.get("total_value", 1)
            holdings    = portfolio.get("holdings", {})
            base_asset  = signal.symbol.replace("USDT", "")
            current_pct = holdings.get(base_asset, 0) / max(total_value, 1) * 100
            if current_pct + signal.position_size > 30:
                flags.append(f"Concentration risk: {current_pct + signal.position_size:.1f}% in {base_asset}")
                score += 25

        # ── Rule 4: High volatility check (RSI extremes) ──────────────────────
        market_map = {d.symbol: d for d in market_data}
        md = market_map.get(signal.symbol)
        if md:
            if md.rsi and (md.rsi > 80 or md.rsi < 20):
                flags.append(f"Extreme RSI: {md.rsi} – high reversal risk")
                score += 20
            if abs(md.change_24h) > 10:
                flags.append(f"Extreme 24h move: {md.change_24h:.1f}%")
                score += 15

        # ── Rule 5: Simulation drawdown check ─────────────────────────────────
        if simulation_result:
            dd = simulation_result.get("max_drawdown", 0)
            if dd > MAX_DRAWDOWN_PCT:
                flags.append(f"Backtest drawdown {dd:.1f}% exceeds limit {MAX_DRAWDOWN_PCT}%")
                score += 20

        # ── Rule 6: Stop loss present ──────────────────────────────────────────
        if not signal.stop_loss:
            flags.append("No stop loss defined")
            score += 10

        # ── Determine level and approval ──────────────────────────────────────
        if score < 20:
            level = "low"
        elif score < 45:
            level = "medium"
        elif score < 70:
            level = "high"
        else:
            level = "extreme"

        approved       = score <= MAX_RISK_SCORE
        adjusted_size  = signal.position_size if approved else min(signal.position_size, 3.0)

        # Use LLM to add narrative reasoning (optional, non-blocking)
        explanation = self._build_explanation(signal, score, level, flags, approved)

        assessment = RiskAssessment(
            score         = min(100, score),
            level         = level,
            approved      = approved,
            flags         = flags,
            adjusted_size = adjusted_size,
        )

        self.log(
            "risk_assessment",
            assessment.dict(),
            explanation
        )
        return assessment

    def _build_explanation(
        self, signal: StrategySignal, score: int,
        level: str, flags: List[str], approved: bool
    ) -> str:
        action = "APPROVED" if approved else "BLOCKED"
        flag_str = "; ".join(flags) if flags else "No flags"
        return (
            f"[{action}] {signal.action.upper()} {signal.symbol} — "
            f"Risk score: {score}/100 ({level}). Flags: {flag_str}."
        )

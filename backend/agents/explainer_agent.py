"""
FinAgentX – Explainer Agent
Converts raw agent decisions into clear, user-friendly explanations.
Also generates ZK-style identity verification badges (mock).
"""
import json
from typing import List, Dict, Any

from .base_agent import BaseAgent
from backend.models import CycleResult, AgentDecision


class ExplainerAgent(BaseAgent):
    name = "ExplainerAgent"

    SYSTEM_PROMPT = """You are the ExplainerAgent in FinAgentX, an AI financial system.
Your job: convert technical trading decisions into clear English for non-expert users.
Be concise (2-3 sentences max per decision). Focus on WHY, not HOW.
Format: plain text, no markdown, no JSON."""

    async def explain_cycle(self, cycle: CycleResult) -> List[str]:
        """
        Generate a list of plain-English explanations for everything
        that happened in an autonomous decision cycle.
        """
        explanations = []

        # Market summary
        if cycle.market_data:
            movers = sorted(cycle.market_data, key=lambda d: abs(d.change_24h), reverse=True)[:3]
            mover_str = ", ".join(f"{d.symbol} {'+' if d.change_24h > 0 else ''}{d.change_24h:.1f}%" for d in movers)
            explanations.append(f"Market scan: Top movers — {mover_str}.")

        # Signals
        for signal in cycle.signals:
            prompt = (
                f"Explain this trade signal in 2 sentences: "
                f"{signal.action.upper()} {signal.symbol}, confidence={signal.confidence:.0%}, "
                f"rationale='{signal.rationale}', position_size={signal.position_size}%"
            )
            text = self.ask_llm(prompt, self.SYSTEM_PROMPT)
            explanations.append(f"Signal: {text.strip()}")

        # Risk assessment
        if cycle.risk:
            status = "approved" if cycle.risk.approved else "blocked"
            flag_str = "; ".join(cycle.risk.flags[:2]) if cycle.risk.flags else "no issues"
            explanations.append(
                f"Risk check ({status}): Score {cycle.risk.score}/100 ({cycle.risk.level} risk). "
                f"Flags: {flag_str}."
            )

        # Executed trades
        for trade in cycle.executed:
            action_word = "Purchased" if "buy" in trade.message.lower() else "Sold"
            explanations.append(
                f"Execution: {action_word} {trade.amount:.4f} units at ${trade.price:,.2f}. "
                f"Status: {trade.status}."
            )

        # Simulation
        if cycle.simulation:
            roi = cycle.simulation.get("roi_pct", 0)
            dd  = cycle.simulation.get("max_drawdown", 0)
            explanations.append(
                f"Backtest preview: This strategy returned {roi:.1f}% with "
                f"{dd:.1f}% maximum drawdown historically."
            )

        self.log("explanations_generated", {"count": len(explanations)},
                 f"Explained {len(explanations)} decision steps for cycle")

        return explanations

    async def explain_decision(self, decision: Dict) -> str:
        """Single decision → human explanation."""
        prompt = f"Explain this AI financial decision briefly:\n{json.dumps(decision, indent=2, default=str)}"
        return self.ask_llm(prompt, self.SYSTEM_PROMPT).strip()

    def generate_zk_badge(self, wallet: str) -> Dict:
        """
        Mock ZK identity verification badge.
        In production: integrate with ZK proof system (e.g., RISC Zero, zkSync identity).
        """
        import hashlib
        proof = hashlib.sha256(f"zk:{wallet}:finagentx".encode()).hexdigest()
        return {
            "wallet":    wallet,
            "verified":  True,
            "scheme":    "ZK-SNARK (mock)",
            "proof_hash": f"0x{proof[:32]}",
            "claims": [
                "wallet_ownership_verified",
                "not_sanctioned",
                "kyc_level_1",
            ],
            "issued_at": "2025-01-01T00:00:00Z",
            "note": "This is a mock ZK proof for demo purposes.",
        }

    def risk_score_narrative(self, score: int, level: str, flags: List[str]) -> str:
        """Generate a color-coded risk narrative for the UI."""
        color_map = {"low": "green", "medium": "yellow", "high": "orange", "extreme": "red"}
        color = color_map.get(level, "gray")
        flag_text = f" Key concerns: {', '.join(flags[:2])}." if flags else ""
        return {
            "narrative": (
                f"Risk level is {level.upper()} ({score}/100).{flag_text} "
                f"{'Safe to proceed.' if level in ('low','medium') else 'Exercise caution or reduce position.'}"
            ),
            "color": color,
            "score": score,
        }

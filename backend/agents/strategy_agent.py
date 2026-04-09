"""
FinAgentX – Strategy Agent
Analyses market data and generates trade signals using LLM + rule-based logic.
"""
import json
from typing import List, Dict, Optional

from .base_agent import BaseAgent
from backend.models import MarketData, StrategySignal, Direction


class StrategyAgent(BaseAgent):
    name = "StrategyAgent"

    SYSTEM_PROMPT = """You are StrategyAgent in the FinAgentX system.
Given market data, generate trading signals as a JSON array.
Each signal must have:
  symbol, action (buy/sell), confidence (0-1), rationale, target_price, stop_loss, position_size (% of portfolio 1-10)
Respond ONLY with valid JSON array. No markdown, no explanation outside JSON."""

    async def run(self, market_data: List[MarketData], portfolio: Optional[Dict] = None) -> List[StrategySignal]:
        """
        Generate trading signals for the given market snapshot.
        Uses LLM reasoning + deterministic fallback for reliability.
        """
        # Build LLM prompt with market data
        market_summary = [
            {
                "symbol":     d.symbol,
                "price":      d.price,
                "change_24h": d.change_24h,
                "rsi":        d.rsi,
                "sentiment":  d.sentiment,
                "trend":      d.trend,
                "volume_24h": d.volume_24h,
            }
            for d in market_data
        ]

        prompt = (
            f"Portfolio: {json.dumps(portfolio or {})}\n"
            f"Market snapshot:\n{json.dumps(market_summary, indent=2)}\n\n"
            "Generate trading signals based on momentum, RSI, and sentiment. "
            "Only generate signals where confidence > 0.5. Max 3 signals."
        )

        raw = self.ask_llm(prompt, self.SYSTEM_PROMPT)

        # Parse LLM output; fall back to deterministic signals on parse failure
        signals = self._parse_llm_signals(raw, market_data)

        # Validate and cap position sizes
        signals = [self._validate_signal(s) for s in signals]

        self.log(
            "signals_generated",
            [s.dict() for s in signals],
            f"Generated {len(signals)} signals: {[s.symbol for s in signals]}"
        )
        return signals

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse_llm_signals(self, raw: str, market_data: List[MarketData]) -> List[StrategySignal]:
        """Try to parse LLM JSON; fall back to rule-based if it fails."""
        try:
            # Extract JSON array from LLM output (it may wrap in markdown)
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                signals = []
                for item in data:
                    signals.append(StrategySignal(
                        symbol        = item["symbol"],
                        action        = Direction(item["action"]),
                        confidence    = float(item.get("confidence", 0.6)),
                        rationale     = item.get("rationale", "LLM signal"),
                        target_price  = item.get("target_price"),
                        stop_loss     = item.get("stop_loss"),
                        position_size = float(item.get("position_size", 5)),
                    ))
                return signals
        except Exception as e:
            self.logger.warning(f"LLM signal parse failed: {e} – using rule-based fallback")

        return self._rule_based_signals(market_data)

    def _rule_based_signals(self, market_data: List[MarketData]) -> List[StrategySignal]:
        """
        Deterministic momentum strategy.
        BUY  if RSI < 40 and sentiment != bearish (oversold)
        SELL if RSI > 70 and sentiment != bullish (overbought)
        """
        signals = []
        for d in market_data:
            if d.rsi is None:
                continue

            if d.rsi < 45 and d.sentiment != "bearish":
                signals.append(StrategySignal(
                    symbol        = d.symbol,
                    action        = Direction.buy,
                    confidence    = round(0.5 + (45 - d.rsi) / 90, 2),
                    rationale     = f"Oversold: RSI={d.rsi}, sentiment={d.sentiment}",
                    target_price  = round(d.price * 1.05, 4),
                    stop_loss     = round(d.price * 0.97, 4),
                    position_size = 5.0,
                ))
            elif d.rsi > 60 and d.sentiment != "bullish":
                signals.append(StrategySignal(
                    symbol        = d.symbol,
                    action        = Direction.sell,
                    confidence    = round(0.5 + (d.rsi - 65) / 70, 2),
                    rationale     = f"Overbought: RSI={d.rsi}, sentiment={d.sentiment}",
                    target_price  = round(d.price * 0.95, 4),
                    stop_loss     = round(d.price * 1.03, 4),
                    position_size = 5.0,
                ))

        return signals[:3]   # Cap at 3 signals

    def _validate_signal(self, s: StrategySignal) -> StrategySignal:
        """Clamp position size and confidence to safe ranges."""
        s.position_size = min(s.position_size, 10.0)
        s.confidence    = max(0.0, min(1.0, s.confidence))
        return s

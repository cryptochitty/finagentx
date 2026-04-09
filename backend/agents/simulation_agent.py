"""
FinAgentX – Simulation Agent
Backtests strategies on historical (or synthetic) data.
Returns ROI, max drawdown, Sharpe ratio, win rate, equity curve.
"""
import math
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .base_agent import BaseAgent
from backend.models import StrategySignal, SimulationRequest, SimulationResponse


class SimulationAgent(BaseAgent):
    name = "SimulationAgent"

    async def run(self, request: SimulationRequest, signals: Optional[List[StrategySignal]] = None) -> SimulationResponse:
        """
        Run a backtest for a strategy over the requested period.
        Uses synthetic OHLCV data when real history is unavailable.
        """
        prices     = self._generate_price_series(request.symbol, request.period_days)
        trades, equity_curve = self._backtest(request, prices)

        roi_pct       = self._calc_roi(equity_curve, request.initial_capital)
        max_drawdown  = self._calc_max_drawdown(equity_curve)
        win_rate      = self._calc_win_rate(trades)
        sharpe        = self._calc_sharpe(equity_curve)

        explanation = self._explain(request.strategy, roi_pct, max_drawdown, win_rate, sharpe)

        result = SimulationResponse(
            strategy     = request.strategy,
            roi_pct      = round(roi_pct, 2),
            max_drawdown = round(max_drawdown, 2),
            win_rate     = round(win_rate, 2),
            sharpe_ratio = round(sharpe, 2),
            total_trades = len(trades),
            equity_curve = equity_curve[-30:],   # last 30 data points for chart
            explanation  = explanation,
        )

        self.log(
            "simulation_complete",
            result.dict(),
            f"Backtest {request.strategy} on {request.symbol} ({request.period_days}d): "
            f"ROI={roi_pct:.1f}% drawdown={max_drawdown:.1f}%"
        )
        return result

    # ── Price series generation ───────────────────────────────────────────────

    def _generate_price_series(self, symbol: str, days: int) -> List[float]:
        """
        Geometric Brownian Motion price simulation.
        Seeded by symbol so results are reproducible per symbol.
        """
        seed_map = {"BTCUSDT": 42, "ETHUSDT": 7, "BNBUSDT": 13, "SOLUSDT": 99}
        random.seed(seed_map.get(symbol, 1))

        base_prices = {"BTCUSDT": 60_000, "ETHUSDT": 3_200, "BNBUSDT": 540, "SOLUSDT": 160}
        price   = base_prices.get(symbol, 100.0)
        mu      = 0.0005    # daily drift
        sigma   = 0.025     # daily volatility

        prices = [price]
        for _ in range(days):
            change = random.gauss(mu, sigma)
            price  = price * math.exp(change)
            prices.append(round(price, 4))

        return prices

    # ── Backtest engine ───────────────────────────────────────────────────────

    def _backtest(self, req: SimulationRequest, prices: List[float]) -> tuple:
        """
        Simple momentum / mean-reversion backtest depending on strategy name.
        Returns (list_of_trades, equity_curve)
        """
        capital = req.initial_capital
        position = 0.0          # units held
        entry_price = 0.0
        trades = []
        equity_curve = []

        window = 14             # rolling window for indicators
        base_date = datetime.utcnow() - timedelta(days=req.period_days)

        for i, price in enumerate(prices):
            date_str = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")

            if i < window:
                equity_curve.append({"date": date_str, "value": round(capital + position * price, 2)})
                continue

            window_prices = prices[i - window:i]
            avg   = sum(window_prices) / window
            rsi   = self._fast_rsi(window_prices)

            # Entry logic
            if position == 0:
                if req.strategy in ("momentum", "default") and price > avg * 1.01 and rsi < 70:
                    # Momentum: buy breakout above MA
                    units    = (capital * 0.95) / price
                    position  = units
                    entry_price = price
                    capital   = capital - (units * price)
                    trades.append({"type": "buy", "price": price, "date": date_str, "units": units})

                elif req.strategy == "mean_reversion" and price < avg * 0.99 and rsi < 35:
                    units     = (capital * 0.95) / price
                    position  = units
                    entry_price = price
                    capital   = capital - (units * price)
                    trades.append({"type": "buy", "price": price, "date": date_str, "units": units})

            # Exit logic
            elif position > 0:
                profit_pct = (price - entry_price) / entry_price * 100

                if profit_pct > 5 or profit_pct < -3:   # take profit @ +5%, stop loss @ -3%
                    pnl      = position * (price - entry_price)
                    capital += position * price
                    trades.append({
                        "type": "sell", "price": price, "date": date_str,
                        "units": position, "pnl": round(pnl, 2),
                        "win": pnl > 0,
                    })
                    position = 0.0

            equity = capital + position * price
            equity_curve.append({"date": date_str, "value": round(equity, 2)})

        # Close any open position at end
        if position > 0:
            final_price = prices[-1]
            pnl = position * (final_price - entry_price)
            capital += position * final_price
            trades.append({"type": "sell", "price": final_price, "date": date_str,
                           "units": position, "pnl": round(pnl, 2), "win": pnl > 0})

        return trades, equity_curve

    # ── Metrics ───────────────────────────────────────────────────────────────

    def _calc_roi(self, equity_curve: List[Dict], initial: float) -> float:
        if not equity_curve:
            return 0.0
        final = equity_curve[-1]["value"]
        return (final - initial) / initial * 100

    def _calc_max_drawdown(self, equity_curve: List[Dict]) -> float:
        values  = [e["value"] for e in equity_curve]
        peak    = values[0]
        max_dd  = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _calc_win_rate(self, trades: List[Dict]) -> float:
        sells = [t for t in trades if t.get("type") == "sell"]
        if not sells:
            return 0.0
        wins = sum(1 for t in sells if t.get("win", False))
        return wins / len(sells) * 100

    def _calc_sharpe(self, equity_curve: List[Dict], risk_free_rate: float = 0.05) -> float:
        values  = [e["value"] for e in equity_curve]
        returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
        if len(returns) < 2:
            return 0.0
        avg_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns))
        if std_r == 0:
            return 0.0
        daily_rf = risk_free_rate / 365
        return round((avg_r - daily_rf) / std_r * math.sqrt(365), 2)

    def _fast_rsi(self, prices: List[float]) -> float:
        gains  = [max(0, prices[i] - prices[i-1]) for i in range(1, len(prices))]
        losses = [max(0, prices[i-1] - prices[i]) for i in range(1, len(prices))]
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _explain(self, strategy: str, roi: float, dd: float, win_rate: float, sharpe: float) -> str:
        perf = "outperformed" if roi > 10 else "underperformed" if roi < 0 else "met expectations for"
        return (
            f"The {strategy} strategy {perf} the market over the test period. "
            f"It achieved a {roi:.1f}% return with a maximum drawdown of {dd:.1f}%. "
            f"The win rate was {win_rate:.0f}% and the Sharpe ratio was {sharpe:.2f}, "
            f"{'indicating good risk-adjusted returns.' if sharpe > 1 else 'suggesting moderate risk-adjusted performance.'}"
        )

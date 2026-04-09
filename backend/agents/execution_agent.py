"""
FinAgentX – Execution Agent
Executes trades via smart contracts (real or simulated).

Live mode:  sends tx to TradeExecutor.executeTrade() on HashKey Chain
Sim mode:   returns realistic mock response, no on-chain state change
"""
import time
import random
import hashlib
from datetime import datetime
from typing import Optional, Dict

from .base_agent import BaseAgent
from backend.config import (
    SIMULATION_MODE, CHAIN_ID,
    PRIVATE_KEY, VAULT_ADDRESS, TRADE_EXEC_ADDRESS,
)
from backend.models import TradeRequest, TradeResponse, TradeStatus, StrategySignal, RiskAssessment


class ExecutionAgent(BaseAgent):
    name = "ExecutionAgent"

    async def execute_trade(
        self,
        signal:    StrategySignal,
        risk:      RiskAssessment,
        portfolio: Dict,
        db=None,
    ) -> TradeResponse:
        """
        Execute a trade from a strategy signal + risk assessment.
        Routes to simulation or on-chain execution based on SIMULATION_MODE / PRIVATE_KEY.
        """
        if not risk.approved:
            return TradeResponse(
                id=0, status=TradeStatus.failed,
                price=0, amount=0,
                message=f"Trade blocked by Risk Agent (score={risk.score})",
            )

        total     = portfolio.get("total_value", 10_000)
        pct       = (risk.adjusted_size or signal.position_size) / 100
        trade_usd = total * pct
        price     = self._get_execution_price(signal.symbol)
        units     = trade_usd / price if price > 0 else 0

        request = TradeRequest(
            wallet    = portfolio.get("wallet", "0x0000"),
            symbol    = signal.symbol,
            direction = signal.action,
            amount    = units,
            simulate  = SIMULATION_MODE,
        )

        if SIMULATION_MODE or not PRIVATE_KEY or not TRADE_EXEC_ADDRESS:
            response = await self._simulate_trade(request, price)
        else:
            response = await self._execute_onchain(request, price)

        if db and response.id == 0:
            response = await self._save_trade(db, request, response, signal, risk)

        self.log(
            "trade_executed",
            response.dict(),
            (
                f"{signal.action.upper()} {signal.symbol}: "
                f"{units:.4f} units @ ${price:,.2f} "
                f"[{response.status}] tx={response.tx_hash or 'simulated'}"
            ),
        )
        return response

    # ── Simulation ────────────────────────────────────────────────────────────

    async def _simulate_trade(self, req: TradeRequest, price: float) -> TradeResponse:
        slippage   = random.uniform(0.001, 0.003)
        exec_price = price * (1 + slippage if req.direction == "buy" else 1 - slippage)
        fake_hash  = "0x" + hashlib.sha256(
            f"{req.wallet}{req.symbol}{time.time()}".encode()
        ).hexdigest()[:40]
        return TradeResponse(
            id      = random.randint(1000, 9999),
            status  = TradeStatus.simulated,
            tx_hash = fake_hash,
            price   = round(exec_price, 4),
            amount  = round(req.amount, 6),
            message = f"[SIMULATED] {req.direction.upper()} {req.amount:.4f} {req.symbol} @ ${exec_price:,.2f}",
        )

    # ── Live on-chain execution ───────────────────────────────────────────────

    async def _execute_onchain(self, req: TradeRequest, price: float) -> TradeResponse:
        """
        Calls TradeExecutor.executeTrade() on HashKey Chain.
        Requires: PRIVATE_KEY, TRADE_EXEC_ADDRESS, RPC_URL in environment.
        The PRIVATE_KEY wallet must be set as agentWallet in TradeExecutor.
        """
        try:
            from web3 import Web3
            from backend.chain import get_web3, get_account, get_trade_executor, send_tx

            w3 = get_web3()
            if not w3 or not w3.is_connected():
                raise ConnectionError("Cannot connect to RPC")

            account  = get_account(w3)
            if not account:
                raise ValueError("No valid PRIVATE_KEY configured")

            executor = get_trade_executor(w3)
            if not executor:
                raise ValueError("TRADE_EXEC_ADDRESS not configured")

            direction_int = 0 if req.direction == "buy" else 1
            # Amount in wei — treat units as ETH-equivalent for on-chain accounting
            amount_wei    = w3.to_wei(min(req.amount, 0.01), "ether")  # cap at 0.01 for safety
            # minPrice with 1% slippage tolerance, encoded as price * 1e8
            min_price_enc = int(price * 0.99 * 1e8) if req.direction == "buy" else 0

            # TradeExecutor.executeTrade(user, symbol, direction, amount, minPrice)
            fn = executor.functions.executeTrade(
                Web3.to_checksum_address(req.wallet),
                req.symbol,
                direction_int,
                amount_wei,
                min_price_enc,
            )

            receipt, tx_hash = send_tx(w3, account, fn)
            status = TradeStatus.executed if receipt.status == 1 else TradeStatus.failed

            # Try to decode tradeId from logs
            trade_id = receipt.blockNumber
            try:
                logs = executor.events.TradeRequested().process_receipt(receipt)
                if logs:
                    trade_id = int(logs[0]["args"]["tradeId"])
            except Exception:
                pass

            return TradeResponse(
                id      = trade_id,
                status  = status,
                tx_hash = tx_hash,
                price   = price,
                amount  = req.amount,
                message = (
                    f"On-chain {'succeeded' if status == TradeStatus.executed else 'FAILED'}: "
                    f"{tx_hash} | chainId={CHAIN_ID}"
                ),
            )

        except ImportError:
            self.logger.error("web3 not installed – falling back to simulation")
            return await self._simulate_trade(req, price)

        except Exception as e:
            self.logger.error("On-chain execution error: %s", e)
            return TradeResponse(
                id=0, status=TradeStatus.failed,
                price=price, amount=req.amount,
                message=f"Execution error: {e}",
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_execution_price(self, symbol: str) -> float:
        """Pull latest price from shared memory (set by MarketAgent) or use defaults."""
        for entry in reversed(self.memory):
            if entry.get("agent") == "MarketIntelligenceAgent":
                for item in entry.get("payload", []):
                    if item.get("symbol") == symbol:
                        return float(item.get("price", 1))
        defaults = {"BTCUSDT": 68_000, "ETHUSDT": 3_500, "BNBUSDT": 580, "SOLUSDT": 175}
        return defaults.get(symbol, 1.0)

    async def _save_trade(self, db, req, resp, signal, risk):
        from backend.database import Trade
        t = Trade(
            wallet     = req.wallet,
            symbol     = req.symbol,
            direction  = req.direction,
            amount     = resp.amount,
            price      = resp.price,
            status     = resp.status,
            tx_hash    = resp.tx_hash,
            risk_score = risk.score,
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        resp.id = t.id
        return resp

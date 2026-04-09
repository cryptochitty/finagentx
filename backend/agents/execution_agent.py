"""
FinAgentX – Execution Agent
Executes trades via smart contracts (real or simulated).
Supports: simulate mode (no on-chain tx) and live mode (web3 tx).
"""
import time
import random
import hashlib
from datetime import datetime
from typing import Optional, Dict

from .base_agent import BaseAgent
from backend.config import (
    SIMULATION_MODE, RPC_URL, CHAIN_ID,
    PRIVATE_KEY, VAULT_ADDRESS, TRADE_EXEC_ADDRESS
)
from backend.models import TradeRequest, TradeResponse, TradeStatus, StrategySignal, RiskAssessment


class ExecutionAgent(BaseAgent):
    name = "ExecutionAgent"

    async def execute_trade(
        self,
        signal:     StrategySignal,
        risk:       RiskAssessment,
        portfolio:  Dict,
        db=None,
    ) -> TradeResponse:
        """
        Execute a trade from signal + risk assessment.
        In SIMULATION_MODE: returns mock tx, no real on-chain state change.
        In live mode: sends tx via web3.
        """
        if not risk.approved:
            return TradeResponse(
                id=0, status=TradeStatus.failed,
                price=0, amount=0,
                message=f"Trade blocked by Risk Agent (score={risk.score})"
            )

        # Determine actual position size (risk-adjusted)
        cash       = portfolio.get("cash_balance", 10_000)
        total      = portfolio.get("total_value", 10_000)
        pct        = (risk.adjusted_size or signal.position_size) / 100
        trade_usd  = total * pct
        price      = self._get_execution_price(signal.symbol)
        units      = trade_usd / price if price > 0 else 0

        request = TradeRequest(
            wallet   = portfolio.get("wallet", "0x0000"),
            symbol   = signal.symbol,
            direction= signal.action,
            amount   = units,
            simulate = SIMULATION_MODE,
        )

        if SIMULATION_MODE or not PRIVATE_KEY:
            response = await self._simulate_trade(request, price)
        else:
            response = await self._execute_onchain(request, price)

        # Persist to DB
        if db and response.id == 0:
            response = await self._save_trade(db, request, response, signal, risk)

        self.log(
            "trade_executed",
            response.dict(),
            f"{signal.action.upper()} {signal.symbol}: {units:.4f} units @ ${price:,.2f} "
            f"[{response.status}] tx={response.tx_hash or 'simulated'}"
        )
        return response

    # ── Simulation mode ───────────────────────────────────────────────────────

    async def _simulate_trade(self, req: TradeRequest, price: float) -> TradeResponse:
        """Returns a realistic simulated trade response without touching the blockchain."""
        # Simulate slight slippage
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
            message = f"[SIMULATED] {req.direction.upper()} {req.amount:.4f} {req.symbol} @ ${exec_price:,.2f}"
        )

    # ── Live on-chain execution ───────────────────────────────────────────────

    async def _execute_onchain(self, req: TradeRequest, price: float) -> TradeResponse:
        """
        Real on-chain execution via web3.py + TradeExecutor contract.
        Requires PRIVATE_KEY, TRADE_EXEC_ADDRESS, RPC_URL in environment.
        """
        try:
            from web3 import Web3
            from web3.middleware import geth_poa_middleware

            w3 = Web3(Web3.HTTPProvider(RPC_URL))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            if not w3.is_connected():
                raise ConnectionError(f"Cannot connect to RPC: {RPC_URL}")

            account = w3.eth.account.from_key(PRIVATE_KEY)

            # Minimal ABI for TradeExecutor.executeTrade(symbol, direction, amount, price)
            abi = [
                {
                    "inputs": [
                        {"name": "symbol",    "type": "string"},
                        {"name": "direction", "type": "uint8"},   # 0=buy, 1=sell
                        {"name": "amount",    "type": "uint256"},
                        {"name": "minPrice",  "type": "uint256"},
                    ],
                    "name": "executeTrade",
                    "outputs": [{"name": "tradeId", "type": "uint256"}],
                    "type": "function",
                    "stateMutability": "nonpayable",
                }
            ]

            contract = w3.eth.contract(
                address=Web3.to_checksum_address(TRADE_EXEC_ADDRESS), abi=abi
            )

            direction_int = 0 if req.direction == "buy" else 1
            amount_wei    = w3.to_wei(req.amount, "ether")
            price_wei     = w3.to_wei(price * 0.99, "ether")  # 1% slippage tolerance

            tx = contract.functions.executeTrade(
                req.symbol, direction_int, amount_wei, price_wei
            ).build_transaction({
                "from":    account.address,
                "nonce":   w3.eth.get_transaction_count(account.address),
                "gas":     200_000,
                "chainId": CHAIN_ID,
            })

            signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

            status = TradeStatus.executed if receipt.status == 1 else TradeStatus.failed

            return TradeResponse(
                id      = receipt.blockNumber,
                status  = status,
                tx_hash = tx_hash.hex(),
                price   = price,
                amount  = req.amount,
                message = f"On-chain trade {'succeeded' if status == TradeStatus.executed else 'failed'}: {tx_hash.hex()}"
            )

        except ImportError:
            self.logger.error("web3 not installed — falling back to simulation")
            return await self._simulate_trade(req, price)

        except Exception as e:
            self.logger.error(f"On-chain execution failed: {e}")
            return TradeResponse(
                id=0, status=TradeStatus.failed,
                price=price, amount=req.amount,
                message=f"Execution error: {str(e)}"
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_execution_price(self, symbol: str) -> float:
        """Returns latest price from memory context (set by MarketAgent) or fallback."""
        for entry in reversed(self.memory):
            if entry.get("agent") == "MarketIntelligenceAgent":
                for item in entry.get("payload", []):
                    if item.get("symbol") == symbol:
                        return float(item.get("price", 1))
        # Fallback prices
        defaults = {"BTCUSDT": 68000, "ETHUSDT": 3500, "BNBUSDT": 580, "SOLUSDT": 175}
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

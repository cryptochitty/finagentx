"""
FinAgentX – PayFi Agent
Manages automated payments: scheduling, optimization, and execution triggers.
Off-chain DB tracking + optional on-chain PaymentScheduler calls.
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from .base_agent import BaseAgent
from backend.config import SIMULATION_MODE, PRIVATE_KEY, PAYFI_ADDRESS
from backend.models import PaymentCreate, PaymentResponse


# Frequency string → uint8 for PaymentScheduler contract
_FREQ_MAP = {"once": 0, "daily": 1, "weekly": 2, "monthly": 3}


class PayFiAgent(BaseAgent):
    name = "PayFiAgent"

    async def schedule_payment(self, payment: PaymentCreate, db=None) -> PaymentResponse:
        """
        Schedule a payment.
        - Always stores in DB for off-chain tracking.
        - If PAYFI_ADDRESS is set and SIMULATION_MODE is off, also registers
          the schedule on-chain via PaymentScheduler.schedulePayment().
        """
        next_exec   = self._calculate_next_execution(payment.schedule)
        gas_tip     = self._optimize_gas_timing()
        on_chain_id = None

        # ── DB record ────────────────────────────────────────────────────────
        pid = 1  # default mock ID
        if db:
            from backend.database import Payment
            db_payment = Payment(
                wallet         = payment.wallet,
                recipient      = payment.recipient,
                amount         = payment.amount,
                token          = payment.token,
                schedule       = payment.schedule,
                next_execution = next_exec,
                status         = "active",
            )
            db.add(db_payment)
            db.commit()
            db.refresh(db_payment)
            pid = db_payment.id

        # ── On-chain registration ─────────────────────────────────────────────
        if not SIMULATION_MODE and PAYFI_ADDRESS and PRIVATE_KEY:
            on_chain_id = await self._register_onchain(payment, next_exec)

        explanation = (
            f"Payment of {payment.amount} {payment.token} to {payment.recipient[:10]}… "
            f"scheduled as '{payment.schedule}'. Next: {next_exec.isoformat()}. "
            f"Gas: {gas_tip}"
            + (f" | on-chain ID: {on_chain_id}" if on_chain_id else "")
        )

        self.log("payment_scheduled", {
            "recipient":    payment.recipient,
            "amount":       payment.amount,
            "token":        payment.token,
            "schedule":     payment.schedule,
            "next":         next_exec.isoformat(),
            "on_chain_id":  on_chain_id,
        }, explanation)

        return PaymentResponse(
            id             = on_chain_id or pid,
            status         = "scheduled",
            next_execution = next_exec,
            message        = explanation,
        )

    async def _register_onchain(self, payment: PaymentCreate, next_exec: datetime) -> Optional[int]:
        """Call PaymentScheduler.schedulePayment() on HashKey Chain."""
        try:
            from web3 import Web3
            from backend.chain import get_web3, get_account, get_payment_scheduler, send_tx

            w3 = get_web3()
            if not w3 or not w3.is_connected():
                self.logger.warning("PayFi: RPC not connected – skipping on-chain registration")
                return None

            account   = get_account(w3)
            scheduler = get_payment_scheduler(w3)
            if not account or not scheduler:
                return None

            delay      = max(0, int((next_exec - datetime.utcnow()).total_seconds()))
            freq_uint8 = _FREQ_MAP.get(payment.schedule.lower(), 0)
            # token address: address(0) for native HSK, else checksum the token string
            token_addr = (
                "0x0000000000000000000000000000000000000000"
                if payment.token.upper() in ("HSK", "ETH", "NATIVE", "")
                else Web3.to_checksum_address(payment.token)
            )
            amount_wei = w3.to_wei(float(payment.amount), "ether")

            fn = scheduler.functions.schedulePayment(
                Web3.to_checksum_address(payment.recipient),
                token_addr,
                amount_wei,
                freq_uint8,
                delay,
                1 if freq_uint8 == 0 else 0,  # maxExecutions: 1 for ONCE, 0=unlimited for recurring
            )

            receipt, tx_hash = send_tx(w3, account, fn)
            if receipt.status == 1:
                # Decode payment ID from event
                try:
                    logs = scheduler.events.PaymentScheduled().process_receipt(receipt)
                    if logs:
                        return int(logs[0]["args"]["id"])
                except Exception:
                    pass
                return receipt.blockNumber
            return None

        except ImportError:
            self.logger.warning("web3 not installed – on-chain payment skipped")
            return None
        except Exception as e:
            self.logger.error("PayFi on-chain error: %s", e)
            return None

    async def execute_due_onchain(self, payment_ids: List[int]) -> Dict:
        """
        Trigger PaymentScheduler.executeBatch() for a list of due payment IDs.
        Returns tx result dict.
        """
        if not payment_ids or SIMULATION_MODE or not PAYFI_ADDRESS or not PRIVATE_KEY:
            return {"executed": False, "reason": "simulation mode or not configured"}
        try:
            from backend.chain import get_web3, get_account, get_payment_scheduler, send_tx

            w3 = get_web3()
            account   = get_account(w3)
            scheduler = get_payment_scheduler(w3)
            if not w3 or not account or not scheduler:
                return {"executed": False, "reason": "chain not available"}

            fn = scheduler.functions.executeBatch(payment_ids)
            receipt, tx_hash = send_tx(w3, account, fn)
            return {
                "executed":   receipt.status == 1,
                "tx_hash":    tx_hash,
                "count":      len(payment_ids),
                "payment_ids": payment_ids,
            }
        except Exception as e:
            self.logger.error("executeBatch error: %s", e)
            return {"executed": False, "reason": str(e)}

    async def check_due_payments(self, wallet: str, db=None) -> List[Dict]:
        """Find all due payments for a wallet and reschedule them."""
        due = []
        if db:
            from backend.database import Payment
            now      = datetime.utcnow()
            payments = (
                db.query(Payment)
                .filter(
                    Payment.wallet == wallet,
                    Payment.status == "active",
                    Payment.next_execution <= now,
                )
                .all()
            )
            for p in payments:
                due.append({
                    "id": p.id, "recipient": p.recipient,
                    "amount": p.amount, "token": p.token, "schedule": p.schedule,
                })
                p.next_execution = self._calculate_next_execution(p.schedule)
            if payments:
                db.commit()

        self.log(
            "payment_check",
            {"due_count": len(due), "wallet": wallet},
            f"Found {len(due)} due payments for {wallet[:10]}…",
        )
        return due

    async def optimize_payment_batch(self, payments: List[Dict]) -> Dict:
        """Batch multiple payments to reduce gas costs."""
        if len(payments) <= 1:
            return {"strategy": "single", "payments": payments, "estimated_savings_usd": 0}

        token_groups: Dict[str, List] = {}
        for p in payments:
            token_groups.setdefault(p.get("token", "HSK"), []).append(p)

        savings = len(payments) * 0.5
        plan = {
            "strategy":              "batch_by_token",
            "groups":                token_groups,
            "total_payments":        len(payments),
            "estimated_savings_usd": round(savings, 2),
            "recommended_time":      self._optimal_execution_window(),
        }
        self.log("payment_optimized", plan,
                 f"Batching {len(payments)} payments → ~${savings:.2f} gas savings")
        return plan

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _calculate_next_execution(self, schedule: str) -> datetime:
        delta_map = {
            "once":    timedelta(minutes=1),
            "daily":   timedelta(days=1),
            "weekly":  timedelta(weeks=1),
            "monthly": timedelta(days=30),
        }
        return datetime.utcnow() + delta_map.get(schedule.lower(), timedelta(minutes=1))

    def _optimize_gas_timing(self) -> str:
        hour = datetime.utcnow().hour
        if 2 <= hour <= 8:
            return "Optimal window (low network activity)"
        if 13 <= hour <= 18:
            return "High congestion – consider delaying 4 hours"
        return "Moderate congestion – acceptable to proceed"

    def _optimal_execution_window(self) -> str:
        return "02:00–08:00 UTC (historically lowest gas fees)"

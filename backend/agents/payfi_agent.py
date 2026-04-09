"""
FinAgentX – PayFi Agent
Manages automated payments: scheduling, optimization, and execution triggers.
Optimizes payment timing based on gas costs and market conditions.
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from .base_agent import BaseAgent
from backend.models import PaymentCreate, PaymentResponse


class PayFiAgent(BaseAgent):
    name = "PayFiAgent"

    async def schedule_payment(self, payment: PaymentCreate, db=None) -> PaymentResponse:
        """
        Schedule a payment. Calculates optimal next execution time.
        Stores in DB if db session is provided.
        """
        next_exec = self._calculate_next_execution(payment.schedule)
        gas_tip   = self._optimize_gas_timing()

        explanation = (
            f"Payment of {payment.amount} {payment.token} to {payment.recipient[:10]}... "
            f"scheduled as '{payment.schedule}'. Next execution: {next_exec.isoformat()}. "
            f"Gas optimization: {gas_tip}"
        )

        if db:
            from backend.database import Payment
            db_payment = Payment(
                wallet        = payment.wallet,
                recipient     = payment.recipient,
                amount        = payment.amount,
                token         = payment.token,
                schedule      = payment.schedule,
                next_execution= next_exec,
                status        = "active",
            )
            db.add(db_payment)
            db.commit()
            db.refresh(db_payment)
            pid = db_payment.id
        else:
            pid = 1   # mock ID for demo

        self.log("payment_scheduled", {
            "recipient": payment.recipient,
            "amount":    payment.amount,
            "token":     payment.token,
            "schedule":  payment.schedule,
            "next":      next_exec.isoformat(),
        }, explanation)

        return PaymentResponse(
            id             = pid,
            status         = "scheduled",
            next_execution = next_exec,
            message        = explanation,
        )

    async def check_due_payments(self, wallet: str, db=None) -> List[Dict]:
        """
        Find all due payments for a wallet and return them for execution.
        """
        due = []
        if db:
            from backend.database import Payment
            now = datetime.utcnow()
            payments = (
                db.query(Payment)
                .filter(Payment.wallet == wallet,
                        Payment.status == "active",
                        Payment.next_execution <= now)
                .all()
            )
            for p in payments:
                due.append({
                    "id":        p.id,
                    "recipient": p.recipient,
                    "amount":    p.amount,
                    "token":     p.token,
                    "schedule":  p.schedule,
                })
                # Reschedule
                p.next_execution = self._calculate_next_execution(p.schedule)

            if payments:
                db.commit()

        self.log("payment_check", {"due_count": len(due), "wallet": wallet},
                 f"Found {len(due)} due payments for {wallet[:10]}...")
        return due

    async def optimize_payment_batch(self, payments: List[Dict]) -> Dict:
        """
        Batches multiple payments to reduce gas costs.
        Returns optimized execution plan.
        """
        if len(payments) <= 1:
            return {"strategy": "single", "payments": payments, "estimated_savings_usd": 0}

        # Group by token to batch same-token payments
        token_groups: Dict[str, List] = {}
        for p in payments:
            token = p.get("token", "USDT")
            token_groups.setdefault(token, []).append(p)

        savings = len(payments) * 0.5   # ~$0.50 gas saved per batched tx
        plan = {
            "strategy":            "batch_by_token",
            "groups":              token_groups,
            "total_payments":      len(payments),
            "estimated_savings_usd": round(savings, 2),
            "recommended_time":    self._optimal_execution_window(),
        }

        self.log("payment_optimized", plan,
                 f"Batching {len(payments)} payments → estimated ${savings:.2f} gas savings")
        return plan

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _calculate_next_execution(self, schedule: str) -> datetime:
        now = datetime.utcnow()
        delta_map = {
            "once":    timedelta(minutes=1),
            "daily":   timedelta(days=1),
            "weekly":  timedelta(weeks=1),
            "monthly": timedelta(days=30),
        }
        return now + delta_map.get(schedule, timedelta(minutes=1))

    def _optimize_gas_timing(self) -> str:
        """
        In production: fetch gas oracle. Here: rule-based advice.
        Best gas windows on EVM chains are typically off-peak hours.
        """
        hour = datetime.utcnow().hour
        if 2 <= hour <= 8:
            return "Optimal window (low network activity)"
        elif 13 <= hour <= 18:
            return "High congestion – consider delaying 4 hours"
        return "Moderate congestion – acceptable to proceed"

    def _optimal_execution_window(self) -> str:
        return "02:00–08:00 UTC (historically lowest gas fees)"

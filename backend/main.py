"""
FinAgentX – FastAPI Application
All REST endpoints + SSE stream for live AI decision feed.
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.config import CORS_ORIGINS, LOG_LEVEL, SIMULATION_MODE
from backend.database import get_db, init_db, Portfolio, DecisionLog, Trade, Payment
from backend.models import (
    TradeRequest, TradeResponse, PaymentCreate, PaymentResponse,
    PortfolioResponse, SimulationRequest, SimulationResponse, CycleResult,
)
from backend.orchestrator import AgentOrchestrator
from backend.agents import (
    MarketIntelligenceAgent, SimulationAgent,
    ExplainerAgent, PayFiAgent,
)

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("finagentx.api")

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "FinAgentX API",
    description = "Autonomous On-Chain Financial Brain",
    version     = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

orchestrator = AgentOrchestrator()


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("FinAgentX started. Simulation mode: %s", SIMULATION_MODE)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":          "ok",
        "simulation_mode": SIMULATION_MODE,
        "timestamp":       datetime.utcnow().isoformat(),
    }


# ─── Portfolio ────────────────────────────────────────────────────────────────

@app.get("/portfolio/{wallet}", response_model=PortfolioResponse)
async def get_portfolio(wallet: str, db: Session = Depends(get_db)):
    p = db.query(Portfolio).filter(Portfolio.wallet == wallet).first()
    if not p:
        # Auto-create demo portfolio for new wallets
        p = Portfolio(
            wallet       = wallet,
            total_value  = 10_000.0,
            cash_balance = 10_000.0,
            holdings     = {},
        )
        db.add(p)
        db.commit()
        db.refresh(p)

    return PortfolioResponse(
        wallet       = p.wallet,
        total_value  = p.total_value,
        cash_balance = p.cash_balance,
        holdings     = p.holdings or {},
        risk_score   = 0,
        updated_at   = p.updated_at,
    )


@app.post("/portfolio/{wallet}/deposit")
async def deposit(wallet: str, amount: float, db: Session = Depends(get_db)):
    p = db.query(Portfolio).filter(Portfolio.wallet == wallet).first()
    if not p:
        p = Portfolio(wallet=wallet, total_value=amount, cash_balance=amount, holdings={})
        db.add(p)
    else:
        p.total_value  += amount
        p.cash_balance += amount
    db.commit()
    return {"wallet": wallet, "deposited": amount, "new_balance": p.total_value}


# ─── Market ───────────────────────────────────────────────────────────────────

@app.get("/market")
async def get_market(
    symbols: Optional[str] = Query(None, description="Comma-separated list, e.g. BTCUSDT,ETHUSDT")
):
    symbol_list = symbols.split(",") if symbols else None
    agent = MarketIntelligenceAgent()
    data  = await agent.run(symbol_list)
    return [d.dict() for d in data]


# ─── Autonomous Cycle ─────────────────────────────────────────────────────────

@app.post("/cycle/{wallet}", response_model=CycleResult)
async def run_cycle(
    wallet:     str,
    autonomous: bool         = Query(False),
    symbols:    Optional[str]= Query(None),
    db:         Session      = Depends(get_db),
):
    """
    Run a full AI decision cycle for a wallet.
    autonomous=true → executes approved trades on-chain (or simulated).
    """
    portfolio = await _get_portfolio_dict(wallet, db)
    symbol_list = symbols.split(",") if symbols else None

    result = await orchestrator.run_autonomous_cycle(
        wallet     = wallet,
        autonomous = autonomous,
        symbols    = symbol_list,
        portfolio  = portfolio,
        db         = db,
    )

    # Persist all decision logs
    for decision in result.decisions:
        log = DecisionLog(
            wallet        = wallet,
            agent         = decision.agent,
            decision_type = decision.decision_type,
            payload       = decision.payload,
            explanation   = decision.explanation,
        )
        db.add(log)
    db.commit()

    return result


# ─── SSE: Live AI Decision Feed ───────────────────────────────────────────────

@app.get("/feed/{wallet}")
async def decision_feed(wallet: str, db: Session = Depends(get_db)):
    """
    Server-Sent Events stream of AI decisions in real time.
    Frontend connects and receives live updates as agents work.
    """
    async def event_generator():
        # Yield a cycle result chunk by chunk (simulating streaming)
        portfolio = await _get_portfolio_dict(wallet, db)
        memory    = []

        yield f"data: {json.dumps({'event': 'cycle_start', 'wallet': wallet[:10]})}\n\n"
        await asyncio.sleep(0.5)

        # Market
        market_agent = MarketIntelligenceAgent(shared_memory=memory)
        market_data  = await market_agent.run()
        yield f"data: {json.dumps({'event': 'market_scan', 'data': [d.dict() for d in market_data[:3]]})}\n\n"
        await asyncio.sleep(0.5)

        # Emit each decision log entry as it happens
        for entry in memory:
            payload = {
                "event":       "agent_decision",
                "agent":       entry["agent"],
                "type":        entry["decision_type"],
                "explanation": entry.get("explanation", ""),
                "timestamp":   entry.get("timestamp", ""),
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.2)

        yield f"data: {json.dumps({'event': 'cycle_complete'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─── Trades ───────────────────────────────────────────────────────────────────

@app.get("/trades/{wallet}")
async def get_trades(wallet: str, limit: int = 20, db: Session = Depends(get_db)):
    trades = (
        db.query(Trade)
        .filter(Trade.wallet == wallet)
        .order_by(Trade.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id":         t.id,
            "symbol":     t.symbol,
            "direction":  t.direction,
            "amount":     t.amount,
            "price":      t.price,
            "status":     t.status,
            "risk_score": t.risk_score,
            "tx_hash":    t.tx_hash,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in trades
    ]


# ─── Payments ─────────────────────────────────────────────────────────────────

@app.post("/payments", response_model=PaymentResponse)
async def create_payment(payment: PaymentCreate, db: Session = Depends(get_db)):
    agent = PayFiAgent()
    return await agent.schedule_payment(payment, db)


@app.get("/payments/{wallet}")
async def get_payments(wallet: str, db: Session = Depends(get_db)):
    payments = db.query(Payment).filter(Payment.wallet == wallet).all()
    return [
        {
            "id":             p.id,
            "recipient":      p.recipient,
            "amount":         p.amount,
            "token":          p.token,
            "schedule":       p.schedule,
            "status":         p.status,
            "next_execution": p.next_execution.isoformat() if p.next_execution else None,
        }
        for p in payments
    ]


# ─── Simulation ───────────────────────────────────────────────────────────────

@app.post("/simulate", response_model=SimulationResponse)
async def simulate(request: SimulationRequest):
    agent  = SimulationAgent()
    return await agent.run(request)


# ─── Decision Logs ────────────────────────────────────────────────────────────

@app.get("/decisions/{wallet}")
async def get_decisions(wallet: str, limit: int = 50, db: Session = Depends(get_db)):
    logs = (
        db.query(DecisionLog)
        .filter(DecisionLog.wallet == wallet)
        .order_by(DecisionLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id":           l.id,
            "agent":        l.agent,
            "type":         l.decision_type,
            "explanation":  l.explanation,
            "executed":     l.executed,
            "created_at":   l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


# ─── ZK Identity ──────────────────────────────────────────────────────────────

@app.get("/zk/verify/{wallet}")
async def zk_verify(wallet: str):
    agent = ExplainerAgent()
    badge = agent.generate_zk_badge(wallet)
    return badge


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_portfolio_dict(wallet: str, db: Session) -> dict:
    p = db.query(Portfolio).filter(Portfolio.wallet == wallet).first()
    if not p:
        return {"wallet": wallet, "total_value": 10_000, "cash_balance": 10_000, "holdings": {}}
    return {
        "wallet":       p.wallet,
        "total_value":  p.total_value,
        "cash_balance": p.cash_balance,
        "holdings":     p.holdings or {},
    }

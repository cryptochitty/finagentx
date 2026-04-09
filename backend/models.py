"""
FinAgentX – Pydantic schemas for API request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    buy  = "buy"
    sell = "sell"


class TradeStatus(str, Enum):
    pending   = "pending"
    executed  = "executed"
    failed    = "failed"
    simulated = "simulated"


class Schedule(str, Enum):
    once    = "once"
    daily   = "daily"
    weekly  = "weekly"
    monthly = "monthly"


# ─── Market ───────────────────────────────────────────────────────────────────
class MarketData(BaseModel):
    symbol:        str
    price:         float
    change_24h:    float
    volume_24h:    float
    market_cap:    Optional[float] = None
    sentiment:     Optional[str]   = None    # bullish | neutral | bearish
    rsi:           Optional[float] = None
    trend:         Optional[str]   = None    # up | down | sideways


# ─── Strategy ─────────────────────────────────────────────────────────────────
class StrategySignal(BaseModel):
    symbol:        str
    action:        Direction
    confidence:    float = Field(..., ge=0, le=1)
    rationale:     str
    target_price:  Optional[float] = None
    stop_loss:     Optional[float] = None
    position_size: float = Field(..., ge=0, le=100)   # % of portfolio


# ─── Risk ─────────────────────────────────────────────────────────────────────
class RiskAssessment(BaseModel):
    score:         int   = Field(..., ge=0, le=100)   # 0=safe, 100=extreme
    level:         str                                 # low | medium | high | extreme
    approved:      bool
    flags:         List[str] = []
    adjusted_size: Optional[float] = None             # risk-adjusted position %


# ─── Execution ────────────────────────────────────────────────────────────────
class TradeRequest(BaseModel):
    wallet:    str
    symbol:    str
    direction: Direction
    amount:    float
    simulate:  bool = True


class TradeResponse(BaseModel):
    id:        int
    status:    TradeStatus
    tx_hash:   Optional[str] = None
    price:     float
    amount:    float
    message:   str


# ─── Payment ──────────────────────────────────────────────────────────────────
class PaymentCreate(BaseModel):
    wallet:    str
    recipient: str
    amount:    float
    token:     str      = "USDT"
    schedule:  Schedule = Schedule.once


class PaymentResponse(BaseModel):
    id:             int
    status:         str
    next_execution: Optional[datetime] = None
    message:        str


# ─── Portfolio ────────────────────────────────────────────────────────────────
class PortfolioResponse(BaseModel):
    wallet:       str
    total_value:  float
    cash_balance: float
    holdings:     Dict[str, float]
    risk_score:   int
    updated_at:   Optional[datetime] = None


# ─── Autonomous cycle ─────────────────────────────────────────────────────────
class AgentDecision(BaseModel):
    agent:        str
    decision_type:str
    payload:      Dict[str, Any]
    explanation:  str
    timestamp:    datetime = Field(default_factory=datetime.utcnow)


class CycleResult(BaseModel):
    wallet:        str
    market_data:   List[MarketData]
    signals:       List[StrategySignal]
    risk:          RiskAssessment
    simulation:    Optional[Dict[str, Any]] = None
    executed:      List[TradeResponse]      = []
    decisions:     List[AgentDecision]      = []
    autonomous:    bool                     = False


# ─── Simulation ───────────────────────────────────────────────────────────────
class SimulationRequest(BaseModel):
    strategy:    str = "momentum"
    symbol:      str = "BTCUSDT"
    period_days: int = Field(30, ge=7, le=365)
    initial_capital: float = 10_000.0


class SimulationResponse(BaseModel):
    strategy:      str
    roi_pct:       float
    max_drawdown:  float
    win_rate:      float
    sharpe_ratio:  float
    total_trades:  int
    equity_curve:  List[Dict[str, Any]]
    explanation:   str

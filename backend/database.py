"""
FinAgentX – Database setup (SQLAlchemy + SQLite for MVP, swap URL for Postgres)
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from backend.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── ORM Models ───────────────────────────────────────────────────────────────

class Portfolio(Base):
    __tablename__ = "portfolios"
    id            = Column(Integer, primary_key=True, index=True)
    wallet        = Column(String, unique=True, index=True)
    total_value   = Column(Float, default=0.0)
    cash_balance  = Column(Float, default=0.0)
    holdings      = Column(JSON, default={})           # {"BTC": 0.5, "ETH": 2.0}
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DecisionLog(Base):
    __tablename__ = "decision_logs"
    id            = Column(Integer, primary_key=True, index=True)
    wallet        = Column(String, index=True)
    agent         = Column(String)                     # which agent produced this
    decision_type = Column(String)                     # trade | payment | risk | info
    payload       = Column(JSON)                       # full decision data
    explanation   = Column(Text)                       # human-readable reason
    executed      = Column(Boolean, default=False)
    tx_hash       = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


class Trade(Base):
    __tablename__ = "trades"
    id            = Column(Integer, primary_key=True, index=True)
    wallet        = Column(String, index=True)
    symbol        = Column(String)                     # BTC/USDT
    direction     = Column(String)                     # buy | sell
    amount        = Column(Float)
    price         = Column(Float)
    status        = Column(String, default="pending")  # pending | executed | failed | simulated
    tx_hash       = Column(String, nullable=True)
    risk_score    = Column(Integer, default=0)
    created_at    = Column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"
    id            = Column(Integer, primary_key=True, index=True)
    wallet        = Column(String, index=True)
    recipient     = Column(String)
    amount        = Column(Float)
    token         = Column(String, default="USDT")
    schedule      = Column(String)                     # once | daily | weekly | monthly
    next_execution= Column(DateTime, nullable=True)
    status        = Column(String, default="active")
    tx_hash       = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


class SimulationResult(Base):
    __tablename__ = "simulation_results"
    id            = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String)
    roi_pct       = Column(Float)
    max_drawdown  = Column(Float)
    win_rate      = Column(Float)
    sharpe_ratio  = Column(Float)
    total_trades  = Column(Integer)
    period_days   = Column(Integer)
    details       = Column(JSON)
    created_at    = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""
FinAgentX – Central configuration
All secrets come from environment variables; sensible defaults enable local dev.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── LLM ──────────────────────────────────────────────────────────────────────
LLM_PROVIDER   = os.getenv("LLM_PROVIDER", "mock")   # mock | gemini | openai | ollama
LLM_API_KEY    = os.getenv("LLM_API_KEY", "")
LLM_MODEL      = os.getenv("LLM_MODEL", "gemini-1.5-flash")
LLM_BASE_URL   = os.getenv("LLM_BASE_URL", "")       # for Ollama / local models

# ─── Market data ──────────────────────────────────────────────────────────────
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
COINGECKO_API_KEY  = os.getenv("COINGECKO_API_KEY", "")
USE_MOCK_DATA      = os.getenv("USE_MOCK_DATA", "true").lower() == "true"

# ─── Blockchain ───────────────────────────────────────────────────────────────
RPC_URL            = os.getenv("RPC_URL", "https://mainnet.hsk.xyz")  # HashKey Chain
CHAIN_ID           = int(os.getenv("CHAIN_ID", "177"))
PRIVATE_KEY        = os.getenv("PRIVATE_KEY", "")                    # agent wallet
VAULT_ADDRESS      = os.getenv("VAULT_ADDRESS", "")
TRADE_EXEC_ADDRESS = os.getenv("TRADE_EXEC_ADDRESS", "")
PAYFI_ADDRESS      = os.getenv("PAYFI_ADDRESS", "")
SIMULATION_MODE    = os.getenv("SIMULATION_MODE", "true").lower() == "true"

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finagentx.db")

# ─── App ──────────────────────────────────────────────────────────────────────
SECRET_KEY    = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
CORS_ORIGINS  = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
LOG_LEVEL     = os.getenv("LOG_LEVEL", "INFO")

# ─── Risk limits ──────────────────────────────────────────────────────────────
MAX_TRADE_SIZE_PCT  = float(os.getenv("MAX_TRADE_SIZE_PCT", "10"))   # % of portfolio
MAX_DRAWDOWN_PCT    = float(os.getenv("MAX_DRAWDOWN_PCT", "15"))
STOP_LOSS_PCT       = float(os.getenv("STOP_LOSS_PCT", "5"))
MAX_RISK_SCORE      = int(os.getenv("MAX_RISK_SCORE", "70"))         # 0-100

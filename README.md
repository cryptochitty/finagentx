# FinAgentX – Autonomous On-Chain Financial Brain

> Multi-agent AI system that autonomously manages crypto trading, payments, and portfolio optimization on HashKey Chain.

[![Demo Ready](https://img.shields.io/badge/demo-ready-brightgreen)]()
[![Simulation Mode](https://img.shields.io/badge/simulation-enabled-blue)]()
[![HashKey Chain](https://img.shields.io/badge/chain-HashKey%20Chain-purple)]()
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/cryptochitty/finagentx)

---

## 🚀 Live Deployment

| Service | URL | Purpose |
|---------|-----|---------|
| **Vercel** (Frontend) | https://finagentx.vercel.app | HTML dashboard UI |
| **Render** (Backend)  | https://finagentx-api.onrender.com | FastAPI + AI agents |

### Deploy in 5 minutes

**Backend → Render**
1. Go to [render.com](https://render.com) → New → Blueprint
2. Connect `cryptochitty/finagentx` → Render auto-reads `render.yaml`
3. Click **Apply** — deploys API + free PostgreSQL automatically

**Frontend → Vercel**
1. Go to [vercel.com](https://vercel.com) → New Project
2. Import `cryptochitty/finagentx`
3. Framework: **Other** · Root: `/` · Output: leave blank
4. Add env var: `FINAGENTX_API_URL` = your Render API URL
5. Deploy → open `https://your-app.vercel.app`

> **Offline demo:** just open `index.html` in any browser — no server needed.

---

## What It Does

FinAgentX is a **collaborative multi-agent AI system** where 7 specialized agents work together to make and execute financial decisions autonomously:

```
Market Intelligence → Strategy → Simulation → Risk → Execution → Explain
```

Each agent passes its output to the next through **shared memory**, giving downstream agents full context of what prior agents decided.

---

## Architecture

### Agents

| Agent | Role |
|-------|------|
| **MarketIntelligenceAgent** | Fetches prices, calculates RSI, sentiment from Binance/CoinGecko |
| **StrategyAgent** | Generates BUY/SELL signals using LLM + momentum rules |
| **SimulationAgent** | Backtests strategies with GBM price simulation |
| **RiskAgent** | Scores risk 0-100 and approves/blocks trades |
| **PayFiAgent** | Schedules and optimizes recurring on-chain payments |
| **ExecutionAgent** | Executes trades via smart contracts (or simulation) |
| **ExplainerAgent** | Converts decisions to plain English + ZK identity |

### Smart Contracts (Solidity, EVM / HashKey Chain)

| Contract | Purpose |
|----------|---------|
| `FundVault.sol` | Secure deposit/withdraw vault per user |
| `TradeExecutor.sol` | Agent-authorized trade execution |
| `PaymentScheduler.sol` | Recurring on-chain payment automation |

### Tech Stack

- **Backend**: Python 3.11 + FastAPI + SQLAlchemy (SQLite/Postgres)
- **AI**: LangGraph-style orchestration, LLM abstraction (Gemini / OpenAI / Ollama / Mock)
- **Frontend**: Next.js 14 + Tailwind CSS + Recharts
- **Blockchain**: Solidity 0.8.20 + Hardhat + web3.py
- **Data**: Binance API, CoinGecko (mock mode built-in)

---

## Quick Start (5 minutes)

### Option A: Local (recommended for demo)

```bash
# 1. Clone and setup
git clone https://github.com/your-org/finagentx
cd finagentx

# 2. Backend
cp .env.example .env
cd backend
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev

# 4. Open http://localhost:3000
```

> No API keys needed! Mock mode is enabled by default.

### Option B: Docker

```bash
cp .env.example .env
docker-compose up --build
# Open http://localhost:3000
```

### Demo script (CLI only)

```bash
python scripts/demo_cycle.py
```

---

## Configuration

Edit `.env`:

```env
# Use real LLM (optional)
LLM_PROVIDER=gemini        # or openai, ollama, mock
LLM_API_KEY=your-key-here

# Use real market data (optional)
USE_MOCK_DATA=false
BINANCE_API_KEY=...

# Keep these true for demo
SIMULATION_MODE=true       # No real blockchain txs
USE_MOCK_DATA=true         # No API keys needed
```

---

## Smart Contract Deployment

```bash
cd contracts
npm install
npx hardhat compile

# Deploy to HashKey Chain testnet
npx hardhat run deploy.js --network hashkey_testnet

# Add the printed addresses to .env
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System status |
| GET | `/market` | Live market data |
| GET | `/portfolio/{wallet}` | Portfolio state |
| POST | `/portfolio/{wallet}/deposit` | Deposit funds |
| POST | `/cycle/{wallet}?autonomous=true` | Run AI cycle |
| GET | `/feed/{wallet}` | SSE live decision stream |
| POST | `/simulate` | Backtest a strategy |
| POST | `/payments` | Schedule payment |
| GET | `/decisions/{wallet}` | Decision history |
| GET | `/zk/verify/{wallet}` | ZK identity badge |

---

## Features

### Autonomous Mode
Toggle "Autonomous ON" in the UI → AI executes approved trades automatically (simulated by default).

### Simulation Mode
Every strategy is backtested before execution. View ROI, drawdown, Sharpe ratio, and equity curve.

### Risk Management
Every trade is scored 0-100 before execution:
- **0-20**: Low risk → approved
- **21-44**: Medium → approved with reduced size
- **45-69**: High → approved with minimal size
- **70+**: Extreme → blocked

### PayFi Automation
Schedule recurring payments (daily/weekly/monthly) with gas optimization.

### ZK Identity (Mock)
Click "ZK Verify" on the portfolio panel to get a mock ZK proof badge showing wallet ownership and KYC claims.

---

## Project Structure

```
finagentx/
├── backend/
│   ├── agents/
│   │   ├── base_agent.py          # LLM abstraction + shared memory
│   │   ├── market_agent.py        # Binance/CoinGecko data fetcher
│   │   ├── strategy_agent.py      # Signal generation (LLM + rules)
│   │   ├── simulation_agent.py    # GBM backtester
│   │   ├── risk_agent.py          # Risk scoring engine
│   │   ├── payfi_agent.py         # Payment scheduler
│   │   ├── execution_agent.py     # Trade executor (sim + live)
│   │   └── explainer_agent.py     # Plain-English explainer + ZK
│   ├── orchestrator.py            # Multi-agent pipeline coordinator
│   ├── main.py                    # FastAPI app + all endpoints
│   ├── models.py                  # Pydantic schemas
│   ├── database.py                # SQLAlchemy ORM
│   └── config.py                  # Environment config
├── contracts/
│   ├── FundVault.sol              # User fund management
│   ├── TradeExecutor.sol          # Agent-authorized trades
│   ├── PaymentScheduler.sol       # Recurring payments
│   ├── deploy.js                  # Deployment script
│   └── hardhat.config.js          # Hardhat + HashKey Chain config
├── frontend/
│   ├── app/page.tsx               # Main dashboard
│   ├── components/
│   │   ├── PortfolioPanel.tsx     # Portfolio + ZK badge
│   │   ├── AIDecisionFeed.tsx     # Live agent decision log
│   │   ├── MarketTicker.tsx       # Real-time price ticker
│   │   ├── TradeSimulation.tsx    # Backtest UI + equity chart
│   │   ├── PaymentPanel.tsx       # PayFi automation UI
│   │   └── AutonomousToggle.tsx   # Mode switcher
│   └── lib/api.ts                 # Typed API client
├── scripts/demo_cycle.py          # CLI demo runner
├── docker-compose.yml
└── .env.example
```

---

## Hackathon Highlights

- **Real autonomous decisions**: agents collaborate through shared memory, not isolated scripts
- **Full pipeline**: Market → Strategy → Backtest → Risk → Execute in one cycle
- **Works offline**: mock mode requires zero API keys
- **Production-ready**: security best practices in smart contracts, typed APIs, error handling
- **ZK integration**: mock ZK proof system ready to wire to real ZK stack
- **HashKey Chain ready**: contracts configured for mainnet and testnet deployment

---

## License

MIT – Built for the FinAgentX Hackathon 2025

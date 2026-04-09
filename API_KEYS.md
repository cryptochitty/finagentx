# FinAgentX – API Keys & External Services

Everything the system can connect to, what's optional, and where to get each key.

---

## TL;DR – Minimum to run (zero keys needed)

| Env var | Default | Notes |
|---------|---------|-------|
| `USE_MOCK_DATA` | `true` | Uses built-in price data |
| `LLM_PROVIDER` | `mock` | Rule-based agent logic |
| `SIMULATION_MODE` | `true` | No on-chain transactions |

> Run `python scripts/demo_cycle.py` or open `index.html` – **no keys required**.

---

## LLM (AI agent brain)

### Option A: Google Gemini ✅ Recommended (free tier available)

| | |
|-|-|
| **Get key** | https://aistudio.google.com/app/apikey (Google account, no billing) |
| **Free tier** | 15 req/min · 1 million tokens/day · gemini-1.5-flash |
| **Env vars** | `LLM_PROVIDER=gemini` `LLM_API_KEY=AIza...` `LLM_MODEL=gemini-1.5-flash` |

### Option B: OpenAI / Together / Groq (OpenAI-compatible)

| Provider | URL | Free tier |
|----------|-----|-----------|
| OpenAI | https://platform.openai.com/api-keys | $5 credit on signup |
| Together AI | https://api.together.xyz | $1 free · Qwen/Mixtral/Llama |
| Groq | https://console.groq.com/keys | Free · Llama 3.1/Mixtral |

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini          # or mixtral-8x7b-32768 on Together/Groq
LLM_BASE_URL=https://api.groq.com/openai/v1    # for Groq
```

### Option C: Ollama (fully local, no key)

```bash
ollama pull qwen2.5
```
```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5
LLM_BASE_URL=http://localhost:11434
```

---

## Market Data

### Binance Public API (no key required)

The 24-hr ticker endpoint is unauthenticated.
`BINANCE_API_KEY` / `BINANCE_API_SECRET` are **not needed** for price data.
They would only be needed for placing real orders (not used in simulation mode).

### CoinGecko

| Tier | Key needed | Rate limit | Get key |
|------|-----------|------------|---------|
| **Demo (free)** | No | 30 req/min | n/a – just works |
| **Pro** | Yes | 500 req/min | https://www.coingecko.com/en/api/pricing |

```env
# leave blank for free demo tier
COINGECKO_API_KEY=
```

---

## Blockchain / Smart Contracts

### For simulation mode (default)

No keys, no wallet, no contracts needed. Set:
```env
SIMULATION_MODE=true
```

### For real on-chain execution

| Var | What it is | Where to get |
|-----|-----------|--------------|
| `PRIVATE_KEY` | Agent wallet private key | MetaMask → Account Details → Export |
| `RPC_URL` | HashKey Chain RPC | `https://mainnet.hsk.xyz` (free public) |
| `CHAIN_ID` | 177 (mainnet) or 133 (testnet) | Fixed |
| `VAULT_ADDRESS` | Deployed FundVault address | After `npx hardhat run deploy.js` |
| `TRADE_EXEC_ADDRESS` | Deployed TradeExecutor | Same |
| `PAYFI_ADDRESS` | Deployed PaymentScheduler | Same |

#### HashKey Chain testnet faucet (free test HSK)
https://faucet.hsk.xyz

#### Deploy contracts
```bash
cd contracts && npm install && npx hardhat run deploy.js --network hashkey_testnet
```

> ⚠️ Never commit `PRIVATE_KEY` to git. Use Render's secret env vars.

---

## Database

### SQLite (default, zero config)

```env
DATABASE_URL=sqlite:///./finagentx.db
```

### PostgreSQL on Render (auto-configured)

Render's Blueprint (`render.yaml`) provisions a free Postgres instance and sets
`DATABASE_URL` automatically. No action needed.

### External Postgres

```env
DATABASE_URL=postgresql://user:password@host:5432/finagentx
```

---

## Summary: what to set on Render

Minimum working deployment (all AI is rule-based mock):

```
USE_MOCK_DATA    = true
SIMULATION_MODE  = true
LLM_PROVIDER     = mock
CORS_ORIGINS     = *
```

Full AI-powered deployment:

```
LLM_PROVIDER     = gemini
LLM_API_KEY      = AIza...          ← from aistudio.google.com
LLM_MODEL        = gemini-1.5-flash
USE_MOCK_DATA    = false
SIMULATION_MODE  = false
PRIVATE_KEY      = 0x...            ← agent wallet (keep secret)
VAULT_ADDRESS    = 0x...
TRADE_EXEC_ADDRESS = 0x...
PAYFI_ADDRESS    = 0x...
CORS_ORIGINS     = https://finagentx.vercel.app
```

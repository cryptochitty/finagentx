# FinAgentX Smart Contracts

Three EVM-compatible contracts deployable on HashKey Chain (mainnet/testnet) or any EVM chain.

---

## Contracts

| Contract | Purpose | Constructor args |
|----------|---------|-----------------|
| `FundVault.sol` | User deposit/withdraw vault | `agentAddress` |
| `TradeExecutor.sol` | Agent-authorized trade execution | `vaultAddress`, `agentWallet` |
| `PaymentScheduler.sol` | Recurring on-chain payments | `agentAddress` |

All three use OpenZeppelin 5.x (`ReentrancyGuard`, `Ownable`, `SafeERC20`).

---

## Prerequisites

```bash
cd contracts
npm install
```

---

## Deploy – HashKey Chain Testnet (free, no real funds)

### 1. Get testnet HSK

- Faucet: https://faucet.hsk.xyz
- Network: HashKey Chain Testnet · Chain ID: 133
- RPC: `https://hashkeychain-testnet.alt.technology`

### 2. Set env vars

```bash
# in root .env
PRIVATE_KEY=0xYOUR_WALLET_PRIVATE_KEY   # never commit this
RPC_URL=https://hashkeychain-testnet.alt.technology
CHAIN_ID=133
```

### 3. Compile + deploy

```bash
cd contracts
npx hardhat compile
npx hardhat run deploy.js --network hashkey_testnet
```

Output:
```
✅ FundVault deployed to:        0xABC...
✅ TradeExecutor deployed to:    0xDEF...
✅ PaymentScheduler deployed to: 0xGHI...
```

### 4. Add addresses to .env

```env
VAULT_ADDRESS=0xABC...
TRADE_EXEC_ADDRESS=0xDEF...
PAYFI_ADDRESS=0xGHI...
SIMULATION_MODE=false          # now uses real contracts
```

---

## Deploy – HashKey Chain Mainnet

```bash
# Change .env
RPC_URL=https://mainnet.hsk.xyz
CHAIN_ID=177

cd contracts
npx hardhat run deploy.js --network hashkey
```

Fund your deployer wallet with HSK for gas first.

---

## Deploy – Local (Hardhat node, zero cost)

```bash
# Terminal 1
cd contracts && npx hardhat node

# Terminal 2
cd contracts && npx hardhat run deploy.js --network localhost
```

---

## Contract addresses (after deployment)

Update `render.yaml` env vars or your Render dashboard:

```
VAULT_ADDRESS      = <FundVault address>
TRADE_EXEC_ADDRESS = <TradeExecutor address>
PAYFI_ADDRESS      = <PaymentScheduler address>
SIMULATION_MODE    = false
```

---

## Security notes

- `FundVault`: users can always withdraw regardless of agent state
- `TradeExecutor`: requires user to call `setAutonomousMode(true)` first
- `PaymentScheduler`: only the registered agent wallet can execute payments
- All contracts use `ReentrancyGuard` + `SafeERC20`
- Never store `PRIVATE_KEY` in the repo – use env vars or Render secrets

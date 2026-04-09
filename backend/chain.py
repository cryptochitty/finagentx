"""
FinAgentX – On-Chain Integration Layer
Web3 provider, contract loaders, and tx helpers for HashKey Chain.

Usage (simulation mode safe — all functions return None gracefully when
web3 is not installed or contract addresses are not configured):

    from backend.chain import get_web3, get_trade_executor, send_tx, get_account
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("finagentx.chain")

# ─── Minimal ABIs ─────────────────────────────────────────────────────────────
# Hand-derived from Solidity source so we don't need compiled artifacts.

FUND_VAULT_ABI = [
    {
        "inputs": [{"name": "_agentAddress", "type": "address"}],
        "stateMutability": "nonpayable", "type": "constructor",
    },
    {
        "inputs": [], "name": "depositETH",
        "outputs": [], "stateMutability": "payable", "type": "function",
    },
    {
        "inputs": [{"name": "token", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "depositToken", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "withdrawETH", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "token", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "withdrawToken", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "enabled", "type": "bool"}],
        "name": "setAutonomousMode", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [
            {"name": "user", "type": "address"}, {"name": "token", "type": "address"},
            {"name": "amount", "type": "uint256"}, {"name": "symbol", "type": "string"},
        ],
        "name": "authorizeTradeExecution", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [
            {"name": "user", "type": "address"}, {"name": "token", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "creditTradeProceeds", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "newAgent", "type": "address"}],
        "name": "setAgent", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [], "name": "collectFees",
        "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "user", "type": "address"}, {"name": "token", "type": "address"}],
        "name": "getBalances",
        "outputs": [{"name": "eth", "type": "uint256"}, {"name": "tok", "type": "uint256"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [{"name": "", "type": "address"}],
        "name": "ethBalances", "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [{"name": "", "type": "address"}],
        "name": "autonomousMode", "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [], "name": "agentAddress", "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [], "name": "totalFeesCollected", "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "user", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": True, "name": "token", "type": "address"},
        ],
        "name": "Deposited", "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "user", "type": "address"},
            {"indexed": True, "name": "token", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "symbol", "type": "string"},
        ],
        "name": "TradeAuthorized", "type": "event",
    },
]

TRADE_EXECUTOR_ABI = [
    {
        "inputs": [{"name": "_vault", "type": "address"}, {"name": "_agentWallet", "type": "address"}],
        "stateMutability": "nonpayable", "type": "constructor",
    },
    {
        "inputs": [
            {"name": "user", "type": "address"},
            {"name": "symbol", "type": "string"},
            {"name": "direction", "type": "uint8"},   # 0=BUY, 1=SELL
            {"name": "amount", "type": "uint256"},
            {"name": "minPrice", "type": "uint256"},  # price * 1e8, 0 = no slippage limit
        ],
        "name": "executeTrade",
        "outputs": [{"name": "tradeId", "type": "uint256"}],
        "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "tradeId", "type": "uint256"}],
        "name": "cancelTrade", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getUserTrades", "outputs": [{"name": "", "type": "uint256[]"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [{"name": "tradeId", "type": "uint256"}],
        "name": "getTrade",
        "outputs": [{
            "components": [
                {"name": "id", "type": "uint256"}, {"name": "user", "type": "address"},
                {"name": "symbol", "type": "string"}, {"name": "direction", "type": "uint8"},
                {"name": "amount", "type": "uint256"}, {"name": "executedPrice", "type": "uint256"},
                {"name": "timestamp", "type": "uint256"}, {"name": "status", "type": "uint8"},
            ],
            "name": "", "type": "tuple",
        }],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [{"name": "_vault", "type": "address"}],
        "name": "setVault", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "_agent", "type": "address"}],
        "name": "setAgentWallet", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [], "name": "tradeCounter", "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [], "name": "agentWallet", "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "tradeId", "type": "uint256"},
            {"indexed": True, "name": "user", "type": "address"},
            {"indexed": False, "name": "symbol", "type": "string"},
            {"indexed": False, "name": "direction", "type": "uint8"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "TradeRequested", "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "tradeId", "type": "uint256"},
            {"indexed": False, "name": "executedPrice", "type": "uint256"},
            {"indexed": False, "name": "timestamp", "type": "uint256"},
        ],
        "name": "TradeExecuted", "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "tradeId", "type": "uint256"},
            {"indexed": False, "name": "reason", "type": "string"},
        ],
        "name": "TradeFailed", "type": "event",
    },
]

PAYMENT_SCHEDULER_ABI = [
    {
        "inputs": [{"name": "_agentAddress", "type": "address"}],
        "stateMutability": "nonpayable", "type": "constructor",
    },
    {
        "inputs": [
            {"name": "recipient", "type": "address"},
            {"name": "token", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "frequency", "type": "uint8"},      # 0=ONCE,1=DAILY,2=WEEKLY,3=MONTHLY
            {"name": "startDelay", "type": "uint256"},   # seconds from now
            {"name": "maxExecutions", "type": "uint256"},# 0 = unlimited
        ],
        "name": "schedulePayment",
        "outputs": [{"name": "paymentId", "type": "uint256"}],
        "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "paymentId", "type": "uint256"}],
        "name": "executePayment", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "paymentIds", "type": "uint256[]"}],
        "name": "executeBatch", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "paymentId", "type": "uint256"}],
        "name": "cancelPayment", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "paymentId", "type": "uint256"}],
        "name": "pausePayment", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "paymentId", "type": "uint256"}],
        "name": "resumePayment", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getUserPayments", "outputs": [{"name": "", "type": "uint256[]"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getDuePayments", "outputs": [{"name": "", "type": "uint256[]"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [], "name": "paymentCounter", "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [{"name": "_agent", "type": "address"}],
        "name": "setAgent", "outputs": [], "stateMutability": "nonpayable", "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "id", "type": "uint256"},
            {"indexed": True, "name": "payer", "type": "address"},
            {"indexed": False, "name": "recipient", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "frequency", "type": "uint8"},
        ],
        "name": "PaymentScheduled", "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "id", "type": "uint256"},
            {"indexed": True, "name": "payer", "type": "address"},
            {"indexed": False, "name": "recipient", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "timestamp", "type": "uint256"},
        ],
        "name": "PaymentExecuted", "type": "event",
    },
]


# ─── Provider helpers ──────────────────────────────────────────────────────────

def get_web3():
    """Return a connected Web3 instance or None if web3 isn't installed / unavailable."""
    from backend.config import RPC_URL
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
        # HashKey Chain (and most EVM L2s) uses POA – inject the middleware
        try:
            from web3.middleware import ExtraDataToPOAMiddleware   # web3 >= 6.0
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        except ImportError:
            from web3.middleware import geth_poa_middleware         # web3 5.x
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        if w3.is_connected():
            return w3
        logger.warning("Web3 connected to RPC but chain not responding: %s", RPC_URL)
        return None
    except ImportError:
        logger.warning("web3 package not installed – on-chain features disabled")
        return None
    except Exception as e:
        logger.warning("Web3 init error: %s", e)
        return None


def get_account(w3):
    """Return the agent's signing account from PRIVATE_KEY env var."""
    from backend.config import PRIVATE_KEY
    if not PRIVATE_KEY or not w3:
        return None
    try:
        return w3.eth.account.from_key(PRIVATE_KEY)
    except Exception as e:
        logger.error("Bad PRIVATE_KEY: %s", e)
        return None


def get_vault(w3):
    """Return a FundVault contract instance or None."""
    from backend.config import VAULT_ADDRESS
    if not VAULT_ADDRESS or not w3:
        return None
    from web3 import Web3
    return w3.eth.contract(
        address=Web3.to_checksum_address(VAULT_ADDRESS),
        abi=FUND_VAULT_ABI,
    )


def get_trade_executor(w3):
    """Return a TradeExecutor contract instance or None."""
    from backend.config import TRADE_EXEC_ADDRESS
    if not TRADE_EXEC_ADDRESS or not w3:
        return None
    from web3 import Web3
    return w3.eth.contract(
        address=Web3.to_checksum_address(TRADE_EXEC_ADDRESS),
        abi=TRADE_EXECUTOR_ABI,
    )


def get_payment_scheduler(w3):
    """Return a PaymentScheduler contract instance or None."""
    from backend.config import PAYFI_ADDRESS
    if not PAYFI_ADDRESS or not w3:
        return None
    from web3 import Web3
    return w3.eth.contract(
        address=Web3.to_checksum_address(PAYFI_ADDRESS),
        abi=PAYMENT_SCHEDULER_ABI,
    )


def send_tx(w3, account, contract_fn, value_wei: int = 0) -> tuple:
    """
    Build, sign, and send a transaction.
    Returns (receipt, tx_hash_hex).
    Raises on failure.
    """
    from backend.config import CHAIN_ID
    tx = contract_fn.build_transaction({
        "from":    account.address,
        "nonce":   w3.eth.get_transaction_count(account.address),
        "gas":     300_000,
        "chainId": CHAIN_ID,
        "value":   value_wei,
    })
    signed  = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    return receipt, "0x" + tx_hash.hex()


# ─── Contract address loader ───────────────────────────────────────────────────

def get_contract_addresses() -> dict:
    """
    Return deployed contract addresses.
    Priority: env vars → contracts/deployments/<network>.json → empty.
    """
    from backend.config import VAULT_ADDRESS, TRADE_EXEC_ADDRESS, PAYFI_ADDRESS, CHAIN_ID

    if VAULT_ADDRESS and TRADE_EXEC_ADDRESS:
        return {
            "FundVault":        VAULT_ADDRESS,
            "TradeExecutor":    TRADE_EXEC_ADDRESS,
            "PaymentScheduler": PAYFI_ADDRESS or "",
            "chain_id":         CHAIN_ID,
            "network":          "hashkey" if CHAIN_ID == 177 else "hashkey_testnet",
            "source":           "env",
        }

    network_map = {133: "hashkey_testnet", 177: "hashkey", 31337: "hardhat"}
    network = network_map.get(CHAIN_ID, "localhost")
    deploy_file = (
        Path(__file__).resolve().parent.parent
        / "contracts" / "deployments" / f"{network}.json"
    )

    if deploy_file.exists():
        with open(deploy_file) as f:
            data = json.load(f)
        return {
            "FundVault":        data.get("FundVault", ""),
            "TradeExecutor":    data.get("TradeExecutor", ""),
            "PaymentScheduler": data.get("PaymentScheduler", ""),
            "chain_id":         data.get("chainId", CHAIN_ID),
            "network":          data.get("network", network),
            "source":           f"deployments/{network}.json",
        }

    return {
        "FundVault": "", "TradeExecutor": "", "PaymentScheduler": "",
        "chain_id": CHAIN_ID, "network": network,
        "source": "not_deployed – run: cd contracts && npx hardhat run deploy.js --network hashkey_testnet",
    }


# ─── Chain status ──────────────────────────────────────────────────────────────

def chain_status() -> dict:
    """Returns a status dict suitable for the /health or /contracts endpoint."""
    from backend.config import SIMULATION_MODE, CHAIN_ID, RPC_URL
    addrs = get_contract_addresses()

    deployed = bool(addrs.get("FundVault") and addrs.get("TradeExecutor"))
    connected = False

    if not SIMULATION_MODE and deployed:
        w3 = get_web3()
        connected = w3 is not None and w3.is_connected()

    return {
        "simulation_mode": SIMULATION_MODE,
        "chain_id":        CHAIN_ID,
        "rpc_url":         RPC_URL,
        "contracts":       addrs,
        "rpc_connected":   connected,
        "explorer": (
            "https://explorer.hsk.xyz"       if CHAIN_ID == 177  else
            "https://testnet-explorer.hsk.xyz" if CHAIN_ID == 133 else
            "http://localhost:8545"
        ),
    }

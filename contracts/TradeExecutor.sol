// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title TradeExecutor
 * @notice Executes trades on behalf of the FinAgentX AI.
 *         In production: integrates with a DEX router (Uniswap V3, etc.).
 *         Currently emits events for off-chain tracking; swap logic is pluggable.
 */

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

interface IFundVault {
    function authorizeTradeExecution(address user, address token, uint256 amount, string calldata symbol) external;
    function creditTradeProceeds(address user, address token, uint256 amount) external;
    function autonomousMode(address user) external view returns (bool);
}

contract TradeExecutor is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ─── State ────────────────────────────────────────────────────────────────

    IFundVault public vault;
    address    public agentWallet;      // off-chain agent address that can call executeTrade

    uint256 public tradeCounter;

    enum Direction { BUY, SELL }
    enum TradeStatus { PENDING, EXECUTED, FAILED, CANCELLED }

    struct TradeRecord {
        uint256   id;
        address   user;
        string    symbol;
        Direction direction;
        uint256   amount;
        uint256   executedPrice;    // stored as price * 1e8 (8 decimal precision)
        uint256   timestamp;
        TradeStatus status;
    }

    mapping(uint256 => TradeRecord) public trades;
    mapping(address => uint256[])   public userTradeIds;

    // ─── Events ───────────────────────────────────────────────────────────────

    event TradeRequested(uint256 indexed tradeId, address indexed user, string symbol, Direction direction, uint256 amount);
    event TradeExecuted(uint256 indexed tradeId, uint256 executedPrice, uint256 timestamp);
    event TradeFailed(uint256 indexed tradeId, string reason);
    event VaultUpdated(address indexed newVault);
    event AgentWalletUpdated(address indexed newAgent);

    // ─── Modifiers ────────────────────────────────────────────────────────────

    modifier onlyAgentOrOwner() {
        require(
            msg.sender == agentWallet || msg.sender == owner(),
            "TradeExecutor: unauthorized"
        );
        _;
    }

    // ─── Constructor ──────────────────────────────────────────────────────────

    constructor(address _vault, address _agentWallet) Ownable(msg.sender) {
        require(_vault != address(0), "zero vault");
        require(_agentWallet != address(0), "zero agent");
        vault        = IFundVault(_vault);
        agentWallet  = _agentWallet;
    }

    // ─── Core: execute a trade ────────────────────────────────────────────────

    /**
     * @notice Execute a trade for a user.
     * @param user       Address whose funds are used (must have autonomous mode enabled)
     * @param symbol     Trading pair string (e.g. "BTCUSDT")
     * @param direction  0 = BUY, 1 = SELL
     * @param amount     Amount in wei / token units
     * @param minPrice   Minimum acceptable execution price (slippage protection) * 1e8
     * @return tradeId   Unique trade identifier
     */
    function executeTrade(
        address  user,
        string   calldata symbol,
        uint8    direction,
        uint256  amount,
        uint256  minPrice
    ) external onlyAgentOrOwner nonReentrant returns (uint256 tradeId) {
        require(amount > 0, "TradeExecutor: zero amount");
        require(vault.autonomousMode(user), "TradeExecutor: user autonomous mode off");

        tradeCounter++;
        tradeId = tradeCounter;

        Direction dir = Direction(direction);

        // Record trade
        trades[tradeId] = TradeRecord({
            id:            tradeId,
            user:          user,
            symbol:        symbol,
            direction:     dir,
            amount:        amount,
            executedPrice: 0,
            timestamp:     block.timestamp,
            status:        TradeStatus.PENDING,
        });
        userTradeIds[user].push(tradeId);

        emit TradeRequested(tradeId, user, symbol, dir, amount);

        // Authorize fund usage from vault
        try vault.authorizeTradeExecution(user, address(0), amount, symbol) {
            // In production: call DEX router here
            // For demo: simulate execution at oracle price
            uint256 execPrice = _getOraclePrice(symbol);

            require(
                dir == Direction.SELL || execPrice >= minPrice,
                "TradeExecutor: slippage exceeded"
            );

            trades[tradeId].executedPrice = execPrice;
            trades[tradeId].status        = TradeStatus.EXECUTED;

            emit TradeExecuted(tradeId, execPrice, block.timestamp);
        } catch Error(string memory reason) {
            trades[tradeId].status = TradeStatus.FAILED;
            emit TradeFailed(tradeId, reason);
        }

        return tradeId;
    }

    /**
     * @notice Cancel a pending trade (user or agent only).
     */
    function cancelTrade(uint256 tradeId) external {
        TradeRecord storage t = trades[tradeId];
        require(t.id != 0, "TradeExecutor: trade not found");
        require(
            msg.sender == t.user || msg.sender == agentWallet || msg.sender == owner(),
            "TradeExecutor: unauthorized"
        );
        require(t.status == TradeStatus.PENDING, "TradeExecutor: not cancellable");
        t.status = TradeStatus.CANCELLED;
    }

    // ─── View helpers ─────────────────────────────────────────────────────────

    function getUserTrades(address user) external view returns (uint256[] memory) {
        return userTradeIds[user];
    }

    function getTrade(uint256 tradeId) external view returns (TradeRecord memory) {
        return trades[tradeId];
    }

    /**
     * @dev Mock oracle – returns hardcoded prices for demo.
     *      In production: use Chainlink price feeds.
     *      Price stored as value * 1e8 (matches Chainlink format).
     */
    function _getOraclePrice(string memory symbol) internal pure returns (uint256) {
        bytes32 h = keccak256(abi.encodePacked(symbol));
        if (h == keccak256("BTCUSDT")) return 68_000 * 1e8;
        if (h == keccak256("ETHUSDT")) return  3_500 * 1e8;
        if (h == keccak256("BNBUSDT")) return    580 * 1e8;
        if (h == keccak256("SOLUSDT")) return    175 * 1e8;
        return 1 * 1e8;  // default
    }

    // ─── Admin ────────────────────────────────────────────────────────────────

    function setVault(address _vault) external onlyOwner {
        vault = IFundVault(_vault);
        emit VaultUpdated(_vault);
    }

    function setAgentWallet(address _agent) external onlyOwner {
        agentWallet = _agent;
        emit AgentWalletUpdated(_agent);
    }
}

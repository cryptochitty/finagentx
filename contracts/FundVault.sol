// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title FundVault
 * @notice Secure vault for FinAgentX users.
 *         Users deposit ETH/ERC-20 which the AI agent can trade on their behalf.
 *         Users can withdraw at any time. Owner can enable/disable autonomous mode.
 */

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract FundVault is ReentrancyGuard, Ownable {
    using SafeERC20 for IERC20;

    // ─── State ────────────────────────────────────────────────────────────────

    // Authorized AI agent address (set by owner, can execute trades)
    address public agentAddress;

    // Per-user ETH balances
    mapping(address => uint256) public ethBalances;

    // Per-user ERC-20 balances: user => token => amount
    mapping(address => mapping(address => uint256)) public tokenBalances;

    // Autonomous mode per user: user => enabled
    mapping(address => bool) public autonomousMode;

    // Cumulative fees collected (owner can withdraw)
    uint256 public totalFeesCollected;

    // Trade fee: 0.1% (10 basis points)
    uint256 public constant FEE_BPS = 10;
    uint256 public constant BPS_BASE = 10_000;

    // ─── Events ───────────────────────────────────────────────────────────────

    event Deposited(address indexed user, uint256 amount, address indexed token);
    event Withdrawn(address indexed user, uint256 amount, address indexed token);
    event AutonomousModeSet(address indexed user, bool enabled);
    event AgentUpdated(address indexed newAgent);
    event TradeAuthorized(address indexed user, address indexed token, uint256 amount, string symbol);
    event FeeCollected(uint256 amount);

    // ─── Modifiers ────────────────────────────────────────────────────────────

    modifier onlyAgent() {
        require(msg.sender == agentAddress, "FundVault: caller is not the agent");
        _;
    }

    modifier autonomousEnabled(address user) {
        require(autonomousMode[user], "FundVault: autonomous mode not enabled by user");
        _;
    }

    // ─── Constructor ──────────────────────────────────────────────────────────

    constructor(address _agentAddress) Ownable(msg.sender) {
        require(_agentAddress != address(0), "FundVault: zero agent address");
        agentAddress = _agentAddress;
    }

    // ─── Deposit ──────────────────────────────────────────────────────────────

    /**
     * @notice Deposit native ETH into the vault.
     */
    function depositETH() external payable nonReentrant {
        require(msg.value > 0, "FundVault: zero deposit");
        ethBalances[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value, address(0));
    }

    /**
     * @notice Deposit an ERC-20 token.
     * @param token   Token contract address
     * @param amount  Amount in token's smallest unit
     */
    function depositToken(address token, uint256 amount) external nonReentrant {
        require(amount > 0, "FundVault: zero deposit");
        require(token != address(0), "FundVault: zero token address");
        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);
        tokenBalances[msg.sender][token] += amount;
        emit Deposited(msg.sender, amount, token);
    }

    // ─── Withdraw ─────────────────────────────────────────────────────────────

    /**
     * @notice Withdraw ETH. Users can always withdraw – agent cannot block withdrawals.
     */
    function withdrawETH(uint256 amount) external nonReentrant {
        require(amount > 0, "FundVault: zero amount");
        require(ethBalances[msg.sender] >= amount, "FundVault: insufficient ETH balance");
        ethBalances[msg.sender] -= amount;
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "FundVault: ETH transfer failed");
        emit Withdrawn(msg.sender, amount, address(0));
    }

    /**
     * @notice Withdraw an ERC-20 token.
     */
    function withdrawToken(address token, uint256 amount) external nonReentrant {
        require(amount > 0, "FundVault: zero amount");
        require(tokenBalances[msg.sender][token] >= amount, "FundVault: insufficient balance");
        tokenBalances[msg.sender][token] -= amount;
        IERC20(token).safeTransfer(msg.sender, amount);
        emit Withdrawn(msg.sender, amount, token);
    }

    // ─── Autonomous mode ──────────────────────────────────────────────────────

    /**
     * @notice User toggles autonomous trading mode on/off.
     *         The AI agent can only execute trades when this is true.
     */
    function setAutonomousMode(bool enabled) external {
        autonomousMode[msg.sender] = enabled;
        emit AutonomousModeSet(msg.sender, enabled);
    }

    // ─── Agent-only functions ─────────────────────────────────────────────────

    /**
     * @notice Agent records a trade execution on behalf of user.
     *         In a real DEX integration this would call the DEX router.
     *         Here it emits an event for frontend tracking.
     * @param user    The user whose funds are used
     * @param token   Token being traded
     * @param amount  Amount to trade
     * @param symbol  Trading pair (e.g. "BTCUSDT") – off-chain reference
     */
    function authorizeTradeExecution(
        address user,
        address token,
        uint256 amount,
        string calldata symbol
    ) external onlyAgent autonomousEnabled(user) nonReentrant {
        uint256 fee = (amount * FEE_BPS) / BPS_BASE;

        if (token == address(0)) {
            // ETH trade
            require(ethBalances[user] >= amount, "FundVault: insufficient ETH for trade");
            ethBalances[user]    -= (amount - fee);
            totalFeesCollected   += fee;
        } else {
            // ERC-20 trade
            require(tokenBalances[user][token] >= amount, "FundVault: insufficient token for trade");
            tokenBalances[user][token] -= (amount - fee);
            totalFeesCollected         += fee;
        }

        emit TradeAuthorized(user, token, amount - fee, symbol);
        emit FeeCollected(fee);
    }

    /**
     * @notice Return proceeds from a completed trade back to user's balance.
     */
    function creditTradeProceeds(
        address user,
        address token,
        uint256 amount
    ) external onlyAgent {
        if (token == address(0)) {
            ethBalances[user] += amount;
        } else {
            tokenBalances[user][token] += amount;
        }
    }

    // ─── Owner functions ──────────────────────────────────────────────────────

    function setAgent(address newAgent) external onlyOwner {
        require(newAgent != address(0), "FundVault: zero address");
        agentAddress = newAgent;
        emit AgentUpdated(newAgent);
    }

    function collectFees() external onlyOwner nonReentrant {
        uint256 fees = totalFeesCollected;
        totalFeesCollected = 0;
        (bool ok, ) = owner().call{value: fees}("");
        require(ok, "FundVault: fee transfer failed");
    }

    // ─── View helpers ─────────────────────────────────────────────────────────

    function getBalances(address user, address token) external view returns (uint256 eth, uint256 tok) {
        eth = ethBalances[user];
        tok = tokenBalances[user][token];
    }

    receive() external payable {
        ethBalances[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value, address(0));
    }
}

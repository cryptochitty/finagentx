// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title PaymentScheduler
 * @notice PayFi automation – schedule recurring or one-time payments.
 *         The FinAgentX agent calls executePayment() when a payment is due.
 *         All funds are held in FundVault; this contract only moves tokens.
 */

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract PaymentScheduler is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ─── Types ────────────────────────────────────────────────────────────────

    enum Frequency { ONCE, DAILY, WEEKLY, MONTHLY }
    enum PaymentStatus { ACTIVE, PAUSED, COMPLETED, CANCELLED }

    struct ScheduledPayment {
        uint256       id;
        address       payer;
        address       recipient;
        address       token;        // address(0) = native ETH
        uint256       amount;
        Frequency     frequency;
        uint256       nextExecution;
        uint256       executionCount;
        uint256       maxExecutions; // 0 = unlimited
        PaymentStatus status;
    }

    // ─── State ────────────────────────────────────────────────────────────────

    uint256 public paymentCounter;
    address public agentAddress;

    mapping(uint256 => ScheduledPayment) public payments;
    mapping(address => uint256[]) public userPayments;

    // Seconds per frequency
    uint256 constant DAY   = 86_400;
    uint256 constant WEEK  = 7 * DAY;
    uint256 constant MONTH = 30 * DAY;

    // ─── Events ───────────────────────────────────────────────────────────────

    event PaymentScheduled(uint256 indexed id, address indexed payer, address recipient, uint256 amount, Frequency frequency);
    event PaymentExecuted(uint256 indexed id, address indexed payer, address recipient, uint256 amount, uint256 timestamp);
    event PaymentCancelled(uint256 indexed id);
    event PaymentPaused(uint256 indexed id);
    event PaymentResumed(uint256 indexed id);

    // ─── Modifiers ────────────────────────────────────────────────────────────

    modifier onlyAgent() {
        require(msg.sender == agentAddress || msg.sender == owner(), "PaymentScheduler: not agent");
        _;
    }

    // ─── Constructor ──────────────────────────────────────────────────────────

    constructor(address _agentAddress) Ownable(msg.sender) {
        agentAddress = _agentAddress;
    }

    // ─── Schedule ─────────────────────────────────────────────────────────────

    /**
     * @notice Create a new scheduled payment.
     * @param recipient     Who receives the payment
     * @param token         Token address (address(0) for ETH)
     * @param amount        Amount per execution
     * @param frequency     ONCE, DAILY, WEEKLY, MONTHLY
     * @param startDelay    Seconds from now until first execution
     * @param maxExecutions 0 = run forever
     */
    function schedulePayment(
        address   recipient,
        address   token,
        uint256   amount,
        uint8     frequency,
        uint256   startDelay,
        uint256   maxExecutions
    ) external returns (uint256 paymentId) {
        require(amount > 0,         "PaymentScheduler: zero amount");
        require(recipient != address(0), "PaymentScheduler: zero recipient");

        paymentCounter++;
        paymentId = paymentCounter;

        payments[paymentId] = ScheduledPayment({
            id:             paymentId,
            payer:          msg.sender,
            recipient:      recipient,
            token:          token,
            amount:         amount,
            frequency:      Frequency(frequency),
            nextExecution:  block.timestamp + startDelay,
            executionCount: 0,
            maxExecutions:  maxExecutions,
            status:         PaymentStatus.ACTIVE,
        });

        userPayments[msg.sender].push(paymentId);

        emit PaymentScheduled(paymentId, msg.sender, recipient, amount, Frequency(frequency));
    }

    // ─── Execute ──────────────────────────────────────────────────────────────

    /**
     * @notice Execute a due payment. Called by the FinAgentX agent.
     *         Requires payer to have approved this contract (ERC-20)
     *         or sent sufficient ETH.
     */
    function executePayment(uint256 paymentId) external onlyAgent nonReentrant {
        ScheduledPayment storage p = payments[paymentId];
        require(p.id != 0,                                      "PaymentScheduler: not found");
        require(p.status == PaymentStatus.ACTIVE,               "PaymentScheduler: not active");
        require(block.timestamp >= p.nextExecution,             "PaymentScheduler: not yet due");

        // Transfer funds
        if (p.token == address(0)) {
            // ETH payment – payer must have pre-deposited ETH to this contract
            require(address(this).balance >= p.amount, "PaymentScheduler: insufficient ETH");
            (bool ok, ) = p.recipient.call{value: p.amount}("");
            require(ok, "PaymentScheduler: ETH transfer failed");
        } else {
            // ERC-20: transferFrom payer's wallet (must be pre-approved)
            IERC20(p.token).safeTransferFrom(p.payer, p.recipient, p.amount);
        }

        p.executionCount++;

        emit PaymentExecuted(paymentId, p.payer, p.recipient, p.amount, block.timestamp);

        // Update next execution or mark complete
        if (p.maxExecutions > 0 && p.executionCount >= p.maxExecutions) {
            p.status = PaymentStatus.COMPLETED;
        } else if (p.frequency == Frequency.ONCE) {
            p.status = PaymentStatus.COMPLETED;
        } else {
            p.nextExecution = block.timestamp + _frequencySeconds(p.frequency);
        }
    }

    /**
     * @notice Execute multiple due payments in a single transaction (gas batching).
     */
    function executeBatch(uint256[] calldata paymentIds) external onlyAgent {
        for (uint256 i = 0; i < paymentIds.length; i++) {
            this.executePayment(paymentIds[i]);
        }
    }

    // ─── User controls ────────────────────────────────────────────────────────

    function cancelPayment(uint256 paymentId) external {
        ScheduledPayment storage p = payments[paymentId];
        require(msg.sender == p.payer || msg.sender == owner(), "PaymentScheduler: unauthorized");
        p.status = PaymentStatus.CANCELLED;
        emit PaymentCancelled(paymentId);
    }

    function pausePayment(uint256 paymentId) external {
        require(payments[paymentId].payer == msg.sender, "PaymentScheduler: unauthorized");
        payments[paymentId].status = PaymentStatus.PAUSED;
        emit PaymentPaused(paymentId);
    }

    function resumePayment(uint256 paymentId) external {
        require(payments[paymentId].payer == msg.sender, "PaymentScheduler: unauthorized");
        payments[paymentId].status = PaymentStatus.ACTIVE;
        emit PaymentResumed(paymentId);
    }

    // ─── View ─────────────────────────────────────────────────────────────────

    function getUserPayments(address user) external view returns (uint256[] memory) {
        return userPayments[user];
    }

    function getDuePayments(address user) external view returns (uint256[] memory) {
        uint256[] memory ids = userPayments[user];
        uint256 count = 0;
        for (uint256 i = 0; i < ids.length; i++) {
            ScheduledPayment storage p = payments[ids[i]];
            if (p.status == PaymentStatus.ACTIVE && block.timestamp >= p.nextExecution) {
                count++;
            }
        }
        uint256[] memory due = new uint256[](count);
        uint256 idx = 0;
        for (uint256 i = 0; i < ids.length; i++) {
            ScheduledPayment storage p = payments[ids[i]];
            if (p.status == PaymentStatus.ACTIVE && block.timestamp >= p.nextExecution) {
                due[idx++] = ids[i];
            }
        }
        return due;
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    function _frequencySeconds(Frequency f) internal pure returns (uint256) {
        if (f == Frequency.DAILY)   return DAY;
        if (f == Frequency.WEEKLY)  return WEEK;
        if (f == Frequency.MONTHLY) return MONTH;
        return 0;
    }

    function setAgent(address _agent) external onlyOwner {
        agentAddress = _agent;
    }

    receive() external payable {}
}

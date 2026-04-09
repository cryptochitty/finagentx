/**
 * FinAgentX – Contract Test Suite
 * Tests: FundVault · TradeExecutor · PaymentScheduler
 *
 * Run:  cd contracts && npx hardhat test
 */
const { expect }  = require("chai");
const { ethers }  = require("hardhat");

describe("FinAgentX Contracts", function () {
  let owner, user1, user2, agentWallet;
  let vault, executor, scheduler;

  beforeEach(async function () {
    [owner, user1, user2, agentWallet] = await ethers.getSigners();

    // ── Deploy ─────────────────────────────────────────────────────────────
    const FundVault = await ethers.getContractFactory("FundVault");
    vault = await FundVault.deploy(owner.address);
    await vault.waitForDeployment();

    const TradeExecutor = await ethers.getContractFactory("TradeExecutor");
    executor = await TradeExecutor.deploy(
      await vault.getAddress(),
      agentWallet.address,
    );
    await executor.waitForDeployment();

    const PaymentScheduler = await ethers.getContractFactory("PaymentScheduler");
    scheduler = await PaymentScheduler.deploy(agentWallet.address);
    await scheduler.waitForDeployment();

    // Wire: vault agent → executor (so executor can authorizeTradeExecution)
    await vault.setAgent(await executor.getAddress());
  });

  // ─────────────────────────────────────────────────────────────────────────
  describe("FundVault", function () {
    it("accepts ETH deposits via depositETH()", async function () {
      const amt = ethers.parseEther("1.0");
      await vault.connect(user1).depositETH({ value: amt });
      expect(await vault.ethBalances(user1.address)).to.equal(amt);
    });

    it("accepts ETH via receive() fallback", async function () {
      const amt = ethers.parseEther("0.5");
      await user1.sendTransaction({ to: await vault.getAddress(), value: amt });
      expect(await vault.ethBalances(user1.address)).to.equal(amt);
    });

    it("allows full ETH withdrawal", async function () {
      const amt = ethers.parseEther("1.0");
      await vault.connect(user1).depositETH({ value: amt });
      await vault.connect(user1).withdrawETH(amt);
      expect(await vault.ethBalances(user1.address)).to.equal(0n);
    });

    it("reverts on withdrawal exceeding balance", async function () {
      await expect(
        vault.connect(user1).withdrawETH(ethers.parseEther("1.0"))
      ).to.be.revertedWith("FundVault: insufficient ETH balance");
    });

    it("reverts on zero deposit", async function () {
      await expect(
        vault.connect(user1).depositETH({ value: 0 })
      ).to.be.revertedWith("FundVault: zero deposit");
    });

    it("sets autonomous mode per user", async function () {
      expect(await vault.autonomousMode(user1.address)).to.equal(false);
      await vault.connect(user1).setAutonomousMode(true);
      expect(await vault.autonomousMode(user1.address)).to.equal(true);
      await vault.connect(user1).setAutonomousMode(false);
      expect(await vault.autonomousMode(user1.address)).to.equal(false);
    });

    it("emits AutonomousModeSet event", async function () {
      await expect(vault.connect(user1).setAutonomousMode(true))
        .to.emit(vault, "AutonomousModeSet")
        .withArgs(user1.address, true);
    });

    it("emits Deposited event", async function () {
      const amt = ethers.parseEther("0.1");
      await expect(vault.connect(user1).depositETH({ value: amt }))
        .to.emit(vault, "Deposited")
        .withArgs(user1.address, amt, ethers.ZeroAddress);
    });

    it("blocks trade when autonomous mode is off", async function () {
      const amt = ethers.parseEther("0.1");
      await vault.connect(user1).depositETH({ value: amt });
      // autonomous mode defaults to false → should revert
      await expect(
        vault
          .connect(await ethers.getSigner(await executor.getAddress()))
          .authorizeTradeExecution(user1.address, ethers.ZeroAddress, amt, "BTCUSDT")
      ).to.be.reverted;
    });

    it("only owner can setAgent", async function () {
      await expect(
        vault.connect(user1).setAgent(user2.address)
      ).to.be.reverted;
    });

    it("getBalances returns correct ETH balance", async function () {
      const amt = ethers.parseEther("2.0");
      await vault.connect(user1).depositETH({ value: amt });
      const [eth, tok] = await vault.getBalances(user1.address, ethers.ZeroAddress);
      expect(eth).to.equal(amt);
      expect(tok).to.equal(0n);
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  describe("TradeExecutor", function () {
    beforeEach(async function () {
      // Fund user and enable autonomous mode
      await vault.connect(user1).depositETH({ value: ethers.parseEther("2.0") });
      await vault.connect(user1).setAutonomousMode(true);
    });

    it("executes a BUY trade and emits TradeRequested + TradeExecuted", async function () {
      const amt = ethers.parseEther("0.1");
      await expect(
        executor.connect(agentWallet).executeTrade(
          user1.address, "BTCUSDT",
          0,    // BUY
          amt,
          0,    // minPrice = 0 (no slippage check)
        )
      )
        .to.emit(executor, "TradeRequested")
        .and.to.emit(executor, "TradeExecuted");
    });

    it("executes a SELL trade", async function () {
      const amt = ethers.parseEther("0.05");
      const tx = await executor.connect(agentWallet).executeTrade(
        user1.address, "ETHUSDT", 1 /* SELL */, amt, 0,
      );
      const receipt = await tx.wait();
      expect(receipt.status).to.equal(1);
    });

    it("increments tradeCounter", async function () {
      expect(await executor.tradeCounter()).to.equal(0n);
      await executor.connect(agentWallet).executeTrade(
        user1.address, "BTCUSDT", 0, ethers.parseEther("0.01"), 0,
      );
      expect(await executor.tradeCounter()).to.equal(1n);
    });

    it("records trade in getUserTrades", async function () {
      await executor.connect(agentWallet).executeTrade(
        user1.address, "BTCUSDT", 0, ethers.parseEther("0.01"), 0,
      );
      const ids = await executor.getUserTrades(user1.address);
      expect(ids.length).to.equal(1);
    });

    it("getTrade returns correct record", async function () {
      await executor.connect(agentWallet).executeTrade(
        user1.address, "SOLUSDT", 0, ethers.parseEther("0.02"), 0,
      );
      const trade = await executor.getTrade(1);
      expect(trade.user).to.equal(user1.address);
      expect(trade.symbol).to.equal("SOLUSDT");
    });

    it("blocks unauthorized caller", async function () {
      await expect(
        executor.connect(user2).executeTrade(
          user1.address, "BTCUSDT", 0, ethers.parseEther("0.01"), 0,
        )
      ).to.be.revertedWith("TradeExecutor: unauthorized");
    });

    it("blocks trade when autonomous mode is off", async function () {
      await vault.connect(user2).depositETH({ value: ethers.parseEther("1.0") });
      // user2 did NOT enable autonomous mode
      await expect(
        executor.connect(agentWallet).executeTrade(
          user2.address, "BTCUSDT", 0, ethers.parseEther("0.01"), 0,
        )
      ).to.be.revertedWith("TradeExecutor: user autonomous mode off");
    });

    it("allows owner to update agentWallet", async function () {
      await executor.connect(owner).setAgentWallet(user2.address);
      expect(await executor.agentWallet()).to.equal(user2.address);
    });

    it("cancels a pending trade", async function () {
      // Create a trade that will be PENDING (already becomes EXECUTED in same tx, so test cancel flow)
      await executor.connect(agentWallet).executeTrade(
        user1.address, "BNBUSDT", 0, ethers.parseEther("0.01"), 0,
      );
      // Try cancelling after execution — should revert because status != PENDING
      await expect(
        executor.connect(agentWallet).cancelTrade(1)
      ).to.be.revertedWith("TradeExecutor: not cancellable");
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  describe("PaymentScheduler", function () {
    it("creates a one-time payment", async function () {
      await scheduler.connect(user1).schedulePayment(
        user2.address,
        ethers.ZeroAddress,
        ethers.parseEther("0.01"),
        0,  // ONCE
        0,  // startDelay = 0 (due now)
        1,  // maxExecutions = 1
      );
      expect(await scheduler.paymentCounter()).to.equal(1n);
    });

    it("emits PaymentScheduled", async function () {
      await expect(
        scheduler.connect(user1).schedulePayment(
          user2.address, ethers.ZeroAddress, ethers.parseEther("0.01"), 0, 0, 1,
        )
      ).to.emit(scheduler, "PaymentScheduled");
    });

    it("executes a due ETH payment", async function () {
      // Fund scheduler with ETH first
      await owner.sendTransaction({
        to: await scheduler.getAddress(),
        value: ethers.parseEther("0.1"),
      });

      await scheduler.connect(user1).schedulePayment(
        user2.address, ethers.ZeroAddress, ethers.parseEther("0.01"), 0, 0, 1,
      );

      await expect(
        scheduler.connect(agentWallet).executePayment(1)
      ).to.emit(scheduler, "PaymentExecuted");
    });

    it("marks one-time payment as COMPLETED after execution", async function () {
      await owner.sendTransaction({
        to: await scheduler.getAddress(),
        value: ethers.parseEther("0.05"),
      });
      await scheduler.connect(user1).schedulePayment(
        user2.address, ethers.ZeroAddress, ethers.parseEther("0.01"), 0, 0, 1,
      );
      await scheduler.connect(agentWallet).executePayment(1);
      const p = await scheduler.payments(1);
      expect(p.status).to.equal(2n); // COMPLETED = 2
    });

    it("cancels a payment", async function () {
      await scheduler.connect(user1).schedulePayment(
        user2.address, ethers.ZeroAddress, ethers.parseEther("0.01"), 0, 3600, 0,
      );
      await scheduler.connect(user1).cancelPayment(1);
      const p = await scheduler.payments(1);
      expect(p.status).to.equal(3n); // CANCELLED = 3
    });

    it("pauses and resumes a payment", async function () {
      await scheduler.connect(user1).schedulePayment(
        user2.address, ethers.ZeroAddress, ethers.parseEther("0.01"), 1 /* DAILY */, 0, 0,
      );
      await scheduler.connect(user1).pausePayment(1);
      expect((await scheduler.payments(1)).status).to.equal(1n); // PAUSED = 1
      await scheduler.connect(user1).resumePayment(1);
      expect((await scheduler.payments(1)).status).to.equal(0n); // ACTIVE = 0
    });

    it("blocks execution before due time", async function () {
      await scheduler.connect(user1).schedulePayment(
        user2.address, ethers.ZeroAddress, ethers.parseEther("0.01"),
        0, 3600, 1, // startDelay = 1 hour
      );
      await expect(
        scheduler.connect(agentWallet).executePayment(1)
      ).to.be.revertedWith("PaymentScheduler: not yet due");
    });

    it("returns user payments list", async function () {
      await scheduler.connect(user1).schedulePayment(
        user2.address, ethers.ZeroAddress, ethers.parseEther("0.01"), 0, 0, 1,
      );
      await scheduler.connect(user1).schedulePayment(
        owner.address, ethers.ZeroAddress, ethers.parseEther("0.02"), 1, 0, 0,
      );
      const ids = await scheduler.getUserPayments(user1.address);
      expect(ids.length).to.equal(2);
    });

    it("only agent/owner can execute payments", async function () {
      await owner.sendTransaction({
        to: await scheduler.getAddress(),
        value: ethers.parseEther("0.05"),
      });
      await scheduler.connect(user1).schedulePayment(
        user2.address, ethers.ZeroAddress, ethers.parseEther("0.01"), 0, 0, 1,
      );
      await expect(
        scheduler.connect(user1).executePayment(1)
      ).to.be.revertedWith("PaymentScheduler: not agent");
    });

    it("executes a batch of payments", async function () {
      await owner.sendTransaction({
        to: await scheduler.getAddress(),
        value: ethers.parseEther("0.1"),
      });
      // Schedule two payments due immediately
      await scheduler.connect(user1).schedulePayment(
        user2.address, ethers.ZeroAddress, ethers.parseEther("0.01"), 0, 0, 1,
      );
      await scheduler.connect(user1).schedulePayment(
        owner.address, ethers.ZeroAddress, ethers.parseEther("0.01"), 0, 0, 1,
      );
      // executeBatch calls this.executePayment() internally
      await scheduler.connect(agentWallet).executeBatch([1, 2]);
      expect((await scheduler.payments(1)).status).to.equal(2n); // COMPLETED
      expect((await scheduler.payments(2)).status).to.equal(2n); // COMPLETED
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  describe("Full integration: Vault → Executor pipeline", function () {
    it("deducts user balance after authorized trade", async function () {
      const deposit = ethers.parseEther("1.0");
      const trade   = ethers.parseEther("0.1");
      const fee     = (trade * 10n) / 10_000n;  // 0.1% fee

      await vault.connect(user1).depositETH({ value: deposit });
      await vault.connect(user1).setAutonomousMode(true);

      await executor.connect(agentWallet).executeTrade(
        user1.address, "BTCUSDT", 0, trade, 0,
      );

      const remaining = await vault.ethBalances(user1.address);
      // balance should be deposit - (trade - fee) = deposit - trade + fee
      expect(remaining).to.equal(deposit - trade + fee);
    });
  });
});

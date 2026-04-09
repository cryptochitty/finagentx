/**
 * FinAgentX – Contract Deployment Script
 * Usage: npx hardhat run contracts/deploy.js --network hashkey
 */
const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("\n Deploying FinAgentX contracts...");
  console.log(" Deployer:", deployer.address);
  console.log(" Balance: ", ethers.formatEther(await deployer.provider.getBalance(deployer.address)), "ETH\n");

  // 1. Deploy FundVault
  const FundVault = await ethers.getContractFactory("FundVault");
  const vault = await FundVault.deploy(deployer.address);
  await vault.waitForDeployment();
  console.log("✅ FundVault deployed to:       ", await vault.getAddress());

  // 2. Deploy TradeExecutor
  const TradeExecutor = await ethers.getContractFactory("TradeExecutor");
  const executor = await TradeExecutor.deploy(await vault.getAddress(), deployer.address);
  await executor.waitForDeployment();
  console.log("✅ TradeExecutor deployed to:   ", await executor.getAddress());

  // 3. Deploy PaymentScheduler
  const PaymentScheduler = await ethers.getContractFactory("PaymentScheduler");
  const scheduler = await PaymentScheduler.deploy(deployer.address);
  await scheduler.waitForDeployment();
  console.log("✅ PaymentScheduler deployed to:", await scheduler.getAddress());

  // 4. Wire up: set TradeExecutor as authorized agent on FundVault
  await vault.setAgent(await executor.getAddress());
  console.log("\n Vault agent set to TradeExecutor ✓");

  console.log("\n Deployment complete! Add these to your .env:");
  console.log(`VAULT_ADDRESS=${await vault.getAddress()}`);
  console.log(`TRADE_EXEC_ADDRESS=${await executor.getAddress()}`);
  console.log(`PAYFI_ADDRESS=${await scheduler.getAddress()}`);
}

main().catch(e => { console.error(e); process.exit(1); });

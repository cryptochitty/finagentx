/**
 * FinAgentX – Unified deploy script
 * Works on: localhost | hashkey_testnet | hashkey (mainnet)
 *
 * Usage:
 *   npx hardhat run deploy.js --network hashkey_testnet
 *   npx hardhat run deploy.js --network hashkey
 *   npx hardhat run deploy.js --network localhost
 */
const { ethers, network } = require("hardhat");
const fs   = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  const balance    = await deployer.provider.getBalance(deployer.address);

  console.log("\n╔══════════════════════════════════════════╗");
  console.log("║   FinAgentX – Contract Deployment         ║");
  console.log("╚══════════════════════════════════════════╝");
  console.log(`Network:   ${network.name} (chainId: ${network.config.chainId})`);
  console.log(`Deployer:  ${deployer.address}`);
  console.log(`Balance:   ${ethers.formatEther(balance)} ETH/HSK\n`);

  if (ethers.formatEther(balance) === "0.0" && network.name !== "hardhat") {
    console.error("❌  Deployer wallet has 0 balance.");
    if (network.name === "hashkey_testnet") {
      console.error("   Get free testnet HSK from: https://faucet.hsk.xyz");
    }
    process.exit(1);
  }

  // ── 1. FundVault ────────────────────────────────────────────────────────
  console.log("Deploying FundVault...");
  const FundVault = await ethers.getContractFactory("FundVault");
  const vault     = await FundVault.deploy(deployer.address);
  await vault.waitForDeployment();
  const vaultAddr = await vault.getAddress();
  console.log(`✅ FundVault:          ${vaultAddr}`);

  // ── 2. TradeExecutor ────────────────────────────────────────────────────
  console.log("Deploying TradeExecutor...");
  const TradeExecutor = await ethers.getContractFactory("TradeExecutor");
  const executor      = await TradeExecutor.deploy(vaultAddr, deployer.address);
  await executor.waitForDeployment();
  const executorAddr  = await executor.getAddress();
  console.log(`✅ TradeExecutor:      ${executorAddr}`);

  // ── 3. PaymentScheduler ─────────────────────────────────────────────────
  console.log("Deploying PaymentScheduler...");
  const PaymentScheduler = await ethers.getContractFactory("PaymentScheduler");
  const scheduler        = await PaymentScheduler.deploy(deployer.address);
  await scheduler.waitForDeployment();
  const schedulerAddr    = await scheduler.getAddress();
  console.log(`✅ PaymentScheduler:   ${schedulerAddr}`);

  // ── 4. Wire up: set TradeExecutor as vault agent ────────────────────────
  console.log("\nWiring contracts...");
  await vault.setAgent(executorAddr);
  console.log("✅ Vault agent → TradeExecutor");

  // ── 5. Save addresses ────────────────────────────────────────────────────
  const out = {
    network:       network.name,
    chainId:       network.config.chainId,
    deployer:      deployer.address,
    FundVault:     vaultAddr,
    TradeExecutor: executorAddr,
    PaymentScheduler: schedulerAddr,
    deployedAt:    new Date().toISOString(),
  };

  // Write to contracts/deployments/<network>.json
  const deploymentsDir = path.join(__dirname, "deployments");
  if (!fs.existsSync(deploymentsDir)) fs.mkdirSync(deploymentsDir);
  const outFile = path.join(deploymentsDir, `${network.name}.json`);
  fs.writeFileSync(outFile, JSON.stringify(out, null, 2));

  console.log(`\n📄 Addresses saved to: contracts/deployments/${network.name}.json`);

  // Print env vars to copy into Render
  console.log("\n══════════════════════════════════════════");
  console.log("Add these to Render Environment Variables:");
  console.log("══════════════════════════════════════════");
  console.log(`VAULT_ADDRESS=${vaultAddr}`);
  console.log(`TRADE_EXEC_ADDRESS=${executorAddr}`);
  console.log(`PAYFI_ADDRESS=${schedulerAddr}`);
  console.log(`SIMULATION_MODE=false`);
  if (network.name === "hashkey_testnet") {
    console.log(`RPC_URL=https://hashkeychain-testnet.alt.technology`);
    console.log(`CHAIN_ID=133`);
  } else if (network.name === "hashkey") {
    console.log(`RPC_URL=https://mainnet.hsk.xyz`);
    console.log(`CHAIN_ID=177`);
  }
  console.log("══════════════════════════════════════════\n");
}

main().catch(e => { console.error(e); process.exit(1); });

require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config({ path: "../.env" });

const PK = process.env.PRIVATE_KEY || "0x" + "a".repeat(64); // dummy key for compile-only

module.exports = {
  solidity: {
    version: "0.8.20",
    settings: { optimizer: { enabled: true, runs: 200 } },
  },
  networks: {
    // ── local ──────────────────────────────────────────────────────────────
    hardhat:   {},
    localhost: { url: "http://127.0.0.1:8545" },

    // ── HashKey Chain Testnet (Chain ID 133) ───────────────────────────────
    // Faucet: https://faucet.hsk.xyz  |  Explorer: https://testnet-explorer.hsk.xyz
    hashkey_testnet: {
      url:      "https://hashkeychain-testnet.alt.technology",
      chainId:  133,
      accounts: [PK],
    },

    // ── HashKey Chain Mainnet (Chain ID 177) ───────────────────────────────
    hashkey: {
      url:      process.env.RPC_URL || "https://mainnet.hsk.xyz",
      chainId:  177,
      accounts: [PK],
    },
  },
  etherscan: {
    apiKey: { hashkey_testnet: "no-key", hashkey: "no-key" },
    customChains: [
      {
        network: "hashkey_testnet",
        chainId: 133,
        urls: {
          apiURL:     "https://testnet-explorer.hsk.xyz/api",
          browserURL: "https://testnet-explorer.hsk.xyz",
        },
      },
      {
        network: "hashkey",
        chainId: 177,
        urls: {
          apiURL:     "https://explorer.hsk.xyz/api",
          browserURL: "https://explorer.hsk.xyz",
        },
      },
    ],
  },
};

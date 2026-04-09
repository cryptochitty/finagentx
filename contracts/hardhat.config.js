require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config({ path: "../.env" });

const PRIVATE_KEY = process.env.PRIVATE_KEY || "0x" + "a".repeat(64);

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    // Local development
    hardhat: {},
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    // HashKey Chain Mainnet
    hashkey: {
      url: process.env.RPC_URL || "https://mainnet.hsk.xyz",
      chainId: 177,
      accounts: [PRIVATE_KEY],
    },
    // HashKey Chain Testnet
    hashkey_testnet: {
      url: "https://hashkeychain-testnet.alt.technology",
      chainId: 133,
      accounts: [PRIVATE_KEY],
    },
  },
  etherscan: {
    apiKey: {
      hashkey: process.env.HASHKEY_EXPLORER_API_KEY || "no-key-needed",
    },
    customChains: [
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

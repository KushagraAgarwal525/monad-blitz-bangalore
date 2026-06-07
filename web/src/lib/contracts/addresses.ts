export const addresses = {
  memoryToken: (process.env.NEXT_PUBLIC_MEMORY_TOKEN_ADDRESS ||
    "0x0000000000000000000000000000000000000000") as `0x${string}`,
  memoryRegistry: (process.env.NEXT_PUBLIC_MEMORY_REGISTRY_ADDRESS ||
    "0x0000000000000000000000000000000000000000") as `0x${string}`,
  licenseManager: (process.env.NEXT_PUBLIC_LICENSE_MANAGER_ADDRESS ||
    "0x0000000000000000000000000000000000000000") as `0x${string}`,
};

export const memoryRegistryAbi = [
  {
    name: "registerRepository",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "genesisCommitHash", type: "bytes32" },
      { name: "primaryParentCommitHash", type: "bytes32" },
      { name: "parentCount", type: "uint8" },
      { name: "secondaryParentsCanonical", type: "bytes32" },
      { name: "contentHash", type: "bytes32" },
      { name: "embeddingHash", type: "bytes32" },
      { name: "sourceAttributionHash", type: "bytes32" },
      { name: "stateRoot", type: "bytes32" },
      { name: "metadataURI", type: "string" },
      { name: "visibility", type: "uint8" },
    ],
    outputs: [{ type: "uint256" }],
  },
  {
    name: "createCommit",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "memoryId", type: "uint256" },
      { name: "commitHash", type: "bytes32" },
      { name: "primaryParentCommitHash", type: "bytes32" },
      { name: "parentCount", type: "uint8" },
      { name: "secondaryParentsCanonical", type: "bytes32" },
      { name: "secondaryParentCommitHashes", type: "bytes32[]" },
      { name: "contentHash", type: "bytes32" },
      { name: "embeddingHash", type: "bytes32" },
      { name: "sourceAttributionHash", type: "bytes32" },
      { name: "stateRoot", type: "bytes32" },
    ],
    outputs: [],
  },
  {
    name: "verifyLineage",
    type: "function",
    stateMutability: "view",
    inputs: [{ name: "memoryId", type: "uint256" }],
    outputs: [
      {
        name: "repoChain",
        type: "tuple[]",
        components: [
          { name: "memoryId", type: "uint256" },
          { name: "ancestorRepoIds", type: "uint256[]" },
          { name: "headToGenesisCommits", type: "bytes32[]" },
          { name: "repositoryChainValid", type: "bool" },
          { name: "forkLinksValid", type: "bool" },
          { name: "commitParentChainValid", type: "bool" },
        ],
      },
      { name: "structurallyValid", type: "bool" },
    ],
  },
] as const;

export const memoryTokenAbi = [
  {
    name: "approve",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "spender", type: "address" },
      { name: "amount", type: "uint256" },
    ],
    outputs: [{ type: "bool" }],
  },
  {
    name: "faucet",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "to", type: "address" },
      { name: "amount", type: "uint256" },
    ],
    outputs: [],
  },
  {
    name: "balanceOf",
    type: "function",
    stateMutability: "view",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ type: "uint256" }],
  },
] as const;

export const licenseManagerAbi = [
  {
    name: "hasActiveLicense",
    type: "function",
    stateMutability: "view",
    inputs: [
      { name: "memoryId", type: "uint256" },
      { name: "user", type: "address" },
    ],
    outputs: [{ type: "bool" }],
  },
  {
    name: "buyLicense",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "memoryId", type: "uint256" },
      { name: "licenseType", type: "uint8" },
      { name: "paymentType", type: "uint8" },
    ],
    outputs: [{ type: "uint256" }],
  },
] as const;

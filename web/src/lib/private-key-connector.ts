import { createConnector } from "wagmi";
import {
  custom,
  numberToHex,
  type Address,
  type Hex,
  type EIP1193Provider,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { createWalletClient, http } from "viem";

const STORAGE_KEY = "memoria_wallet_private_key";

export type PrivateKeyConnectorParameters = {
  /** Optional key from env — dev only (bundled into client if NEXT_PUBLIC_) */
  envPrivateKey?: string;
  /** Optional expected address — mismatch raises on connect */
  expectedAddress?: string;
};

function normalizeKey(key: string): Hex {
  const trimmed = key.trim();
  const hex = trimmed.startsWith("0x") ? trimmed : `0x${trimmed}`;
  if (hex.length !== 66) {
    throw new Error("Private key must be 32 bytes (64 hex chars, optional 0x prefix).");
  }
  return hex as Hex;
}

export function getStoredPrivateKey(): Hex | null {
  if (typeof window === "undefined") return null;
  const stored = sessionStorage.getItem(STORAGE_KEY);
  return stored ? normalizeKey(stored) : null;
}

export function setStoredPrivateKey(key: string): Hex {
  const hex = normalizeKey(key);
  sessionStorage.setItem(STORAGE_KEY, hex);
  return hex;
}

export function clearStoredPrivateKey(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

function resolveKey(params: PrivateKeyConnectorParameters): Hex {
  const fromEnv = params.envPrivateKey?.trim();
  if (fromEnv) return normalizeKey(fromEnv);
  const stored = getStoredPrivateKey();
  if (stored) return stored;
  throw new Error("No private key configured. Paste your key in Connect Wallet.");
}

privateKeyConnector.type = "privateKey" as const;

export function privateKeyConnector(parameters: PrivateKeyConnectorParameters = {}) {
  let connectedKey: Hex | null = null;
  let connectedChainId: number | undefined;

  return createConnector((config) => ({
    id: "privateKey",
    name: "Private Key",
    type: privateKeyConnector.type,

    async connect({ chainId, withCapabilities } = {}) {
      const key = resolveKey(parameters);
      const account = privateKeyToAccount(key);

      if (parameters.expectedAddress) {
        const expected = parameters.expectedAddress.toLowerCase();
        if (account.address.toLowerCase() !== expected) {
          throw new Error(
            `Private key does not match expected address ${parameters.expectedAddress}.`
          );
        }
      }

      connectedKey = key;
      connectedChainId = chainId ?? config.chains[0]?.id;
      if (!connectedChainId) throw new Error("No chain configured");

      return {
        accounts: (withCapabilities
          ? [{ address: account.address, capabilities: {} }]
          : [account.address]) as never,
        chainId: connectedChainId,
      };
    },

    async disconnect() {
      connectedKey = null;
      connectedChainId = undefined;
    },

    async getAccounts() {
      if (!connectedKey) return [];
      return [privateKeyToAccount(connectedKey).address];
    },

    async getChainId() {
      return connectedChainId ?? config.chains[0]?.id ?? 143;
    },

    async isAuthorized() {
      try {
        if (parameters.envPrivateKey?.trim()) return true;
        return !!getStoredPrivateKey();
      } catch {
        return false;
      }
    },

    async switchChain({ chainId }) {
      const chain = config.chains.find((c) => c.id === chainId);
      if (!chain) throw new Error(`Chain ${chainId} not configured`);
      connectedChainId = chainId;
      return chain;
    },

    onAccountsChanged() {},
    onChainChanged() {},
    onDisconnect() {
      connectedKey = null;
      connectedChainId = undefined;
      config.emitter.emit("disconnect");
    },

    async getProvider({ chainId } = {}) {
      if (!connectedKey) {
        try {
          connectedKey = resolveKey(parameters);
        } catch {
          connectedKey = null;
        }
      }
      if (!connectedKey) {
        throw new Error("Wallet not connected");
      }

      const account = privateKeyToAccount(connectedKey);
      const chain =
        config.chains.find((c) => c.id === (chainId ?? connectedChainId)) ??
        config.chains[0];
      if (!chain) throw new Error("No chain configured");

      const rpc = chain.rpcUrls.default.http[0];
      const walletClient = createWalletClient({
        account,
        chain,
        transport: http(rpc),
      });

      const provider: EIP1193Provider = {
        on: () => {},
        removeListener: () => {},
        request: (async ({ method, params }) => {
          if (method === "eth_chainId") {
            return numberToHex(chain.id);
          }
          if (method === "eth_accounts" || method === "eth_requestAccounts") {
            return [account.address];
          }
          if (method === "personal_sign") {
            const [message, address] = (params ?? []) as [Hex, Address];
            if (address.toLowerCase() !== account.address.toLowerCase()) {
              throw new Error("Address mismatch");
            }
            return walletClient.signMessage({ message: { raw: message } });
          }
          if (method === "eth_signTypedData_v4") {
            const [address, typedData] = (params ?? []) as [Address, string];
            if (address.toLowerCase() !== account.address.toLowerCase()) {
              throw new Error("Address mismatch");
            }
            const parsed = JSON.parse(typedData) as {
              domain: Record<string, unknown>;
              types: Record<string, { name: string; type: string }[]>;
              primaryType: string;
              message: Record<string, unknown>;
            };
            return walletClient.signTypedData({
              domain: parsed.domain as Parameters<typeof walletClient.signTypedData>[0]["domain"],
              types: parsed.types,
              primaryType: parsed.primaryType,
              message: parsed.message,
            });
          }
          if (method === "eth_sendTransaction") {
            const tx = (params as unknown[] | undefined)?.[0] as Parameters<
              typeof walletClient.sendTransaction
            >[0];
            return walletClient.sendTransaction({
              ...tx,
              account,
              chain,
            });
          }
          if (method === "wallet_switchEthereumChain") {
            const nextId = Number((params as [{ chainId: Hex }])?.[0]?.chainId);
            const next = config.chains.find((c) => c.id === nextId);
            if (!next) throw new Error(`Chain ${nextId} not supported`);
            connectedChainId = nextId;
            return null;
          }
          throw new Error(`Unsupported RPC method: ${method}`);
        }) as EIP1193Provider["request"],
      };

      return custom(provider)({ retryCount: 0 });
    },
  }));
}

export function addressFromPrivateKey(key: string): Address {
  return privateKeyToAccount(normalizeKey(key)).address;
}

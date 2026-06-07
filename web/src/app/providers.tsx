"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WagmiProvider, createConfig, http, injected } from "wagmi";
import { defineChain } from "viem";
import { Toaster } from "sonner";
import { useState } from "react";
import { privateKeyConnector } from "@/lib/private-key-connector";

const chainId = Number(process.env.NEXT_PUBLIC_CHAIN_ID || 143);
const rpcUrl =
  process.env.NEXT_PUBLIC_MONAD_RPC_URL ||
  (chainId === 143 ? "https://rpc.monad.xyz" : "https://testnet-rpc.monad.xyz");

const monad = defineChain({
  id: chainId,
  name: chainId === 143 ? "Monad" : "Monad Testnet",
  nativeCurrency: { name: "MON", symbol: "MON", decimals: 18 },
  rpcUrls: { default: { http: [rpcUrl] } },
});

const devPrivateKey = process.env.NEXT_PUBLIC_DEV_WALLET_PRIVATE_KEY?.trim();
const devWalletAddress = process.env.NEXT_PUBLIC_DEV_WALLET_ADDRESS?.trim();

const connectors = [
  privateKeyConnector({
    envPrivateKey: devPrivateKey,
    expectedAddress: devWalletAddress,
  }),
  injected(),
];

const config = createConfig({
  chains: [monad],
  connectors,
  transports: { [monad.id]: http(rpcUrl) },
  multiInjectedProviderDiscovery: false,
  ssr: true,
});

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster />
      </QueryClientProvider>
    </WagmiProvider>
  );
}

export { config as wagmiConfig };

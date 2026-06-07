"use client";

import { useEffect, useState } from "react";
import { useConnect, useAccount, useDisconnect } from "wagmi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  addressFromPrivateKey,
  clearStoredPrivateKey,
  setStoredPrivateKey,
} from "@/lib/private-key-connector";

export function WalletConnect() {
  const [mounted, setMounted] = useState(false);
  const { address, isConnected, connector } = useAccount();
  const { connect, connectors, isPending } = useConnect();
  const { disconnect } = useDisconnect();
  const [open, setOpen] = useState(false);

  useEffect(() => setMounted(true), []);
  const [privateKey, setPrivateKey] = useState("");
  const [expectedAddress, setExpectedAddress] = useState("");
  const [derivedAddress, setDerivedAddress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pkConnector = connectors.find((c) => c.id === "privateKey");
  const metaMaskConnector = connectors.find((c) => c.id === "injected");

  useEffect(() => {
    if (!pkConnector || isConnected) return;
    void pkConnector.isAuthorized().then((ok) => {
      if (ok) connect({ connector: pkConnector });
    });
  }, [connect, pkConnector, isConnected]);

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_DEV_WALLET_PRIVATE_KEY && pkConnector && !isConnected) {
      connect({ connector: pkConnector });
    }
  }, [connect, pkConnector, isConnected]);

  useEffect(() => {
    if (!privateKey.trim()) {
      setDerivedAddress(null);
      return;
    }
    try {
      setDerivedAddress(addressFromPrivateKey(privateKey));
      setError(null);
    } catch {
      setDerivedAddress(null);
    }
  }, [privateKey]);

  const connectWithKey = () => {
    setError(null);
    try {
      setStoredPrivateKey(privateKey);
      if (expectedAddress && derivedAddress) {
        if (expectedAddress.toLowerCase() !== derivedAddress.toLowerCase()) {
          setError("Private key does not match the wallet address you entered.");
          return;
        }
      }
      if (!pkConnector) {
        setError("Private key connector unavailable.");
        return;
      }
      connect({ connector: pkConnector });
      setOpen(false);
      setPrivateKey("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid private key");
    }
  };

  const handleDisconnect = () => {
    if (connector?.id === "privateKey") {
      clearStoredPrivateKey();
    }
    disconnect();
  };

  if (!mounted) {
    return (
      <div className="relative flex gap-2">
        <Button size="sm" disabled>
          Connect with key
        </Button>
      </div>
    );
  }

  if (address) {
    return (
      <Button variant="outline" size="sm" onClick={handleDisconnect} title={address}>
        {connector?.name === "Private Key" ? "🔑 " : ""}
        {address.slice(0, 6)}…{address.slice(-4)}
      </Button>
    );
  }

  if (open) {
    return (
      <div className="absolute right-0 top-full z-50 mt-2 w-80 rounded-lg border bg-white p-4 shadow-lg">
        <p className="mb-2 text-sm font-medium">Connect with private key</p>
        <p className="mb-3 text-xs text-zinc-500">
          Dev/demo only. Key stays in this browser tab (sessionStorage), not sent to the API.
        </p>
        <Input
          className="mb-2 font-mono text-xs"
          placeholder="Wallet address (optional check)"
          value={expectedAddress}
          onChange={(e) => setExpectedAddress(e.target.value.trim())}
        />
        <Input
          className="mb-2 font-mono text-xs"
          type="password"
          placeholder="Private key (0x…)"
          value={privateKey}
          onChange={(e) => setPrivateKey(e.target.value)}
        />
        {derivedAddress && (
          <p className="mb-2 font-mono text-xs text-emerald-700">Derived: {derivedAddress}</p>
        )}
        {error && <p className="mb-2 text-xs text-red-600">{error}</p>}
        <div className="flex gap-2">
          <Button size="sm" onClick={connectWithKey} disabled={!privateKey.trim() || isPending}>
            Connect
          </Button>
          <Button size="sm" variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex gap-2">
      <Button
        size="sm"
        disabled={isPending}
        onClick={() => setOpen(true)}
      >
        Connect with key
      </Button>
      {metaMaskConnector && (
        <Button
          size="sm"
          variant="outline"
          disabled={isPending}
          onClick={() => connect({ connector: metaMaskConnector })}
        >
          MetaMask
        </Button>
      )}
    </div>
  );
}

export function useWalletAddress() {
  const { address } = useAccount();
  return address ?? null;
}

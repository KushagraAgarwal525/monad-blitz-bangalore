"use client";

import { useState } from "react";
import { useAccount } from "wagmi";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LicensePurchaseButton } from "@/components/license-purchase-button";
import { API_URL } from "@/lib/utils";

export function OnchainActions({
  repoId,
  onChainId,
  ownerWallet,
  visibility,
  onUpdated,
}: {
  repoId: string;
  onChainId: number | null;
  ownerWallet: string;
  visibility: string;
  onUpdated: () => void;
}) {
  const { address, isConnected } = useAccount();
  const [syncing, setSyncing] = useState(false);

  const isOwner =
    address && ownerWallet && address.toLowerCase() === ownerWallet.toLowerCase();

  const syncToChain = async () => {
    setSyncing(true);
    try {
      const r = await fetch(`${API_URL}/repositories/${repoId}/sync-onchain`, { method: "POST" });
      const res = await r.json();
      if (!r.ok) throw new Error(res.detail || "Sync failed");
      toast.success(`Synced on-chain as memoryId ${res.on_chain_id}`);
      onUpdated();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          On-chain (Monad)
          {onChainId ? (
            <Badge variant="success">memoryId {onChainId}</Badge>
          ) : (
            <Badge variant="default">Not synced</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        {isOwner && (
          <Button size="sm" onClick={syncToChain} disabled={syncing || !isConnected}>
            {syncing ? "Syncing…" : onChainId ? "Sync new commits" : "Register on mainnet"}
          </Button>
        )}
        {!isOwner && !onChainId && (
          <p className="text-xs text-zinc-500">
            Connect the owner wallet ({ownerWallet.slice(0, 6)}…) to sync.
          </p>
        )}
        {onChainId && visibility === "LICENSED" && isConnected && !isOwner && (
          <LicensePurchaseButton
            repoId={repoId}
            onChainId={onChainId}
            ownerWallet={ownerWallet}
            onSuccess={onUpdated}
          />
        )}
        {onChainId && visibility !== "LICENSED" && isOwner && (
          <p className="text-xs text-zinc-500">
            Tip: set visibility to LICENSED when creating the repo to enable licensing demos.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

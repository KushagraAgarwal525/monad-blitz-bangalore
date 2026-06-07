"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAccount } from "wagmi";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LicensePurchaseButton } from "@/components/license-purchase-button";
import { API_URL } from "@/lib/utils";

type MarketItem = {
  id: string;
  title: string;
  owner_wallet: string;
  visibility: string;
  on_chain_id: number | null;
  license_price_mem: number | null;
  knowledge_revenue: number;
  fork_count: number;
  score: number;
  provenance_verified: boolean;
  viewer_has_license: boolean;
};

export default function MarketplacePage() {
  const { address, isConnected } = useAccount();
  const [items, setItems] = useState<MarketItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const walletParam = address ? `&wallet=${address}` : "";
    fetch(`${API_URL}/marketplace/repositories?sort=knowledge_revenue${walletParam}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
        const data = await r.json();
        if (!Array.isArray(data)) throw new Error("Unexpected API response");
        return data as MarketItem[];
      })
      .then(setItems)
      .catch((e: Error) => {
        setItems([]);
        setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [address]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Marketplace</h1>
      <p className="text-sm text-zinc-500">
        Browse LICENSED and PUBLIC memory repositories. License prices in MEM; Knowledge Revenue is earned.
      </p>
      {loading && <p className="text-sm text-zinc-500">Loading repositories…</p>}
      {error && (
        <p className="text-sm text-red-500">
          Failed to load marketplace: {error}
        </p>
      )}
      <Card>
        <CardHeader><CardTitle>Knowledge Repositories</CardTitle></CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-zinc-500">
                <th className="pb-2">Title</th>
                <th>License Price</th>
                <th>Knowledge Revenue</th>
                <th>Forks</th>
                <th>Score</th>
                <th>Provenance</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const isOwner =
                  isConnected &&
                  address &&
                  address.toLowerCase() === item.owner_wallet.toLowerCase();
                const canLicense =
                  item.visibility === "LICENSED" &&
                  item.on_chain_id != null &&
                  isConnected &&
                  address &&
                  !isOwner &&
                  !(item.viewer_has_license ?? false);

                return (
                  <tr key={item.id} className="border-b">
                    <td className="py-3">
                      <Link href={`/repositories/${item.id}`} className="font-medium hover:underline">
                        {item.title}
                      </Link>
                      {item.visibility === "LICENSED" && (
                        <Badge variant="default" className="ml-2 text-[10px]">
                          LICENSED
                        </Badge>
                      )}
                    </td>
                    <td>
                      {item.license_price_mem != null ? `${item.license_price_mem.toFixed(0)} MEM` : "—"}
                    </td>
                    <td>{item.knowledge_revenue.toFixed(2)} MEM</td>
                    <td>{item.fork_count}</td>
                    <td>{item.score.toFixed(1)}</td>
                    <td>
                      <Badge variant={item.provenance_verified ? "success" : "destructive"}>
                        {item.provenance_verified ? "Verified" : "Unverified"}
                      </Badge>
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1">
                        {canLicense ? (
                          <LicensePurchaseButton
                            repoId={item.id}
                            onChainId={item.on_chain_id!}
                            ownerWallet={item.owner_wallet}
                            onSuccess={load}
                          />
                        ) : (item.viewer_has_license ?? false) && !isOwner ? (
                          <>
                            <Badge variant="success" className="text-[10px]">
                              Licensed
                            </Badge>
                            <Button asChild size="sm" variant="outline">
                              <Link href={`/repositories/${item.id}`}>View</Link>
                            </Button>
                          </>
                        ) : (
                          <Button asChild size="sm" variant="outline">
                            <Link href={`/repositories/${item.id}`}>View</Link>
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

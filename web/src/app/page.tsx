"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useWalletAddress } from "@/components/wallet-connect";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { API_URL } from "@/lib/utils";

export default function DashboardPage() {
  const address = useWalletAddress();
  const [data, setData] = useState<{ owned_count: number; active_licenses: number; royalty_revenue_mem: number } | null>(null);
  const [repos, setRepos] = useState<Array<{ id: string; title: string | null }>>([]);

  useEffect(() => {
    if (!address) return;
    fetch(`${API_URL}/analytics/dashboard/${address}`).then((r) => r.json()).then(setData);
    fetch(`${API_URL}/repositories?owner=${address}`).then((r) => r.json()).then(setRepos);
  }, [address]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      {!address && <p className="text-zinc-500">Connect wallet to view your repositories.</p>}
      <div className="grid gap-4 md:grid-cols-3">
        {data ? (
          <>
            <Card><CardHeader><CardTitle className="text-sm">Owned Repositories</CardTitle></CardHeader><CardContent><p className="text-3xl font-bold">{data.owned_count}</p></CardContent></Card>
            <Card><CardHeader><CardTitle className="text-sm">Active Licenses</CardTitle></CardHeader><CardContent><p className="text-3xl font-bold">{data.active_licenses}</p></CardContent></Card>
            <Card><CardHeader><CardTitle className="text-sm">Royalty Revenue (MEM)</CardTitle></CardHeader><CardContent><p className="text-3xl font-bold">{data.royalty_revenue_mem}</p></CardContent></Card>
          </>
        ) : (
          <>
            <Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" />
          </>
        )}
      </div>
      <Card>
        <CardHeader><CardTitle>Your Memory Repositories</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {repos.map((r) => (
            <Link key={r.id} href={`/repositories/${r.id}`} className="block rounded-md border p-3 hover:bg-zinc-50">
              {r.title || r.id.slice(0, 8)}
            </Link>
          ))}
          {address && repos.length === 0 && <p className="text-sm text-zinc-500">No repositories yet.</p>}
        </CardContent>
      </Card>
    </div>
  );
}

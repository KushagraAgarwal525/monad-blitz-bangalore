"use client";

import { useEffect, useState } from "react";
import { useWalletAddress } from "@/components/wallet-connect";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { API_URL } from "@/lib/utils";

type Dashboard = {
  license_revenue_mem: number;
  royalty_revenue_mem: number;
  knowledge_revenue_mem: number;
  active_licenses: number;
  owned_count: number;
};

export default function AnalyticsPage() {
  const address = useWalletAddress();
  const [dash, setDash] = useState<Dashboard | null>(null);

  useEffect(() => {
    if (!address) return;
    fetch(`${API_URL}/analytics/dashboard/${address}`).then((r) => r.json()).then(setDash);
  }, [address]);

  const chartData = dash
    ? [
        { name: "License revenue", value: dash.license_revenue_mem },
        { name: "Royalty revenue", value: dash.royalty_revenue_mem },
      ]
    : [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Royalty Analytics</h1>
      {!address && (
        <p className="text-sm text-zinc-500">Connect a wallet to see earnings from repos you own.</p>
      )}
      {dash && (
        <p className="text-sm text-zinc-600">
          Total knowledge revenue earned: <strong>{dash.knowledge_revenue_mem.toFixed(2)} MEM</strong>
          {" · "}
          {dash.owned_count} owned repo{dash.owned_count === 1 ? "" : "s"}
          {" · "}
          {dash.active_licenses} active license{dash.active_licenses === 1 ? "" : "s"} purchased
        </p>
      )}
      <Card>
        <CardHeader><CardTitle>Knowledge Revenue Overview</CardTitle></CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <XAxis dataKey="name" /><YAxis /><Tooltip formatter={(v) => [`${v} MEM`, ""]} />
              <Bar dataKey="value" fill="#18181b" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

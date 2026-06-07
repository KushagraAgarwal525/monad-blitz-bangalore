"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useWalletAddress } from "@/components/wallet-connect";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { API_URL } from "@/lib/utils";

type Proposal = { id: string; proposed_content_json: { text: string }; agent_rationale: string };
type Repo = { id: string; title: string | null; on_chain_id: number | null; visibility?: string; owner_wallet?: string };

function AgentPageContent() {
  const address = useWalletAddress();
  const searchParams = useSearchParams();
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [repos, setRepos] = useState<Repo[]>([]);
  const [repoId, setRepoId] = useState(searchParams.get("repo") || "");
  const [newTitle, setNewTitle] = useState("Agent Demo Memory");
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const loadProposals = useCallback(() => {
    if (!address) return;
    fetch(`${API_URL}/proposals/pending?wallet=${address}`).then((r) => r.json()).then(setProposals);
  }, [address]);

  const loadRepos = useCallback(() => {
    if (!address) return;
    fetch(`${API_URL}/repositories?accessible_to=${address}`)
      .then((r) => r.json())
      .then((list: Repo[]) => {
        setRepos(list);
        const fromUrl = searchParams.get("repo");
        if (fromUrl && list.some((r) => r.id === fromUrl)) {
          setRepoId(fromUrl);
        } else if (!repoId && list[0]) {
          setRepoId(list[0].id);
        }
      });
  }, [address, repoId, searchParams]);

  useEffect(() => {
    loadProposals();
    loadRepos();
  }, [loadProposals, loadRepos]);

  const createRepo = async () => {
    if (!address) return;
    const res = await fetch(`${API_URL}/repositories`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        owner_wallet: address,
        title: newTitle,
        description: "Repository for agent commit demo",
        visibility: "LICENSED",
        content_json: { text: "Genesis commit for agent demo repository.", format: "markdown" },
        source_attribution_json: { source: "agent-demo" },
      }),
    }).then((r) => r.json());
    if (res.id) {
      setRepoId(res.id);
      toast.success(`Created repo ${res.id.slice(0, 8)}…`);
      loadRepos();
    }
  };

  const send = async () => {
    if (!address || !message) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          wallet: address,
          session_id: "demo",
          message,
          repository_ids: repoId ? [repoId] : null,
        }),
      }).then((r) => r.json());
      if (res.access_denied) {
        toast.error("No access to selected repository — purchase a license first");
      }
      setAnswer(res.answer);
      loadProposals();
    } finally {
      setLoading(false);
    }
  };

  const approve = async (proposalId: string) => {
    if (!address || !repoId) {
      toast.error("Select or create a repository first");
      return;
    }
    const res = await fetch(`${API_URL}/proposals/${proposalId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repository_id: repoId, wallet: address }),
    }).then((r) => r.json());
    toast.success(`Commit saved off-chain: ${res.commit_hash?.slice(0, 12)}…`);
    loadProposals();
  };

  const syncOnChain = async () => {
    if (!repoId) return;
    setSyncing(true);
    try {
      const r = await fetch(`${API_URL}/repositories/${repoId}/sync-onchain`, { method: "POST" });
      const res = await r.json();
      if (!r.ok) throw new Error(res.detail || "Sync failed");
      toast.success(`On mainnet as memoryId ${res.on_chain_id}`);
      loadRepos();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const selected = repos.find((r) => r.id === repoId);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Agent Workspace</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input placeholder="New repo title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
            <Button variant="outline" onClick={createRepo} disabled={!address}>Create repo</Button>
          </div>
          <select
            className="w-full rounded-md border p-2 text-sm"
            value={repoId}
            onChange={(e) => setRepoId(e.target.value)}
          >
            <option value="">Select repository…</option>
            {repos.map((r) => {
              const isOwned = r.owner_wallet && address && r.owner_wallet.toLowerCase() === address.toLowerCase();
              const tag = isOwned ? "owned" : r.visibility === "LICENSED" ? "licensed" : "public";
              return (
                <option key={r.id} value={r.id}>
                  {(r.title || r.id.slice(0, 8)) + ` · ${tag}` + (r.on_chain_id ? ` · chain #${r.on_chain_id}` : "")}
                </option>
              );
            })}
          </select>
          {selected && (
            <div className="flex flex-wrap gap-2">
              {address && selected.owner_wallet?.toLowerCase() === address.toLowerCase() && (
                <Button size="sm" variant="default" onClick={syncOnChain} disabled={syncing}>
                  {syncing ? "Syncing…" : selected.on_chain_id ? "Sync new commits" : "Register on mainnet"}
                </Button>
              )}
              <Button size="sm" variant="outline" asChild>
                <a href={`/repositories/${repoId}`}>Open repository →</a>
              </Button>
            </div>
          )}
          <textarea
            className="min-h-[120px] w-full rounded-md border p-3 text-sm"
            placeholder="Ask a research question…"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
          <Button onClick={send} disabled={loading || !address}>{loading ? "Thinking…" : "Send"}</Button>
          {answer && (
            <div className="rounded-md bg-zinc-100 p-4 text-sm">
              <p className="mb-1 font-medium">Answer</p>
              {answer}
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Pending Proposals</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-zinc-500">
            Agent proposes → you approve (off-chain) → Sync to mainnet → Provenance tab → Buy license for revenue.
          </p>
          {proposals.map((p) => (
            <div key={p.id} className="rounded border p-3 text-sm">
              <p className="font-medium">{p.proposed_content_json.text.slice(0, 120)}…</p>
              <p className="text-zinc-500">{p.agent_rationale}</p>
              <div className="mt-2 flex gap-2">
                <Button size="sm" onClick={() => approve(p.id)}>Approve</Button>
              </div>
            </div>
          ))}
          {proposals.length === 0 && <p className="text-zinc-500">No pending proposals.</p>}
        </CardContent>
      </Card>
    </div>
  );
}

export default function AgentPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <AgentPageContent />
    </Suspense>
  );
}

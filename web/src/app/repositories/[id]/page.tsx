"use client";



import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState } from "@xyflow/react";

import "@xyflow/react/dist/style.css";

import { TabsRoot, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { Button } from "@/components/ui/button";

import { Badge } from "@/components/ui/badge";

import { ProvenancePanel } from "@/components/provenance-panel";

import { OnchainActions } from "@/components/onchain-actions";

import { LicensePurchaseButton } from "@/components/license-purchase-button";

import { useWalletAddress } from "@/components/wallet-connect";

import { API_URL } from "@/lib/utils";



type CommitRow = {

  commit_hash: string;

  state_root: string;

  content_text: string | null;

};



type AccessInfo = {

  can_access_content: boolean;

  has_license: boolean;

  visibility: string;

  requires_license: boolean;

};



export default function RepositoryDetailPage({ params }: { params: { id: string } }) {

  const address = useWalletAddress();

  const [repo, setRepo] = useState<Record<string, unknown> | null>(null);

  const [commits, setCommits] = useState<CommitRow[]>([]);

  const [access, setAccess] = useState<AccessInfo | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);

  const [edges, setEdges, onEdgesChange] = useEdgesState([]);



  const load = useCallback(async () => {

    const walletParam = address ? `?wallet=${address}` : "";

    const [r, c, g, a] = await Promise.all([

      fetch(`${API_URL}/repositories/${params.id}`).then((x) => x.json()),

      fetch(`${API_URL}/repositories/${params.id}/commits${walletParam}`).then((x) => x.json()),

      fetch(`${API_URL}/repositories/${params.id}/graph`).then((x) => x.json()),

      fetch(`${API_URL}/repositories/${params.id}/access${walletParam}`).then((x) => x.json()),

    ]);

    setRepo(r);

    setCommits(c);

    setAccess(a);

    setNodes(

      g.nodes.map((n: { id: string; label: string; type: string }, i: number) => ({

        id: n.id,

        data: { label: n.label },

        position: { x: n.type === "repository" ? 100 : 100 + i * 120, y: n.type === "repository" ? 0 : 80 },

        type: n.type === "commit" ? "default" : "input",

      }))

    );

    setEdges(g.edges.map((e: { source: string; target: string }) => ({ id: `${e.source}-${e.target}`, source: e.source, target: e.target })));

  }, [params.id, address, setNodes, setEdges]);



  useEffect(() => {

    load();

  }, [load]);



  if (!repo) return <p>Loading…</p>;



  const visibility = repo.visibility as string;

  const onChainId = (repo.on_chain_id as number | null) ?? null;

  const ownerWallet = repo.owner_wallet as string;

  const isOwner = address && ownerWallet && address.toLowerCase() === ownerWallet.toLowerCase();

  const showLicenseGate = access?.requires_license && !access?.can_access_content;



  return (

    <div className="space-y-6">

      <div>

        <h1 className="text-2xl font-bold">{(repo.display_metadata as { title: string })?.title || "Repository"}</h1>

        <p className="text-sm text-zinc-500">HEAD: {(repo.head_commit_hash as string)?.slice(0, 14)}…</p>

        {typeof repo.on_chain_id === "number" && (

          <p className="text-sm text-emerald-600">On-chain memoryId: {repo.on_chain_id}</p>

        )}

        {visibility === "LICENSED" && (

          <Badge variant="default" className="mt-2 text-[10px]">LICENSED</Badge>

        )}

      </div>



      {showLicenseGate && (

        <Card className="border-amber-200 bg-amber-50">

          <CardContent className="flex flex-wrap items-center gap-3 py-4">

            <p className="text-sm text-amber-900">

              Memory content is restricted. Purchase a license (100 MEM) to read commits and query via Agent.

            </p>

            {onChainId && address && !isOwner && (

              <LicensePurchaseButton

                repoId={params.id}

                onChainId={onChainId}

                ownerWallet={ownerWallet}

                onSuccess={load}

              />

            )}

            {!address && (

              <p className="text-xs text-amber-800">Connect your wallet to purchase a license.</p>

            )}

          </CardContent>

        </Card>

      )}



      {access?.has_license && (

        <Card className="border-emerald-200 bg-emerald-50">

          <CardContent className="flex flex-wrap items-center gap-3 py-4">

            <Badge variant="success">Licensed</Badge>

            <p className="text-sm text-emerald-900">You have access to this repository&apos;s memory.</p>

            <Button asChild size="sm">
              <Link href={`/agent?repo=${params.id}`}>Query in Agent</Link>
            </Button>

          </CardContent>

        </Card>

      )}



      <OnchainActions

        repoId={params.id}

        onChainId={onChainId}

        ownerWallet={ownerWallet}

        visibility={visibility}

        onUpdated={load}

      />

      <TabsRoot defaultValue="commits">

        <TabsList>

          <TabsTrigger value="commits">Commits</TabsTrigger>

          <TabsTrigger value="lineage">Lineage</TabsTrigger>

          <TabsTrigger value="provenance">Provenance</TabsTrigger>

        </TabsList>

        <TabsContent value="commits" className="mt-4">

          <Card>

            <CardHeader><CardTitle>Commit History</CardTitle></CardHeader>

            <CardContent className="space-y-2">

              {commits.map((c) => (

                <div key={c.commit_hash} className="rounded border p-3 text-xs">

                  <div className="font-mono">{c.commit_hash.slice(0, 18)}…</div>

                  <div className="font-mono text-zinc-500">stateRoot: {c.state_root.slice(0, 18)}…</div>

                  {c.content_text ? (

                    <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-800">{c.content_text}</p>

                  ) : showLicenseGate ? (

                    <p className="mt-2 text-zinc-400 italic">Content hidden — license required</p>

                  ) : null}

                </div>

              ))}

            </CardContent>

          </Card>

        </TabsContent>

        <TabsContent value="lineage" className="mt-4 h-[400px]">

          <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} fitView>

            <Background /><Controls /><MiniMap />

          </ReactFlow>

        </TabsContent>

        <TabsContent value="provenance" className="mt-4">

          <ProvenancePanel repoId={params.id} onChainId={onChainId} />

        </TabsContent>

      </TabsRoot>

    </div>

  );

}


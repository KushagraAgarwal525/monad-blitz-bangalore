"use client";

import { useEffect, useState } from "react";
import { useReadContract } from "wagmi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { addresses, memoryRegistryAbi } from "@/lib/contracts/addresses";
import { API_URL } from "@/lib/utils";

type VerifyResponse = {
  verified?: boolean;
  repository_chain?: string;
  structural?: {
    repository_chain_valid?: boolean;
    fork_links_valid?: boolean;
    commit_parent_chain_valid?: boolean;
  };
  cryptographic?: {
    content_hash_match?: boolean;
    embedding_hash_match?: boolean;
    state_root_match?: boolean;
  };
  commits?: Array<{
    content_hash_match?: boolean;
    embedding_hash_match?: boolean;
    state_root_match?: boolean;
  }>;
};

function hashMark(loaded: boolean, match?: boolean) {
  if (!loaded) return "…";
  return match ? "✓" : "✗";
}

export function ProvenancePanel({ repoId, onChainId }: { repoId: string; onChainId: number | null }) {
  const [crypto, setCrypto] = useState<VerifyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { data: structuralValid } = useReadContract({
    address: addresses.memoryRegistry,
    abi: memoryRegistryAbi,
    functionName: "verifyLineage",
    args: onChainId ? [BigInt(onChainId)] : undefined,
    query: { enabled: !!onChainId && addresses.memoryRegistry !== "0x0000000000000000000000000000000000000000" },
  });

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_URL}/repositories/${repoId}/provenance/verify`)
      .then((r) => {
        if (!r.ok) throw new Error(`Verify failed (${r.status})`);
        return r.json();
      })
      .then((data: VerifyResponse) => setCrypto(data))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [repoId]);

  const structural = crypto?.structural;
  const commits = crypto?.commits ?? [];
  const contentOk = commits.length ? commits.every((c) => c.content_hash_match) : crypto?.cryptographic?.content_hash_match;
  const embeddingOk = commits.length ? commits.every((c) => c.embedding_hash_match) : crypto?.cryptographic?.embedding_hash_match;
  const stateRootOk = commits.length ? commits.every((c) => c.state_root_match) : crypto?.cryptographic?.state_root_match;
  const contentLabel = loading ? "Checking…" : error ? "Unavailable" : crypto?.verified ? "Valid" : "Invalid";
  const backendStructOk =
    !!structural?.repository_chain_valid &&
    !!structural?.fork_links_valid &&
    !!structural?.commit_parent_chain_valid;
  const onChainStructOk = structuralValid?.[1];
  const structLabel = !onChainId
    ? "Not synced"
    : onChainStructOk === true
      ? "Valid"
      : onChainStructOk === false && backendStructOk
        ? "Valid (off-chain)"
        : structuralValid === undefined
          ? "Checking…"
          : "Invalid";

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Structural Verification
            <Badge
              variant={
                structLabel === "Valid" || structLabel === "Valid (off-chain)" ? "success" : structLabel === "Checking…" ? "default" : "destructive"
              }
            >
              {structLabel}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-zinc-600">
          <p className="mb-2 font-medium">On-chain · verifyLineage()</p>
          <ul className="list-inside list-disc space-y-1">
            <li>Repository ancestry chain</li>
            <li>Fork relationships</li>
            <li>Commit parent linkage</li>
            <li>Commit existence</li>
          </ul>
          <p className="mt-4 text-xs text-zinc-400">Blockchain verifies structure.</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Content Verification
            <Badge
              variant={
                contentLabel === "Valid" ? "success" : contentLabel === "Checking…" ? "default" : "destructive"
              }
            >
              {contentLabel}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-zinc-600">
          <p className="mb-2 font-medium">Off-chain · GET /provenance/verify</p>
          <ul className="list-inside list-disc space-y-1">
            <li>contentHash: {hashMark(!loading && !error, contentOk)}</li>
            <li>embeddingHash: {hashMark(!loading && !error, embeddingOk)}</li>
            <li>stateRoot: {hashMark(!loading && !error, stateRootOk)}</li>
          </ul>
          <p className="mt-2 font-mono text-xs">{crypto?.repository_chain || ""}</p>
          {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
          {!loading && !error && !crypto?.verified && (
            <p className="mt-2 text-xs text-amber-700">
              Verification failed —{" "}
              {!backendStructOk
                ? "structural lineage check (fork/commit parent chain)."
                : "stored commitments no longer match recomputed hashes."}
            </p>
          )}
          <p className="mt-4 text-xs text-zinc-400">Backend verifies content.</p>
        </CardContent>
      </Card>
    </div>
  );
}

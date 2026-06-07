"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API_URL } from "@/lib/utils";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";

const TOTAL_STEPS = 7;
const EXPLORER_TX = "https://testnet.monadvision.com/tx/";

type StepResult = {
  step: number;
  title: string;
  narrative: string;
  tx_hash?: string;
  tx_hashes?: string[];
  parent?: { knowledge_revenue: number; license_revenue: number; royalty_revenue: number };
  child?: { knowledge_revenue: number; license_revenue: number; royalty_revenue: number };
  links?: Record<string, string>;
  expected?: Record<string, number>;
};

type StepStatus = "pending" | "running" | "done" | "error";

export function DemoFlowPanel() {
  const [running, setRunning] = useState(false);
  const [stepStatuses, setStepStatuses] = useState<StepStatus[]>(
    Array(TOTAL_STEPS).fill("pending")
  );
  const [results, setResults] = useState<StepResult[]>([]);
  const [finalSummary, setFinalSummary] = useState<StepResult | null>(null);

  const runFlow = useCallback(async () => {
    setRunning(true);
    setResults([]);
    setFinalSummary(null);
    setStepStatuses(Array(TOTAL_STEPS).fill("pending"));

    const paint = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    await paint();

    for (let step = 1; step <= TOTAL_STEPS; step++) {
      setStepStatuses((prev) => {
        const next = [...prev];
        next[step - 1] = "running";
        return next;
      });
      await paint();

      try {
        const res = await fetch(`${API_URL}/demo/flow/step/${step}`, { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `Step ${step} failed`);

        setResults((prev) => [...prev, data]);
        if (step === TOTAL_STEPS) setFinalSummary(data);

        setStepStatuses((prev) => {
          const next = [...prev];
          next[step - 1] = "done";
          return next;
        });
      } catch (e) {
        setStepStatuses((prev) => {
          const next = [...prev];
          next[step - 1] = "error";
          return next;
        });
        toast.error(e instanceof Error ? e.message : `Step ${step} failed`);
        break;
      }
    }

    setRunning(false);
  }, []);

  const stepLabels = [
    "Setup parent repo",
    "Sync on-chain",
    "License parent",
    "Fork + royalty rules",
    "Extend fork",
    "License child",
    "Complete",
  ];

  return (
    <Card className="border-amber-200 bg-amber-50/50">
      <CardHeader>
        <CardTitle className="text-base">Hackathon Demo Flow</CardTitle>
        <p className="text-sm text-zinc-600">
          On-chain: license parent → fork → extend → license child → upstream royalty to parent.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={runFlow} disabled={running} size="lg">
          {running ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Running demo…
            </>
          ) : (
            "Simulate Flow"
          )}
        </Button>

        <ol className="space-y-2">
          {stepLabels.map((label, i) => {
            const status = stepStatuses[i];
            const result = results.find((r) => r.step === i + 1);
            return (
              <li key={label} className="flex gap-3 text-sm">
                {status === "done" ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                ) : status === "running" ? (
                  <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-amber-600" />
                ) : status === "error" ? (
                  <Circle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                ) : (
                  <Circle className="mt-0.5 h-4 w-4 shrink-0 text-zinc-300" />
                )}
                <div>
                  <span className="font-medium">{label}</span>
                  {result && (
                    <p className="text-zinc-600">{result.narrative}</p>
                  )}
                  {result?.tx_hash && (
                    <a
                      href={`${EXPLORER_TX}${result.tx_hash}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 hover:underline"
                    >
                      tx {result.tx_hash.slice(0, 10)}…
                    </a>
                  )}
                  {result?.tx_hashes?.map((tx) => (
                    <a
                      key={tx}
                      href={`${EXPLORER_TX}${tx}`}
                      target="_blank"
                      rel="noreferrer"
                      className="mr-2 block text-xs text-blue-600 hover:underline"
                    >
                      tx {tx.slice(0, 10)}…
                    </a>
                  ))}
                  {result?.parent && (
                    <p className="text-xs text-zinc-500">
                      Parent revenue: {result.parent.knowledge_revenue.toFixed(0)} MEM
                      (license {result.parent.license_revenue.toFixed(0)}, royalty{" "}
                      {result.parent.royalty_revenue.toFixed(0)})
                    </p>
                  )}
                  {result?.child && (
                    <p className="text-xs text-zinc-500">
                      Child revenue: {result.child.knowledge_revenue.toFixed(0)} MEM
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>

        {finalSummary?.links && (
          <div className="flex flex-wrap gap-2 border-t pt-4">
            <Button asChild variant="outline" size="sm">
              <Link href={finalSummary.links.marketplace}>Marketplace</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href={finalSummary.links.parent_repo}>Parent repo</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href={finalSummary.links.child_repo}>Child fork</Link>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

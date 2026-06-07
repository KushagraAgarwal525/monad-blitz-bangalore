"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAccount, useWriteContract, useWaitForTransactionReceipt, useReadContract } from "wagmi";
import { parseEther } from "viem";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { addresses, licenseManagerAbi, memoryTokenAbi } from "@/lib/contracts/addresses";
import { API_URL } from "@/lib/utils";

export const PERMANENT_LICENSE_PRICE = parseEther("100");
export const LICENSE_PRICE_MEM = 100;

export function LicensePurchaseButton({
  repoId,
  onChainId,
  ownerWallet,
  onSuccess,
  size = "sm" as const,
  showMint = true,
}: {
  repoId: string;
  onChainId: number;
  ownerWallet: string;
  onSuccess?: () => void;
  size?: "sm" | "default";
  showMint?: boolean;
}) {
  const { address, isConnected } = useAccount();
  const [licenseStep, setLicenseStep] = useState<"idle" | "approve" | "buy">("idle");
  const [apiLicensed, setApiLicensed] = useState(false);
  const [accessChecked, setAccessChecked] = useState(false);
  const recordedRef = useRef<string | null>(null);

  const { writeContract: writeApprove, data: approveHash, isPending: approving } = useWriteContract();
  const { writeContract: writeBuy, data: buyHash, isPending: buying } = useWriteContract();
  const { writeContract: writeFaucet, isPending: fauceting } = useWriteContract();

  const { isSuccess: approveConfirmed } = useWaitForTransactionReceipt({ hash: approveHash });
  const { isSuccess: buyConfirmed } = useWaitForTransactionReceipt({ hash: buyHash });

  const { data: memBalance, refetch: refetchBalance } = useReadContract({
    address: addresses.memoryToken,
    abi: memoryTokenAbi,
    functionName: "balanceOf",
    args: address ? [address] : undefined,
    query: { enabled: !!address },
  });

  const { data: onChainLicensed, refetch: refetchLicense } = useReadContract({
    address: addresses.licenseManager,
    abi: licenseManagerAbi,
    functionName: "hasActiveLicense",
    args: address ? [BigInt(onChainId), address] : undefined,
    query: { enabled: !!address && !!onChainId },
  });

  const checkApiAccess = () => {
    if (!address) {
      setApiLicensed(false);
      setAccessChecked(true);
      return;
    }
    setAccessChecked(false);
    fetch(`${API_URL}/repositories/${repoId}/access?wallet=${address}`)
      .then((r) => r.json())
      .then((d) => setApiLicensed(!!d.has_license))
      .catch(() => setApiLicensed(false))
      .finally(() => setAccessChecked(true));
  };

  useEffect(() => {
    checkApiAccess();
  }, [address, repoId]);

  const isOwner =
    address && ownerWallet && address.toLowerCase() === ownerWallet.toLowerCase();

  const hasLicense = !!onChainLicensed || apiLicensed;

  const mintMem = () => {
    if (!address) return;
    writeFaucet(
      {
        address: addresses.memoryToken,
        abi: memoryTokenAbi,
        functionName: "faucet",
        args: [address, parseEther("1000")],
      },
      {
        onSuccess: () => {
          toast.success("Minted 1000 MEM");
          refetchBalance();
        },
      }
    );
  };

  const startBuyLicense = () => {
    if (!address || !onChainId) return;
    const balance = memBalance ?? 0n;
    if (balance < PERMANENT_LICENSE_PRICE) {
      toast.error("Need 100 MEM — click Mint MEM first");
      return;
    }
    setLicenseStep("approve");
    writeApprove({
      address: addresses.memoryToken,
      abi: memoryTokenAbi,
      functionName: "approve",
      args: [addresses.licenseManager, PERMANENT_LICENSE_PRICE],
    });
  };

  useEffect(() => {
    if (licenseStep === "approve" && approveConfirmed && onChainId && !buyHash) {
      setLicenseStep("buy");
      writeBuy({
        address: addresses.licenseManager,
        abi: licenseManagerAbi,
        functionName: "buyLicense",
        args: [BigInt(onChainId), 0, 0],
      });
    }
  }, [licenseStep, approveConfirmed, onChainId, buyHash, writeBuy]);

  useEffect(() => {
    if (!buyConfirmed || !buyHash || !address) return;
    if (recordedRef.current === buyHash) return;
    recordedRef.current = buyHash;
    setLicenseStep("idle");
    fetch(`${API_URL}/repositories/${repoId}/record-license`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tx_hash: buyHash,
        buyer_wallet: address,
        license_type: "Permanent",
        amount_mem: LICENSE_PRICE_MEM,
      }),
    })
      .then((r) => r.json())
      .then(() => {
        toast.success("Licensed — you can now query this memory in Agent");
        refetchLicense();
        checkApiAccess();
        onSuccess?.();
      })
      .catch(() => toast.error("On-chain license OK but failed to record in API"));
  }, [buyConfirmed, buyHash, address, repoId, onSuccess, refetchLicense]);

  if (!isConnected || isOwner) return null;

  if (!accessChecked && onChainLicensed === undefined) {
    return (
      <Button size={size} variant="outline" disabled>
        Checking…
      </Button>
    );
  }

  if (hasLicense) {
    return (
      <>
        <Badge variant="success" className="text-[10px]">
          Licensed
        </Badge>
        <Button asChild size={size} variant="default">
          <Link href={`/agent?repo=${repoId}`}>Query memory</Link>
        </Button>
        <Button asChild size={size} variant="outline">
          <Link href={`/repositories/${repoId}`}>View content</Link>
        </Button>
      </>
    );
  }

  return (
    <>
      {showMint && (
        <Button size={size} variant="outline" onClick={mintMem} disabled={fauceting}>
          Mint MEM
        </Button>
      )}
      <Button
        size={size}
        onClick={startBuyLicense}
        disabled={approving || buying || licenseStep !== "idle"}
      >
        License ({LICENSE_PRICE_MEM} MEM)
      </Button>
    </>
  );
}

#!/usr/bin/env python3
"""On-chain operations for Memoria demo flow.

Examples:
  # After agent approve (or seed), sync repo to Monad mainnet:
  python scripts/onchain_ops.py sync --repo-id <uuid>

  # Purchase a license (faucets MEM if needed) and record revenue in Postgres:
  python scripts/onchain_ops.py license --repo-id <uuid> --type permanent

  # Mint test MEM to a wallet:
  python scripts/onchain_ops.py faucet --to 0xYourWallet
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.database import async_session, init_db
from app.models import MemoryCommit, MemoryRepository
from app.services.onchain_sync import (
    faucet_mem,
    purchase_license_onchain,
    record_license_purchase,
    sync_repository_onchain,
    _get_account,
    _get_web3,
)


async def cmd_sync(repo_id: str) -> None:
    await init_db()
    rid = uuid.UUID(repo_id)
    async with async_session() as db:
        repo = await db.get(MemoryRepository, rid)
        if not repo:
            raise SystemExit(f"Repository not found: {repo_id}")
        commits = (
            await db.execute(
                select(MemoryCommit)
                .where(MemoryCommit.repository_id == rid)
                .order_by(MemoryCommit.commit_index)
            )
        ).scalars().all()

        result = sync_repository_onchain(repo, list(commits))
        await db.commit()

    print("On-chain sync complete")
    print(f"  repository_id: {result.repository_id}")
    print(f"  on_chain_id:   {result.on_chain_id}")
    print(f"  commits_synced: {result.commits_synced}")
    for h in result.tx_hashes:
        print(f"  tx: {h}")


async def cmd_license(repo_id: str, license_type: str) -> None:
    await init_db()
    rid = uuid.UUID(repo_id)
    async with async_session() as db:
        repo = await db.get(MemoryRepository, rid)
        if not repo:
            raise SystemExit(f"Repository not found: {repo_id}")
        if not repo.on_chain_id:
            raise SystemExit("Repository is not synced on-chain. Run: onchain_ops.py sync --repo-id ...")

        w3 = _get_web3()
        account = _get_account(w3)
        tx_hash, amount = purchase_license_onchain(
            repo.on_chain_id, license_type, w3=w3, account=account
        )
        stats = await record_license_purchase(
            db,
            rid,
            buyer_wallet=account.address,
            license_type=license_type.capitalize(),
            amount_mem=amount,
            tx_hash=tx_hash,
        )

    print("License purchased on-chain and recorded in database")
    print(f"  tx: {tx_hash}")
    print(f"  amount_mem: {amount}")
    print(f"  knowledge_revenue: {stats['knowledge_revenue']}")
    print(f"  memory_score: {stats['score']}")


async def cmd_faucet(to: str, amount: float) -> None:
    w3 = _get_web3()
    account = _get_account(w3)
    tx_hash = faucet_mem(w3, account, to, amount_ether=amount)
    print(f"Faucet tx: {tx_hash}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memoria on-chain demo operations")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="Register repo + commits on MemoryRegistry")
    p_sync.add_argument("--repo-id", required=True, help="PostgreSQL repository UUID")

    p_lic = sub.add_parser("license", help="Buy license with MEM and record revenue")
    p_lic.add_argument("--repo-id", required=True)
    p_lic.add_argument(
        "--type",
        default="permanent",
        choices=["permanent", "monthly", "daily"],
    )

    p_faucet = sub.add_parser("faucet", help="Mint test MEM via MemoryToken.faucet")
    p_faucet.add_argument("--to", required=True, help="Recipient wallet address")
    p_faucet.add_argument("--amount", type=float, default=1000.0, help="MEM amount (ether units)")

    args = parser.parse_args()
    if args.command == "sync":
        asyncio.run(cmd_sync(args.repo_id))
    elif args.command == "license":
        asyncio.run(cmd_license(args.repo_id, args.type))
    elif args.command == "faucet":
        asyncio.run(cmd_faucet(args.to, args.amount))


if __name__ == "__main__":
    main()

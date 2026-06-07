#!/usr/bin/env python3
"""Reassign repository ownership (e.g. after seed_demo used a placeholder wallet)."""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select, update

from app.database import async_session, init_db
from app.models import MemoryCommit, MemoryRepository

DEMO_WALLET = "0x1111111111111111111111111111111111111111"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Set repository owner_wallet")
    parser.add_argument("new_owner", help="New owner address (0x…)")
    parser.add_argument("--repo-id", help="Single repository UUID (default: all demo-owned repos)")
    parser.add_argument(
        "--from-wallet",
        default=DEMO_WALLET,
        help=f"Only repos currently owned by this address (default: {DEMO_WALLET})",
    )
    args = parser.parse_args()

    new_owner = args.new_owner.lower()
    if not new_owner.startswith("0x") or len(new_owner) != 42:
        raise SystemExit("new_owner must be a 42-char hex address starting with 0x")

    await init_db()
    async with async_session() as db:
        if args.repo_id:
            repo = await db.get(MemoryRepository, uuid.UUID(args.repo_id))
            if not repo:
                raise SystemExit(f"Repository not found: {args.repo_id}")
            repos = [repo]
        else:
            repos = (
                await db.execute(
                    select(MemoryRepository).where(
                        MemoryRepository.owner_wallet == args.from_wallet.lower()
                    )
                )
            ).scalars().all()

        if not repos:
            raise SystemExit("No matching repositories found.")

        for repo in repos:
            # Ownership transfer only — creator_wallet is part of the cryptographic
            # commitment and must not change without recomputing the commit chain.
            repo.owner_wallet = new_owner

        await db.commit()

    print(f"Updated {len(repos)} repository/repositories to owner {new_owner}:")
    for r in repos:
        print(f"  {r.id}")


if __name__ == "__main__":
    asyncio.run(main())

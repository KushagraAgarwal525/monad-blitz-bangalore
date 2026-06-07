#!/usr/bin/env python3
"""Restore commit creator_wallet values that still match stored hash commitments.

Use after set_repo_owner incorrectly rewrote creator_wallet without re-hashing.
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
from app.services.commit_service import (
    compute_commit_hash,
    compute_state_root,
    content_hash,
    embedding_hash,
    source_attribution_hash,
)
from app.services.commit_service_ext import CommitService
from app.services.deps import get_qdrant

DEMO_WALLET = "0x1111111111111111111111111111111111111111"


def hashes_match(commit: MemoryCommit, content, embedding, source_attr, creator: str) -> bool:
    ch = content_hash(content)
    eh = embedding_hash(embedding) if embedding else ""
    sah = source_attribution_hash(source_attr)
    if ch != commit.content_hash or eh != commit.embedding_hash or sah != commit.source_attribution_hash:
        return False
    sr = compute_state_root(
        ch,
        eh,
        commit.primary_parent_commit_hash,
        sah,
        creator,
        commit.timestamp,
    )
    if sr != commit.state_root:
        return False
    computed = compute_commit_hash(
        sr,
        commit.primary_parent_commit_hash,
        commit.secondary_parents_canonical,
        creator,
        commit.timestamp,
    )
    return computed == commit.commit_hash


async def main() -> None:
    parser = argparse.ArgumentParser(description="Repair commit creator_wallet fields")
    parser.add_argument("--repo-id", help="Single repository UUID")
    parser.add_argument(
        "--candidate",
        action="append",
        default=[DEMO_WALLET],
        help="Wallet(s) to try (repeatable). Default: demo seed wallet.",
    )
    args = parser.parse_args()

    await init_db()
    cs = CommitService(get_qdrant())

    async with async_session() as db:
        if args.repo_id:
            repo = await db.get(MemoryRepository, uuid.UUID(args.repo_id))
            repos = [repo] if repo else []
        else:
            repos = (await db.execute(select(MemoryRepository))).scalars().all()

        fixed = 0
        for repo in repos:
            commits = (
                await db.execute(
                    select(MemoryCommit)
                    .where(MemoryCommit.repository_id == repo.id)
                    .order_by(MemoryCommit.commit_index)
                )
            ).scalars().all()
            for commit in commits:
                if commit.creator_wallet in args.candidate:
                    continue
                stored = cs.qdrant.get_by_commit_hash(commit.commit_hash)
                if not stored:
                    continue
                content = stored.get("content_json", commit.content_json)
                embedding = stored.get("embedding")
                source_attr = stored.get("source_attribution", commit.source_attribution_json)
                for candidate in args.candidate:
                    creator = candidate.lower()
                    if hashes_match(commit, content, embedding, source_attr, creator):
                        print(
                            f"  {commit.commit_hash[:14]}… creator "
                            f"{commit.creator_wallet[:10]}… -> {creator[:10]}…"
                        )
                        commit.creator_wallet = creator
                        fixed += 1
                        break

        await db.commit()

    print(f"Repaired {fixed} commit(s).")


if __name__ == "__main__":
    asyncio.run(main())

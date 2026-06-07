#!/usr/bin/env python3
"""Seed demo repositories for Memoria hackathon demo."""
import asyncio
import os
import ssl
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

# Shell exports (Neon/Qdrant prod) must beat repo-root .env (localhost).
if any(os.environ.get(k) for k in ("DATABASE_URL", "QDRANT_URL", "QDRANT_API_KEY", "FIREWORKS_API_KEY")):
    os.environ["MEMORIA_SKIP_ENV_FILE"] = "1"

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base


def _engine():
    url = settings.database_url
    kwargs: dict = {"echo": False}
    if "neon.tech" in url or "ssl=require" in url:
        kwargs["connect_args"] = {"ssl": ssl.create_default_context()}
    return create_async_engine(url, **kwargs)


async def init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


from app.models import (
    MemoryRepository,
    MemoryScore,
    RepositoryDisplayMetadata,
    RevenueEvent,
    RoyaltyRule,
    Visibility,
)
from app.services.commit_service_ext import CommitService
from app.services.deps import get_fireworks, get_qdrant
from app.services.memory_score import MemoryScoreService


DEMO_WALLET = "0x1111111111111111111111111111111111111111"


async def seed():
    host = settings.database_url.split("@")[-1].split("/")[0] if "@" in settings.database_url else settings.database_url
    print(f"Seeding against {host} …")
    engine = _engine()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await init_db(engine)
    fw = get_fireworks()
    qd = get_qdrant()
    cs = CommitService(qd)
    score_svc = MemoryScoreService()

    demos = [
        ("Quant Research Memory", "quant", [
            "Market factor analysis: momentum and value premia dominate cross-sectional returns.",
            "Risk model v2: incorporate fat-tail adjustments for crypto-adjacent assets.",
            "Backtest notes: Sharpe 1.4 on 2018-2024 walk-forward.",
        ]),
        ("Biology Research Memory", "biology", [
            "CRISPR-Cas9 overview: guide RNA design constraints and off-target mitigation.",
            "Phase II trial data: 67% response rate in targeted cohort.",
        ]),
        ("Software Engineering Memory", "engineering", [
            "API design: REST + commit-hash verification endpoints.",
            "Test strategy: golden vectors for canonical hashing.",
            "Deploy pipeline: Foundry + Monad testnet 10143.",
            "Performance: Qdrant semantic search p99 under 50ms.",
        ]),
    ]

    async with session_factory() as db:
        repos = []
        for title, category, commits_text in demos:
            repo = MemoryRepository(
                owner_wallet=DEMO_WALLET,
                visibility=Visibility.PUBLIC if category != "quant" else Visibility.LICENSED,
                metadata_uri=f"/metadata/seed-{category}.json",
            )
            db.add(repo)
            await db.flush()
            db.add(
                RepositoryDisplayMetadata(
                    repository_id=repo.id,
                    title=title,
                    description=f"Demo {category} research memory",
                    display_tags=[category, "demo"],
                    category=category,
                )
            )
            for text in commits_text:
                content = {"text": text, "format": "markdown"}
                attr = {"source": "seed", "category": category}
                emb = fw.embed_text(text)
                await cs.create_commit_from_approved(db, repo, content, attr, emb, DEMO_WALLET)
            repos.append(repo)
            await score_svc.recompute(db, repo.id)

        # Fork biology from quant at commit 2
        quant, biology, eng = repos
        biology.parent_memory_id = quant.id
        biology.fork_point_commit_hash = quant.head_commit_hash
        biology.visibility = Visibility.LICENSED

        db.add(
            RoyaltyRule(
                repository_id=biology.id,
                ancestor_repository_id=quant.id,
                percentage_bps=500,
            )
        )
        db.add(
            RevenueEvent(
                repository_id=quant.id,
                event_type="license",
                amount_mem=100.0,
                payer_wallet="0x2222222222222222222222222222222222222222",
            )
        )
        for r in repos:
            ms = await db.get(MemoryScore, r.id)
            if ms:
                ms.knowledge_revenue = ms.license_revenue + ms.royalty_revenue

        await db.commit()
        print("Seeded repositories:")
        for r in repos:
            print(f"  {r.id} HEAD={r.head_commit_hash[:14]}…")


if __name__ == "__main__":
    asyncio.run(seed())

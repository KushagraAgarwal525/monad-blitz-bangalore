"""Hackathon demo flow — license parent → fork → extend → license child → parent royalty."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import (
    ForkRelationship,
    License,
    MemoryCommit,
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
from app.services.onchain_sync import (
    _account_from_key,
    _get_web3,
    fork_repository_onchain,
    purchase_license_onchain,
    record_license_purchase,
    setup_fork_royalties_onchain,
    sync_commit_onchain,
    sync_repository_onchain,
)

DEMO_TAG = "demo-flow"
PARENT_BPS = 500
LICENSE_PRICE = 100.0

PARENT_COMMITS = [
    "Market factor analysis: momentum and value premia dominate cross-sectional returns.",
    "Risk model v2: incorporate fat-tail adjustments for crypto-adjacent assets.",
    "Backtest notes: Sharpe 1.4 on 2018-2024 walk-forward.",
]

EXTENSION_TEXT = (
    "Live portfolio rules: size momentum sleeve at 12% vol target, "
    "cap crypto-adjacent exposure at 15%, rebalance weekly on factor z-scores."
)


@dataclass
class DemoState:
    parent_id: uuid.UUID | None = None
    child_id: uuid.UUID | None = None
    last_step: int = 0


_state = DemoState()


def get_demo_state() -> DemoState:
    return _state


def _require_keys() -> tuple[str, str, str]:
    parent = settings.demo_parent_private_key or settings.private_key
    forker = settings.demo_forker_private_key
    buyer = settings.demo_buyer_private_key
    if not parent:
        raise ValueError("DEMO_PARENT_PRIVATE_KEY or PRIVATE_KEY is required")
    if not forker:
        raise ValueError("DEMO_FORKER_PRIVATE_KEY is required")
    if not buyer:
        raise ValueError("DEMO_BUYER_PRIVATE_KEY is required")
    return parent, forker, buyer


def _wallet(key: str) -> str:
    return _account_from_key(key).address.lower()


async def _delete_repo_dependents(db: AsyncSession, rid: uuid.UUID) -> None:
    await db.execute(delete(License).where(License.repository_id == rid))
    await db.execute(delete(RevenueEvent).where(RevenueEvent.repository_id == rid))
    await db.execute(delete(RoyaltyRule).where(RoyaltyRule.repository_id == rid))
    await db.execute(delete(RoyaltyRule).where(RoyaltyRule.ancestor_repository_id == rid))
    await db.execute(
        delete(ForkRelationship).where(
            (ForkRelationship.parent_repository_id == rid)
            | (ForkRelationship.child_repository_id == rid)
        )
    )
    await db.execute(delete(MemoryScore).where(MemoryScore.repository_id == rid))
    await db.execute(delete(MemoryCommit).where(MemoryCommit.repository_id == rid))
    await db.execute(
        delete(RepositoryDisplayMetadata).where(RepositoryDisplayMetadata.repository_id == rid)
    )


async def _cleanup_demo_repos(db: AsyncSession) -> None:
    meta_rows = (await db.execute(select(RepositoryDisplayMetadata))).scalars().all()
    demo_repo_ids = [m.repository_id for m in meta_rows if DEMO_TAG in (m.display_tags or [])]
    if not demo_repo_ids:
        _state.parent_id = None
        _state.child_id = None
        _state.last_step = 0
        return

    demo_set = set(demo_repo_ids)
    repos = (
        await db.execute(select(MemoryRepository).where(MemoryRepository.id.in_(demo_repo_ids)))
    ).scalars().all()
    child_ids = [r.id for r in repos if r.parent_memory_id in demo_set]
    parent_ids = [r.id for r in repos if r.id not in child_ids]

    for rid in demo_repo_ids:
        await _delete_repo_dependents(db, rid)

    # Clear fork FK on repositories before deleting rows (parent ← child reference).
    await db.execute(
        update(MemoryRepository)
        .where(MemoryRepository.id.in_(demo_repo_ids))
        .values(parent_memory_id=None)
    )

    for rid in child_ids + parent_ids:
        await db.execute(delete(MemoryRepository).where(MemoryRepository.id == rid))

    _state.parent_id = None
    _state.child_id = None
    _state.last_step = 0
    await db.flush()


async def _repo_metrics(db: AsyncSession, repo_id: uuid.UUID) -> dict:
    score = await db.get(MemoryScore, repo_id)
    repo = await db.get(MemoryRepository, repo_id)
    return {
        "repository_id": str(repo_id),
        "on_chain_id": repo.on_chain_id if repo else None,
        "knowledge_revenue": score.knowledge_revenue if score else 0,
        "license_revenue": score.license_revenue if score else 0,
        "royalty_revenue": score.royalty_revenue if score else 0,
        "fork_count": score.fork_count if score else 0,
    }


async def step_setup(db: AsyncSession) -> dict:
    """Step 1: Create demo parent repository with commits."""
    parent_key, forker_key, buyer_key = _require_keys()
    parent_wallet = _wallet(parent_key)

    await _cleanup_demo_repos(db)

    fw = get_fireworks()
    qd = get_qdrant()
    cs = CommitService(qd)
    score_svc = MemoryScoreService()

    parent = MemoryRepository(
        owner_wallet=parent_wallet,
        visibility=Visibility.LICENSED,
        metadata_uri="/metadata/demo-parent.json",
    )
    db.add(parent)
    await db.flush()
    db.add(
        RepositoryDisplayMetadata(
            repository_id=parent.id,
            title="Quant Research Memory (Demo)",
            description="Hackathon demo parent repository — LICENSED at 100 MEM",
            display_tags=[DEMO_TAG, "quant", "demo"],
            category="quant",
        )
    )

    for text in PARENT_COMMITS:
        content = {"text": text, "format": "markdown"}
        attr = {"source": "demo-flow", "category": "quant"}
        emb = fw.embed_text(text)
        await cs.create_commit_from_approved(db, parent, content, attr, emb, parent_wallet)

    await score_svc.recompute(db, parent.id)
    await db.commit()

    _state.parent_id = parent.id
    _state.child_id = None
    _state.last_step = 1

    return {
        "step": 1,
        "title": "Setup parent repository",
        "narrative": "Researcher publishes Quant Research Memory (LICENSED, 100 MEM)",
        "parent": await _repo_metrics(db, parent.id),
        "wallets": {
            "parent": parent_wallet,
            "forker": _wallet(forker_key),
            "buyer": _wallet(buyer_key),
        },
    }


async def step_sync_parent(db: AsyncSession) -> dict:
    """Step 2: Sync parent on-chain."""
    if not _state.parent_id:
        raise ValueError("Run step 1 (setup) first")

    parent_key, _, _ = _require_keys()
    w3 = _get_web3()
    parent_account = _account_from_key(parent_key)

    parent = (
        await db.execute(
            select(MemoryRepository)
            .where(MemoryRepository.id == _state.parent_id)
            .options(selectinload(MemoryRepository.commits))
        )
    ).scalar_one()

    commits = sorted(parent.commits, key=lambda c: c.commit_index)
    result = sync_repository_onchain(parent, commits, w3=w3, account=parent_account)
    await db.commit()

    _state.last_step = 2
    return {
        "step": 2,
        "title": "Sync parent on-chain",
        "narrative": "Parent repository registered on Monad testnet",
        "tx_hashes": result.tx_hashes,
        "on_chain_id": result.on_chain_id,
        "parent": await _repo_metrics(db, parent.id),
    }


async def step_license_parent(db: AsyncSession) -> dict:
    """Step 3: Buyer licenses parent."""
    if not _state.parent_id:
        raise ValueError("Run step 1 first")

    _, _, buyer_key = _require_keys()
    w3 = _get_web3()
    buyer_account = _account_from_key(buyer_key)

    parent = await db.get(MemoryRepository, _state.parent_id)
    if not parent or not parent.on_chain_id:
        raise ValueError("Parent must be synced on-chain (run step 2)")

    tx_hash, price = purchase_license_onchain(
        parent.on_chain_id,
        w3=w3,
        account=buyer_account,
    )
    stats = await record_license_purchase(
        db,
        parent.id,
        buyer_wallet=buyer_account.address,
        license_type="Permanent",
        amount_mem=price,
        tx_hash=tx_hash,
    )

    _state.last_step = 3
    return {
        "step": 3,
        "title": "License parent",
        "narrative": f"Buyer licenses parent → {price:.0f} MEM to original owner",
        "tx_hash": tx_hash,
        "parent": await _repo_metrics(db, parent.id),
        "stats": stats,
    }


async def step_fork(db: AsyncSession) -> dict:
    """Step 4: Off-chain fork + on-chain fork + royalty rules."""
    if not _state.parent_id:
        raise ValueError("Run step 1 first")

    parent_key, forker_key, _ = _require_keys()
    w3 = _get_web3()
    forker_account = _account_from_key(forker_key)
    deployer_account = _account_from_key(settings.private_key or parent_key)

    parent = (
        await db.execute(
            select(MemoryRepository)
            .where(MemoryRepository.id == _state.parent_id)
            .options(selectinload(MemoryRepository.commits))
        )
    ).scalar_one()

    if not parent.on_chain_id:
        raise ValueError("Parent must be synced on-chain (run step 2)")

    parent_commits = sorted(parent.commits, key=lambda c: c.commit_index)
    if len(parent_commits) < 2:
        raise ValueError("Parent needs at least 2 commits to fork")

    fork_point = parent_commits[1]
    forker_wallet = forker_account.address.lower()

    child = MemoryRepository(
        owner_wallet=forker_wallet,
        visibility=Visibility.LICENSED,
        parent_memory_id=parent.id,
        fork_point_commit_hash=fork_point.commit_hash,
        head_commit_hash=fork_point.commit_hash,
        metadata_uri="/metadata/demo-child.json",
    )
    db.add(child)
    await db.flush()
    db.add(
        RepositoryDisplayMetadata(
            repository_id=child.id,
            title="Quant Risk Extension (Demo)",
            description=(
                "Fork of Quant Research Memory at the risk-model commit — "
                "adds deployable portfolio rules on top of upstream factor research"
            ),
            display_tags=[DEMO_TAG, "quant", "demo", "fork"],
            category="quant",
        )
    )

    # Inherited commits remain on parent only (commit_hash is globally unique in DB).

    db.add(
        ForkRelationship(
            parent_repository_id=parent.id,
            child_repository_id=child.id,
            fork_point_commit_hash=fork_point.commit_hash,
        )
    )
    db.add(
        RoyaltyRule(
            repository_id=child.id,
            ancestor_repository_id=parent.id,
            percentage_bps=PARENT_BPS,
        )
    )
    child.head_commit_hash = fork_point.commit_hash
    child.current_commit_id = None
    await db.flush()

    child_memory_id, fork_tx = fork_repository_onchain(
        parent,
        child,
        fork_point,
        fork_point,
        w3=w3,
        account=forker_account,
    )
    royalty_tx = setup_fork_royalties_onchain(
        child_memory_id,
        parent.on_chain_id,
        PARENT_BPS,
        w3=w3,
        account=deployer_account,
    )

    score_svc = MemoryScoreService()
    await score_svc.recompute(db, parent.id)
    await score_svc.recompute(db, child.id)
    await db.commit()

    _state.child_id = child.id
    _state.last_step = 4

    return {
        "step": 4,
        "title": "Fork repository",
        "narrative": "Developer forks Quant Research at risk-model commit → inherits factor lineage",
        "tx_hashes": [fork_tx, royalty_tx],
        "parent": await _repo_metrics(db, parent.id),
        "child": await _repo_metrics(db, child.id),
    }


async def step_extend(db: AsyncSession) -> dict:
    """Step 5: Add extension commit to child."""
    if not _state.child_id:
        raise ValueError("Run step 4 (fork) first")

    _, forker_key, _ = _require_keys()
    w3 = _get_web3()
    forker_account = _account_from_key(forker_key)

    child = await db.get(MemoryRepository, _state.child_id)
    if not child or not child.on_chain_id:
        raise ValueError("Child must exist and be synced on-chain")

    fw = get_fireworks()
    cs = CommitService(get_qdrant())
    content = {"text": EXTENSION_TEXT, "format": "markdown"}
    attr = {"source": "demo-flow", "category": "quant", "extends": "risk-model-v2"}
    emb = fw.embed_text(EXTENSION_TEXT)
    commit = await cs.create_commit_from_approved(
        db, child, content, attr, emb, forker_account.address.lower()
    )

    tx_hash = sync_commit_onchain(
        child.on_chain_id,
        commit,
        w3=w3,
        account=forker_account,
    )

    score_svc = MemoryScoreService()
    await score_svc.recompute(db, child.id)
    await db.commit()

    _state.last_step = 5
    return {
        "step": 5,
        "title": "Extend fork",
        "narrative": "Developer adds live portfolio rules on top of inherited quant memory",
        "tx_hash": tx_hash,
        "child": await _repo_metrics(db, child.id),
    }


async def step_license_child(db: AsyncSession) -> dict:
    """Step 6: Buyer licenses child — parent receives royalty."""
    if not _state.child_id or not _state.parent_id:
        raise ValueError("Run steps 1–5 first")

    _, _, buyer_key = _require_keys()
    w3 = _get_web3()
    buyer_account = _account_from_key(buyer_key)

    child = await db.get(MemoryRepository, _state.child_id)
    parent = await db.get(MemoryRepository, _state.parent_id)
    if not child or not child.on_chain_id:
        raise ValueError("Child must be synced on-chain")

    tx_hash, price = purchase_license_onchain(
        child.on_chain_id,
        w3=w3,
        account=buyer_account,
    )
    stats = await record_license_purchase(
        db,
        child.id,
        buyer_wallet=buyer_account.address,
        license_type="Permanent",
        amount_mem=price,
        tx_hash=tx_hash,
    )

    _state.last_step = 6
    return {
        "step": 6,
        "title": "License child fork",
        "narrative": f"Buyer licenses fork → {PARENT_BPS / 100:.0f}% royalty ({price * PARENT_BPS / 10000:.0f} MEM) to parent owner",
        "tx_hash": tx_hash,
        "parent": await _repo_metrics(db, parent.id),
        "child": await _repo_metrics(db, child.id),
        "stats": stats,
    }


async def step_done(db: AsyncSession) -> dict:
    """Step 7: Summary."""
    if not _state.parent_id or not _state.child_id:
        raise ValueError("Complete steps 1–6 first")

    parent = await _repo_metrics(db, _state.parent_id)
    child = await _repo_metrics(db, _state.child_id)
    _state.last_step = 7

    return {
        "step": 7,
        "title": "Demo complete",
        "narrative": "Full flow: license → fork → extend → license with upstream royalty",
        "parent": parent,
        "child": child,
        "links": {
            "marketplace": "/marketplace",
            "parent_repo": f"/repositories/{_state.parent_id}",
            "child_repo": f"/repositories/{_state.child_id}",
            "parent_lineage": f"/repositories/{_state.parent_id}?tab=lineage",
        },
        "expected": {
            "parent_knowledge_revenue": LICENSE_PRICE + LICENSE_PRICE * PARENT_BPS / 10000,
            "child_knowledge_revenue": LICENSE_PRICE * (10000 - PARENT_BPS) / 10000,
            "parent_fork_count": 1,
        },
    }


STEP_RUNNERS = {
    1: step_setup,
    2: step_sync_parent,
    3: step_license_parent,
    4: step_fork,
    5: step_extend,
    6: step_license_child,
    7: step_done,
}

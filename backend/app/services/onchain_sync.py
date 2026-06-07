"""Sync off-chain repositories/commits to MemoryRegistry on Monad."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eth_account import Account
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3
from web3.contract import Contract

from app.config import settings
from app.models import License, MemoryCommit, MemoryRepository, RevenueEvent, RoyaltyRule, Visibility
from app.services.memory_score import MemoryScoreService

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_OUT = REPO_ROOT / "contracts" / "out"
BUNDLED_ABI_DIR = Path(__file__).resolve().parents[1] / "abi"


def _load_abi(contract_file: str, contract_name: str) -> list[dict[str, Any]]:
    bundled = BUNDLED_ABI_DIR / f"{contract_name}.json"
    if bundled.exists():
        with bundled.open(encoding="utf-8") as f:
            return json.load(f)["abi"]
    path = CONTRACTS_OUT / contract_file / f"{contract_name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"ABI not found for {contract_name}. "
            f"Expected bundled file at {bundled} or forge artifact at {path}."
        )
    with path.open(encoding="utf-8") as f:
        return json.load(f)["abi"]


VISIBILITY_ONCHAIN = {
    Visibility.PRIVATE: 0,
    Visibility.LICENSED: 1,
    Visibility.PUBLIC: 2,
}

LICENSE_TYPE_ONCHAIN = {"permanent": 0, "monthly": 1, "daily": 2}
LICENSE_PRICES_MEM = {"permanent": 100.0, "monthly": 10.0, "daily": 1.0}


@dataclass
class SyncResult:
    repository_id: str
    on_chain_id: int
    commits_synced: int
    tx_hashes: list[str]


def _hex32(value: str) -> bytes:
    raw = value[2:] if value.startswith("0x") else value
    return bytes.fromhex(raw.zfill(64))


def _get_web3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(settings.monad_rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {settings.monad_rpc_url}")
    chain_id = w3.eth.chain_id
    if chain_id != settings.chain_id:
        raise ValueError(f"RPC chain id {chain_id} != CHAIN_ID {settings.chain_id} in .env")
    return w3


def _normalize_key(key: str) -> str:
    if not key:
        raise ValueError("Private key is not set")
    return key if key.startswith("0x") else "0x" + key


def _account_from_key(key: str):
    return Account.from_key(_normalize_key(key))


def _get_account(w3: Web3):
    key = os.environ.get("PRIVATE_KEY") or settings.private_key
    if not key:
        raise ValueError("PRIVATE_KEY is not set in environment or .env")
    return _account_from_key(key)


def _registry_contract(w3: Web3) -> Contract:
    abi = _load_abi("MemoryRegistry.sol", "MemoryRegistry")
    return w3.eth.contract(
        address=Web3.to_checksum_address(settings.memory_registry_address),
        abi=abi,
    )


def _token_contract(w3: Web3) -> Contract:
    abi = _load_abi("MemoryToken.sol", "MemoryToken")
    return w3.eth.contract(
        address=Web3.to_checksum_address(settings.memory_token_address),
        abi=abi,
    )


def _license_contract(w3: Web3) -> Contract:
    abi = _load_abi("LicenseManager.sol", "LicenseManager")
    return w3.eth.contract(
        address=Web3.to_checksum_address(settings.license_manager_address),
        abi=abi,
    )


def _royalty_contract(w3: Web3) -> Contract:
    abi = _load_abi("RoyaltyEngine.sol", "RoyaltyEngine")
    return w3.eth.contract(
        address=Web3.to_checksum_address(settings.royalty_engine_address),
        abi=abi,
    )


def _send(w3: Web3, account, tx: dict) -> str:
    tx = dict(tx)
    tx.setdefault("from", account.address)
    tx.setdefault("chainId", settings.chain_id)
    if "nonce" not in tx:
        tx["nonce"] = w3.eth.get_transaction_count(account.address)
    if "gas" not in tx:
        tx["gas"] = w3.eth.estimate_gas(tx)
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex()


def _send_register_memory(registry, w3: Web3, account, tx: dict) -> tuple[str, int]:
    """Send register/fork tx and resolve new memoryId via nextMemoryId (robust vs event ABI drift)."""
    before = registry.functions.nextMemoryId().call()
    tx_hash = _send(w3, account, tx)
    after = registry.functions.nextMemoryId().call()
    if after <= before:
        raise RuntimeError("nextMemoryId did not increment after transaction")
    return tx_hash, after - 1


def sync_repository_onchain(
    repo: MemoryRepository,
    commits: list[MemoryCommit],
    *,
    w3: Web3 | None = None,
    account=None,
) -> SyncResult:
    """Register repository and push unsynced commits to MemoryRegistry."""
    if repo.parent_memory_id:
        raise NotImplementedError(
            "Fork sync is not implemented yet. Use a linear repository for the demo."
        )

    w3 = w3 or _get_web3()
    account = account or _get_account(w3)
    registry = _registry_contract(w3)

    if repo.owner_wallet.lower() != account.address.lower():
        raise ValueError(
            f"Repo owner {repo.owner_wallet} != signer {account.address}. "
            "Use the owner wallet's PRIVATE_KEY or re-create the repo with your wallet."
        )

    commits = sorted(commits, key=lambda c: c.commit_index)
    if not commits:
        raise ValueError("Repository has no commits to sync")

    tx_hashes: list[str] = []
    memory_id = repo.on_chain_id

    unsynced = [c for c in commits if not c.tx_hash]
    if memory_id is None:
        genesis = commits[0]
        metadata_uri = repo.metadata_uri or f"/metadata/{repo.id}.json"
        visibility = VISIBILITY_ONCHAIN.get(repo.visibility, 0)

        tx = registry.functions.registerRepository(
            _hex32(genesis.commit_hash),
            _hex32(genesis.primary_parent_commit_hash),
            genesis.parent_count,
            _hex32(genesis.secondary_parents_canonical),
            _hex32(genesis.content_hash),
            _hex32(genesis.embedding_hash),
            _hex32(genesis.source_attribution_hash),
            _hex32(genesis.state_root),
            metadata_uri,
            visibility,
        ).build_transaction({"from": account.address})
        tx_hash, memory_id = _send_register_memory(registry, w3, account, tx)
        tx_hashes.append(tx_hash)
        genesis.tx_hash = tx_hash
        repo.on_chain_id = memory_id
        unsynced = [c for c in unsynced if c.id != genesis.id]

    assert memory_id is not None

    for commit in unsynced:
        tx = registry.functions.createCommit(
            memory_id,
            _hex32(commit.commit_hash),
            _hex32(commit.primary_parent_commit_hash),
            commit.parent_count,
            _hex32(commit.secondary_parents_canonical),
            [],
            _hex32(commit.content_hash),
            _hex32(commit.embedding_hash),
            _hex32(commit.source_attribution_hash),
            _hex32(commit.state_root),
        ).build_transaction({"from": account.address})
        tx_hash = _send(w3, account, tx)
        commit.tx_hash = tx_hash
        tx_hashes.append(tx_hash)

    return SyncResult(
        repository_id=str(repo.id),
        on_chain_id=memory_id,
        commits_synced=len(tx_hashes),
        tx_hashes=tx_hashes,
    )


def fork_repository_onchain(
    parent: MemoryRepository,
    child: MemoryRepository,
    fork_point_commit: MemoryCommit,
    initial_commit: MemoryCommit,
    *,
    w3: Web3 | None = None,
    account=None,
) -> tuple[int, str]:
    """Fork on-chain; forker account becomes child owner."""
    if parent.on_chain_id is None:
        raise ValueError("Parent repository is not synced on-chain")

    w3 = w3 or _get_web3()
    account = account or _get_account(w3)
    registry = _registry_contract(w3)

    if child.owner_wallet.lower() != account.address.lower():
        raise ValueError(
            f"Child owner {child.owner_wallet} != signer {account.address}. "
            "Use the forker wallet's private key."
        )

    metadata_uri = child.metadata_uri or f"/metadata/{child.id}.json"
    visibility = VISIBILITY_ONCHAIN.get(child.visibility, 0)

    tx = registry.functions.forkRepository(
        parent.on_chain_id,
        _hex32(fork_point_commit.commit_hash),
        _hex32(initial_commit.commit_hash),
        _hex32(initial_commit.primary_parent_commit_hash),
        initial_commit.parent_count,
        _hex32(initial_commit.secondary_parents_canonical),
        _hex32(initial_commit.content_hash),
        _hex32(initial_commit.embedding_hash),
        _hex32(initial_commit.source_attribution_hash),
        _hex32(initial_commit.state_root),
        metadata_uri,
        visibility,
    ).build_transaction({"from": account.address})
    tx_hash, child_memory_id = _send_register_memory(registry, w3, account, tx)
    child.on_chain_id = child_memory_id
    return child_memory_id, tx_hash


def setup_fork_royalties_onchain(
    child_memory_id: int,
    parent_memory_id: int,
    parent_bps: int = 500,
    *,
    w3: Web3 | None = None,
    account=None,
) -> str:
    """Configure royalty rules on child; must be called by RoyaltyEngine owner (deployer)."""
    w3 = w3 or _get_web3()
    account = account or _get_account(w3)
    royalty = _royalty_contract(w3)

    tx = royalty.functions.inheritRoyaltyRules(
        child_memory_id,
        parent_memory_id,
        parent_bps,
    ).build_transaction({"from": account.address})
    return _send(w3, account, tx)


def sync_commit_onchain(
    memory_id: int,
    commit: MemoryCommit,
    *,
    w3: Web3 | None = None,
    account=None,
) -> str:
    """Push a single unsynced commit to an existing on-chain repository."""
    w3 = w3 or _get_web3()
    account = account or _get_account(w3)
    registry = _registry_contract(w3)

    tx = registry.functions.createCommit(
        memory_id,
        _hex32(commit.commit_hash),
        _hex32(commit.primary_parent_commit_hash),
        commit.parent_count,
        _hex32(commit.secondary_parents_canonical),
        [],
        _hex32(commit.content_hash),
        _hex32(commit.embedding_hash),
        _hex32(commit.source_attribution_hash),
        _hex32(commit.state_root),
    ).build_transaction({"from": account.address})
    tx_hash = _send(w3, account, tx)
    commit.tx_hash = tx_hash
    return tx_hash


def faucet_mem(w3: Web3, account, to: str, amount_ether: float = 1000.0) -> str:
    token = _token_contract(w3)
    amount = w3.to_wei(amount_ether, "ether")
    tx = token.functions.faucet(Web3.to_checksum_address(to), amount).build_transaction(
        {"from": account.address}
    )
    return _send(w3, account, tx)


def purchase_license_onchain(
    memory_id: int,
    license_type: str = "permanent",
    *,
    w3: Web3 | None = None,
    account=None,
) -> tuple[str, float]:
    w3 = w3 or _get_web3()
    account = account or _get_account(w3)
    token = _token_contract(w3)
    license_mgr = _license_contract(w3)

    lic_type = LICENSE_TYPE_ONCHAIN.get(license_type.lower(), 0)
    price_mem = LICENSE_PRICES_MEM.get(license_type.lower(), 100.0)
    price_wei = w3.to_wei(price_mem, "ether")

    balance = token.functions.balanceOf(account.address).call()
    if balance < price_wei:
        faucet_mem(w3, account, account.address, amount_ether=max(price_mem * 2, 1000.0))

    allowance = token.functions.allowance(
        account.address, Web3.to_checksum_address(settings.license_manager_address)
    ).call()
    if allowance < price_wei:
        tx = token.functions.approve(
            Web3.to_checksum_address(settings.license_manager_address),
            price_wei,
        ).build_transaction({"from": account.address})
        _send(w3, account, tx)

    tx = license_mgr.functions.buyLicense(memory_id, lic_type, 0).build_transaction(
        {"from": account.address}
    )
    tx_hash = _send(w3, account, tx)
    return tx_hash, price_mem


async def sync_repository_db(db: AsyncSession, repository_id) -> SyncResult:
    repo = await db.get(MemoryRepository, repository_id)
    if not repo:
        raise ValueError("Repository not found")

    commits = (
        await db.execute(
            select(MemoryCommit)
            .where(MemoryCommit.repository_id == repository_id)
            .order_by(MemoryCommit.commit_index)
        )
    ).scalars().all()

    result = sync_repository_onchain(repo, list(commits))
    await db.commit()
    return result


async def record_license_purchase(
    db: AsyncSession,
    repository_id,
    *,
    buyer_wallet: str,
    license_type: str,
    amount_mem: float,
    tx_hash: str,
) -> dict:
    from datetime import datetime, timezone

    repo = await db.get(MemoryRepository, repository_id)
    if not repo:
        raise ValueError("Repository not found")

    db.add(
        License(
            repository_id=repository_id,
            licensee_wallet=buyer_wallet.lower(),
            license_type=license_type,
            payment_type="MEM",
            start_date=datetime.now(timezone.utc),
            end_date=None,
            price_paid_mem=amount_mem,
            tx_hash=tx_hash,
            active=True,
        )
    )

    rules = (
        await db.execute(
            select(RoyaltyRule).where(RoyaltyRule.repository_id == repository_id)
        )
    ).scalars().all()

    royalty_total = 0.0
    ancestor_ids: list = []
    for rule in rules:
        share = amount_mem * rule.percentage_bps / 10000
        if share <= 0:
            continue
        ancestor = await db.get(MemoryRepository, rule.ancestor_repository_id)
        if not ancestor:
            continue
        royalty_total += share
        ancestor_ids.append(ancestor.id)
        db.add(
            RevenueEvent(
                repository_id=ancestor.id,
                event_type="royalty",
                amount_mem=share,
                payer_wallet=buyer_wallet.lower(),
                recipient_wallet=ancestor.owner_wallet.lower(),
                tx_hash=tx_hash,
            )
        )

    owner_share = amount_mem - royalty_total
    if owner_share > 0:
        db.add(
            RevenueEvent(
                repository_id=repository_id,
                event_type="license",
                amount_mem=owner_share,
                payer_wallet=buyer_wallet.lower(),
                recipient_wallet=repo.owner_wallet.lower(),
                tx_hash=tx_hash,
            )
        )

    score_svc = MemoryScoreService()
    ms = await score_svc.recompute(db, repository_id)
    for ancestor_id in ancestor_ids:
        await score_svc.recompute(db, ancestor_id)

    await db.commit()
    return {
        "knowledge_revenue": ms.knowledge_revenue,
        "license_revenue": ms.license_revenue,
        "royalty_revenue": ms.royalty_revenue,
        "score": ms.score,
        "owner_share_mem": owner_share,
        "royalty_total_mem": royalty_total,
    }

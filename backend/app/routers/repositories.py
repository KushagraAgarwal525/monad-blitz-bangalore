import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import MemoryCommit, MemoryRepository, RepositoryDisplayMetadata, Visibility
from app.services.access_service import can_access_content, has_active_license, list_accessible_repositories
from app.services.deps import get_commit_service, get_provenance_service
from app.services.onchain_sync import record_license_purchase, sync_repository_db
from app.services.provenance_service import ProvenanceService

router = APIRouter(prefix="/repositories", tags=["repositories"])


class RepositoryCreate(BaseModel):
    owner_wallet: str
    title: str
    description: str = ""
    visibility: Visibility = Visibility.PRIVATE
    content_json: dict = Field(default_factory=lambda: {"text": "Genesis memory", "format": "markdown"})
    source_attribution_json: dict = Field(default_factory=dict)


class RepositoryRead(BaseModel):
    id: str
    owner_wallet: str
    head_commit_hash: str | None
    visibility: Visibility
    on_chain_id: int | None
    title: str | None = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[RepositoryRead])
async def list_repositories(
    owner: str | None = None,
    accessible_to: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if accessible_to:
        repos = await list_accessible_repositories(db, accessible_to)
    else:
        q = select(MemoryRepository).options(selectinload(MemoryRepository.display_metadata))
        if owner:
            q = q.where(MemoryRepository.owner_wallet == owner.lower())
        repos = (await db.execute(q)).scalars().all()
    return [
        RepositoryRead(
            id=str(r.id),
            owner_wallet=r.owner_wallet,
            head_commit_hash=r.head_commit_hash,
            visibility=r.visibility,
            on_chain_id=r.on_chain_id,
            title=r.display_metadata.title if r.display_metadata else None,
        )
        for r in repos
    ]


@router.post("", response_model=RepositoryRead)
async def create_repository(body: RepositoryCreate, db: AsyncSession = Depends(get_db)):
    from app.services.deps import get_fireworks, get_qdrant
    from app.services.commit_service_ext import CommitService

    repo = MemoryRepository(
        owner_wallet=body.owner_wallet.lower(),
        visibility=body.visibility,
        metadata_uri=f"/metadata/{{id}}.json",
    )
    db.add(repo)
    await db.flush()

    meta = RepositoryDisplayMetadata(
        repository_id=repo.id,
        title=body.title,
        description=body.description,
    )
    db.add(meta)
    repo.metadata_uri = f"/metadata/{repo.id}.json"

    fw = get_fireworks()
    qd = get_qdrant()
    cs = CommitService(qd)
    text = body.content_json.get("text", "")
    emb = fw.embed_text(text)
    await cs.create_commit_from_approved(
        db, repo, body.content_json, body.source_attribution_json, emb, body.owner_wallet.lower()
    )
    await db.refresh(repo, ["display_metadata"])
    return RepositoryRead(
        id=str(repo.id),
        owner_wallet=repo.owner_wallet,
        head_commit_hash=repo.head_commit_hash,
        visibility=repo.visibility,
        on_chain_id=repo.on_chain_id,
        title=meta.title,
    )


@router.get("/{repo_id}")
async def get_repository(repo_id: str, db: AsyncSession = Depends(get_db)):
    rid = uuid.UUID(repo_id)
    repo = (
        await db.execute(
            select(MemoryRepository)
            .options(selectinload(MemoryRepository.display_metadata))
            .where(MemoryRepository.id == rid)
        )
    ).scalar_one_or_none()
    if not repo:
        raise HTTPException(404, "Not found")
    return {
        "id": str(repo.id),
        "owner_wallet": repo.owner_wallet,
        "head_commit_hash": repo.head_commit_hash,
        "visibility": repo.visibility,
        "on_chain_id": repo.on_chain_id,
        "metadata_uri": repo.metadata_uri,
        "display_metadata": {
            "title": repo.display_metadata.title if repo.display_metadata else "",
            "description": repo.display_metadata.description if repo.display_metadata else "",
        },
    }


@router.get("/{repo_id}/access")
async def check_access(
    repo_id: str,
    wallet: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    repo = await db.get(MemoryRepository, uuid.UUID(repo_id))
    if not repo:
        raise HTTPException(404, "Not found")
    can_access = await can_access_content(db, repo, wallet)
    licensed = bool(wallet and await has_active_license(db, repo.id, wallet))
    return {
        "can_access_content": can_access,
        "has_license": licensed,
        "visibility": repo.visibility.value,
        "requires_license": repo.visibility == Visibility.LICENSED,
    }


@router.get("/{repo_id}/commits")
async def list_commits(
    repo_id: str,
    wallet: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    rid = uuid.UUID(repo_id)
    repo = await db.get(MemoryRepository, rid)
    if not repo:
        raise HTTPException(404, "Not found")

    can_access = await can_access_content(db, repo, wallet)
    commits = (
        await db.execute(
            select(MemoryCommit)
            .where(MemoryCommit.repository_id == rid)
            .order_by(MemoryCommit.commit_index)
        )
    ).scalars().all()
    return [
        {
            "commit_hash": c.commit_hash,
            "primary_parent_commit_hash": c.primary_parent_commit_hash,
            "parent_count": c.parent_count,
            "content_hash": c.content_hash,
            "state_root": c.state_root,
            "timestamp": c.timestamp,
            "creator_wallet": c.creator_wallet,
            "content_text": c.content_json.get("text") if can_access else None,
        }
        for c in commits
    ]


@router.get("/{repo_id}/provenance/verify")
async def verify_provenance(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    prov: ProvenanceService = Depends(get_provenance_service),
):
    return await prov.verify_full(db, repo_id)


@router.post("/{repo_id}/sync-onchain")
async def sync_onchain(repo_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await sync_repository_db(db, uuid.UUID(repo_id))
    except FileNotFoundError as e:
        raise HTTPException(500, str(e)) from e
    except (ValueError, NotImplementedError, ConnectionError, RuntimeError) as e:
        raise HTTPException(400, str(e)) from e
    return {
        "repository_id": result.repository_id,
        "on_chain_id": result.on_chain_id,
        "commits_synced": result.commits_synced,
        "tx_hashes": result.tx_hashes,
    }


class RecordLicenseBody(BaseModel):
    tx_hash: str
    buyer_wallet: str
    license_type: str = "Permanent"
    amount_mem: float = 100.0


@router.post("/{repo_id}/record-license")
async def record_license(
    repo_id: str,
    body: RecordLicenseBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        stats = await record_license_purchase(
            db,
            uuid.UUID(repo_id),
            buyer_wallet=body.buyer_wallet,
            license_type=body.license_type,
            amount_mem=body.amount_mem,
            tx_hash=body.tx_hash,
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return stats


@router.get("/{repo_id}/commits/{commit_hash}/verify")
async def verify_commit(
    repo_id: str,
    commit_hash: str,
    db: AsyncSession = Depends(get_db),
    cs=Depends(get_commit_service),
):
    commit = (
        await db.execute(
            select(MemoryCommit).where(
                MemoryCommit.repository_id == uuid.UUID(repo_id),
                MemoryCommit.commit_hash == commit_hash,
            )
        )
    ).scalar_one_or_none()
    if not commit:
        raise HTTPException(404, "Commit not found")
    return await cs.verify_single_commit(db, commit)


@router.get("/{repo_id}/graph")
async def get_graph(repo_id: str, db: AsyncSession = Depends(get_db)):
    commits = (
        await db.execute(
            select(MemoryCommit)
            .where(MemoryCommit.repository_id == uuid.UUID(repo_id))
            .order_by(MemoryCommit.commit_index)
        )
    ).scalars().all()
    nodes = [{"id": str(repo_id), "type": "repository", "label": "Repository"}]
    edges = []
    for c in commits:
        nid = c.commit_hash[:10]
        nodes.append({"id": nid, "type": "commit", "label": nid})
        if c.primary_parent_commit_hash != "0x" + "00" * 32:
            edges.append({"source": c.primary_parent_commit_hash[:10], "target": nid})
        else:
            edges.append({"source": str(repo_id), "target": nid})
    return {"nodes": nodes, "edges": edges}

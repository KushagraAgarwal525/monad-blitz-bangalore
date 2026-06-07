from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import License, MemoryRepository, MemoryScore, Visibility
from app.services.provenance_service import ProvenanceService
from app.services.deps import get_provenance_service

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/repositories")
async def marketplace_repositories(
    sort: str = "knowledge_revenue",
    wallet: str | None = None,
    db: AsyncSession = Depends(get_db),
    prov: ProvenanceService = Depends(get_provenance_service),
):
    licensed_ids: set = set()
    if wallet:
        licensed_ids = set(
            (
                await db.execute(
                    select(License.repository_id).where(
                        License.licensee_wallet == wallet.lower(),
                        License.active == True,
                    )
                )
            ).scalars().all()
        )

    repos = (
        await db.execute(
            select(MemoryRepository)
            .options(selectinload(MemoryRepository.display_metadata))
            .where(MemoryRepository.visibility.in_([Visibility.LICENSED, Visibility.PUBLIC]))
        )
    ).scalars().all()

    items = []
    for r in repos:
        score = await db.get(MemoryScore, r.id)
        proof = await prov.verify_full(db, r.id)
        items.append(
            {
                "id": str(r.id),
                "title": r.display_metadata.title if r.display_metadata else "Untitled",
                "owner_wallet": r.owner_wallet,
                "visibility": r.visibility.value,
                "on_chain_id": r.on_chain_id,
                "license_price_mem": 100.0 if r.visibility == Visibility.LICENSED else None,
                "knowledge_revenue": score.knowledge_revenue if score else 0,
                "score": score.score if score else 0,
                "fork_count": score.fork_count if score else 0,
                "provenance_verified": proof.get("verified", False),
                "viewer_has_license": r.id in licensed_ids,
            }
        )

    if sort == "knowledge_revenue":
        items.sort(key=lambda x: x["knowledge_revenue"], reverse=True)
    elif sort == "score":
        items.sort(key=lambda x: x["score"], reverse=True)
    return items

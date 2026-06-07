from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import License, MemoryRepository, MemoryScore, RevenueEvent

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard/{wallet}")
async def dashboard(wallet: str, db: AsyncSession = Depends(get_db)):
    wallet = wallet.lower()
    owned = (
        await db.execute(select(MemoryRepository).where(MemoryRepository.owner_wallet == wallet))
    ).scalars().all()
    licenses = (
        await db.execute(select(License).where(License.licensee_wallet == wallet, License.active == True))
    ).scalars().all()
    license_revenue = (
        await db.execute(
            select(func.coalesce(func.sum(RevenueEvent.amount_mem), 0)).where(
                RevenueEvent.recipient_wallet == wallet,
                RevenueEvent.event_type == "license",
            )
        )
    ).scalar()
    royalty = (
        await db.execute(
            select(func.coalesce(func.sum(RevenueEvent.amount_mem), 0)).where(
                RevenueEvent.recipient_wallet == wallet,
                RevenueEvent.event_type == "royalty",
            )
        )
    ).scalar()
    return {
        "owned_count": len(owned),
        "active_licenses": len(licenses),
        "licensed_repository_ids": [str(l.repository_id) for l in licenses],
        "license_revenue_mem": license_revenue or 0,
        "royalty_revenue_mem": royalty or 0,
        "knowledge_revenue_mem": (license_revenue or 0) + (royalty or 0),
    }


@router.get("/repositories/{repo_id}/score")
async def repo_score(repo_id: str, db: AsyncSession = Depends(get_db)):
    score = await db.get(MemoryScore, repo_id)
    if not score:
        return {"score": 0, "knowledge_revenue": 0}
    return {
        "score": score.score,
        "knowledge_revenue": score.knowledge_revenue,
        "license_revenue": score.license_revenue,
        "royalty_revenue": score.royalty_revenue,
        "fork_count": score.fork_count,
        "breakdown_json": score.breakdown_json,
    }


@router.get("/repositories/{repo_id}/revenue")
async def repo_revenue(repo_id: str, db: AsyncSession = Depends(get_db)):
    events = (
        await db.execute(select(RevenueEvent).where(RevenueEvent.repository_id == repo_id))
    ).scalars().all()
    return [
        {
            "event_type": e.event_type,
            "amount_mem": e.amount_mem,
            "payer_wallet": e.payer_wallet,
            "tx_hash": e.tx_hash,
        }
        for e in events
    ]

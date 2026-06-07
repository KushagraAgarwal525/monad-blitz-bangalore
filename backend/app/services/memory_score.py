import math
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ForkRelationship, MemoryRepository, MemoryScore, MemoryUsageEvent, RevenueEvent


class MemoryScoreService:
    WEIGHTS = {"license": 0.3, "royalty": 0.25, "forks": 0.15, "users": 0.1, "retrieval": 0.15, "age": 0.05}

    async def recompute(self, db: AsyncSession, repository_id) -> MemoryScore:
        repo = await db.get(MemoryRepository, repository_id)
        if not repo:
            raise ValueError("Repository not found")

        license_rev = (
            await db.execute(
                select(func.coalesce(func.sum(RevenueEvent.amount_mem), 0)).where(
                    RevenueEvent.repository_id == repository_id,
                    RevenueEvent.event_type == "license",
                )
            )
        ).scalar() or 0

        royalty_rev = (
            await db.execute(
                select(func.coalesce(func.sum(RevenueEvent.amount_mem), 0)).where(
                    RevenueEvent.repository_id == repository_id,
                    RevenueEvent.event_type == "royalty",
                )
            )
        ).scalar() or 0

        fork_count = (
            await db.execute(
                select(func.count()).where(ForkRelationship.parent_repository_id == repository_id)
            )
        ).scalar() or 0

        retrieval_volume = (
            await db.execute(
                select(func.count()).where(
                    MemoryUsageEvent.repository_id == repository_id,
                    MemoryUsageEvent.event_type == "retrieve",
                )
            )
        ).scalar() or 0

        age_days = max(0, (datetime.now(timezone.utc) - repo.created_at.replace(tzinfo=timezone.utc)).days)

        score = (
            self.WEIGHTS["license"] * math.log1p(license_rev)
            + self.WEIGHTS["royalty"] * math.log1p(royalty_rev)
            + self.WEIGHTS["forks"] * math.sqrt(fork_count)
            + self.WEIGHTS["retrieval"] * math.log1p(retrieval_volume)
            + self.WEIGHTS["age"] * math.log1p(age_days)
        )

        knowledge_revenue = license_rev + royalty_rev

        existing = await db.get(MemoryScore, repository_id)
        if existing:
            existing.score = score
            existing.license_revenue = license_rev
            existing.royalty_revenue = royalty_rev
            existing.knowledge_revenue = knowledge_revenue
            existing.fork_count = fork_count
            existing.retrieval_volume = retrieval_volume
            existing.memory_age_days = age_days
            ms = existing
        else:
            ms = MemoryScore(
                repository_id=repository_id,
                score=score,
                license_revenue=license_rev,
                royalty_revenue=royalty_rev,
                knowledge_revenue=knowledge_revenue,
                fork_count=fork_count,
                retrieval_volume=retrieval_volume,
                memory_age_days=age_days,
            )
            db.add(ms)
        await db.flush()
        return ms

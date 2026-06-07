from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import License, MemoryRepository, Visibility


async def can_access_content(
    db: AsyncSession,
    repo: MemoryRepository,
    wallet: str | None,
) -> bool:
    if repo.visibility == Visibility.PUBLIC:
        return True
    if not wallet:
        return False
    wallet = wallet.lower()
    if repo.owner_wallet == wallet:
        return True
    if repo.visibility == Visibility.LICENSED:
        lic = (
            await db.execute(
                select(License).where(
                    License.repository_id == repo.id,
                    License.licensee_wallet == wallet,
                    License.active == True,
                )
            )
        ).scalar_one_or_none()
        return lic is not None
    return False


async def has_active_license(
    db: AsyncSession,
    repo_id,
    wallet: str,
) -> bool:
    lic = (
        await db.execute(
            select(License).where(
                License.repository_id == repo_id,
                License.licensee_wallet == wallet.lower(),
                License.active == True,
            )
        )
    ).scalar_one_or_none()
    return lic is not None


async def list_accessible_repositories(
    db: AsyncSession,
    wallet: str,
) -> list[MemoryRepository]:
    wallet = wallet.lower()
    licensed_ids = (
        await db.execute(
            select(License.repository_id).where(
                License.licensee_wallet == wallet,
                License.active == True,
            )
        )
    ).scalars().all()

    conditions = [
        MemoryRepository.owner_wallet == wallet,
        MemoryRepository.visibility == Visibility.PUBLIC,
    ]
    if licensed_ids:
        conditions.append(MemoryRepository.id.in_(licensed_ids))
    repos = (
        await db.execute(
            select(MemoryRepository)
            .options(selectinload(MemoryRepository.display_metadata))
            .where(or_(*conditions))
        )
    ).scalars().all()
    return list(repos)

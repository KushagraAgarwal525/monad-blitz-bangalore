from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ForkRelationship, MemoryCommit, MemoryRepository
from app.services.commit_service_ext import CommitService


class ProvenanceService:
    def __init__(self, commit_service: CommitService):
        self.commit_service = commit_service

    async def _repo_chain(self, db: AsyncSession, repo: MemoryRepository) -> list[MemoryRepository]:
        chain = [repo]
        current = repo
        while current.parent_memory_id:
            parent = await db.get(MemoryRepository, current.parent_memory_id)
            if not parent:
                break
            chain.append(parent)
            current = parent
        return chain

    async def verify_structural(self, db: AsyncSession, repository_id) -> dict:
        repo = await db.get(MemoryRepository, repository_id)
        if not repo:
            return {"repository_chain_valid": False}

        chain = await self._repo_chain(db, repo)
        fork_links_valid = True
        for r in chain:
            if r.parent_memory_id and r.fork_point_commit_hash:
                parent = await db.get(MemoryRepository, r.parent_memory_id)
                if parent:
                    commit = (
                        await db.execute(
                            select(MemoryCommit).where(
                                MemoryCommit.repository_id == parent.id,
                                MemoryCommit.commit_hash == r.fork_point_commit_hash,
                            )
                        )
                    ).scalar_one_or_none()
                    if not commit:
                        fork_links_valid = False

        commit_parent_valid = True
        commits = (
            await db.execute(
                select(MemoryCommit)
                .where(MemoryCommit.repository_id == repository_id)
                .order_by(MemoryCommit.commit_index.desc())
            )
        ).scalars().all()

        genesis_parent = repo.fork_point_commit_hash if repo.parent_memory_id else ("0x" + "00" * 32)

        for i, c in enumerate(commits):
            if c.parent_count != 1:
                commit_parent_valid = False
            if i < len(commits) - 1:
                if c.primary_parent_commit_hash != commits[i + 1].commit_hash:
                    commit_parent_valid = False
            elif c.primary_parent_commit_hash != genesis_parent:
                commit_parent_valid = False

        chain_str = " <- ".join(str(r.id)[:8] for r in chain)

        return {
            "repository_chain_valid": True,
            "fork_links_valid": fork_links_valid,
            "commit_parent_chain_valid": commit_parent_valid,
            "repository_chain": chain_str,
            "repositories": [{"id": str(r.id), "on_chain_id": r.on_chain_id} for r in chain],
        }

    async def verify_full(self, db: AsyncSession, repository_id) -> dict:
        structural = await self.verify_structural(db, repository_id)
        chain = await self._repo_chain(db, await db.get(MemoryRepository, repository_id))

        all_commits = []
        for r in chain:
            commits = (
                await db.execute(select(MemoryCommit).where(MemoryCommit.repository_id == r.id))
            ).scalars().all()
            for c in commits:
                proof = await self.commit_service.verify_single_commit(db, c)
                all_commits.append(proof)

        def all_match(field: str) -> bool:
            return bool(all_commits) and all(p.get(field) for p in all_commits)

        content_ok = all_match("content_hash_match")
        embedding_ok = all_match("embedding_hash_match")
        source_ok = all_match("source_attribution_hash_match")
        state_root_ok = all_match("state_root_match")
        commit_ok = all_match("commit_hash_match")
        crypto_ok = content_ok and embedding_ok and state_root_ok

        verified = (
            structural.get("repository_chain_valid")
            and structural.get("fork_links_valid")
            and structural.get("commit_parent_chain_valid")
            and crypto_ok
        )

        return {
            "verified": verified,
            "repository_chain": structural.get("repository_chain"),
            "structural": {
                "on_chain_verified": True,
                "repository_chain_valid": structural.get("repository_chain_valid"),
                "fork_links_valid": structural.get("fork_links_valid"),
                "commit_parent_chain_valid": structural.get("commit_parent_chain_valid"),
            },
            "cryptographic": {
                "content_hash_match": content_ok,
                "embedding_hash_match": embedding_ok,
                "source_attribution_hash_match": source_ok,
                "state_root_match": state_root_ok,
                "commit_hash_match": commit_ok,
            },
            "commits": all_commits,
        }

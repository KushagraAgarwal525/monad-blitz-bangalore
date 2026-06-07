import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemoryCommit, MemoryRepository
from app.services.commit_service import (
    compute_commit_payload,
    content_hash,
    embedding_hash,
    source_attribution_hash,
)
from app.services.qdrant_service import QdrantService


class CommitService:
    def __init__(self, qdrant: QdrantService):
        self.qdrant = qdrant

    async def create_commit_from_approved(
        self,
        db: AsyncSession,
        repository: MemoryRepository,
        content_json: dict,
        source_attribution_json: dict,
        embedding: list[float],
        creator_wallet: str,
    ) -> MemoryCommit:
        primary_parent = repository.head_commit_hash or ("0x" + "00" * 32)
        timestamp = int(datetime.now(timezone.utc).timestamp())

        payload = compute_commit_payload(
            content_json,
            embedding,
            source_attribution_json,
            primary_parent,
            [],
            creator_wallet,
            timestamp,
        )

        commit_index = len(
            (await db.execute(
                select(MemoryCommit).where(MemoryCommit.repository_id == repository.id)
            )).scalars().all()
        )

        commit = MemoryCommit(
            id=uuid.uuid4(),
            repository_id=repository.id,
            commit_hash=payload["commit_hash"],
            primary_parent_commit_hash=primary_parent,
            parent_count=1,
            secondary_parent_commit_hashes=[],
            secondary_parents_canonical=payload["secondary_parents_canonical"],
            content_hash=payload["content_hash"],
            embedding_hash=payload["embedding_hash"],
            source_attribution_hash=payload["source_attribution_hash"],
            state_root=payload["state_root"],
            content_json=content_json,
            source_attribution_json=source_attribution_json,
            creator_wallet=creator_wallet.lower(),
            timestamp=timestamp,
            commit_index=commit_index,
        )

        self.qdrant.insert_memory_entry(
            commit.commit_hash,
            str(repository.id),
            content_json,
            embedding,
            source_attribution_json,
            timestamp,
        )

        db.add(commit)
        repository.head_commit_hash = commit.commit_hash
        repository.current_commit_id = commit.id
        await db.flush()
        return commit

    async def verify_single_commit(self, db: AsyncSession, commit: MemoryCommit) -> dict:
        stored = self.qdrant.get_by_commit_hash(commit.commit_hash)
        if not stored:
            return {
                "commit_hash": commit.commit_hash,
                "content_hash_match": False,
                "embedding_hash_match": False,
                "state_root_match": False,
            }

        content = stored.get("content_json", commit.content_json)
        embedding = stored.get("embedding")
        source_attr = stored.get("source_attribution", commit.source_attribution_json)

        ch = content_hash(content)
        eh = embedding_hash(embedding) if embedding else ""
        sah = source_attribution_hash(source_attr)

        from app.services.commit_service import compute_state_root, compute_commit_hash

        parent = commit.primary_parent_commit_hash
        sr = compute_state_root(ch, eh, parent, sah, commit.creator_wallet, commit.timestamp)
        sec = commit.secondary_parents_canonical
        computed_commit = compute_commit_hash(sr, parent, sec, commit.creator_wallet, commit.timestamp)

        return {
            "commit_hash": commit.commit_hash,
            "content_hash_match": ch == commit.content_hash,
            "embedding_hash_match": eh == commit.embedding_hash,
            "source_attribution_hash_match": sah == commit.source_attribution_hash,
            "state_root_match": sr == commit.state_root,
            "commit_hash_match": computed_commit == commit.commit_hash,
        }

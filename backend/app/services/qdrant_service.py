from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import settings


class QdrantService:
    COLLECTION = "memory_commits"

    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
        self._ensure_collection()

    def _ensure_collection(self):
        collections = [c.name for c in self.client.get_collections().collections]
        if self.COLLECTION not in collections:
            self.client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=models.VectorParams(
                    size=settings.fireworks_embedding_dimensions,
                    distance=models.Distance.COSINE,
                ),
            )

    def insert_memory_entry(
        self,
        commit_hash: str,
        repository_id: str,
        content_json: dict,
        embedding: list[float],
        source_attribution: dict,
        timestamp: int,
    ):
        point_id = commit_hash.replace("0x", "")[:32]
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "commit_hash": commit_hash,
                        "repository_id": repository_id,
                        "content_json": content_json,
                        "source_attribution": source_attribution,
                        "timestamp": timestamp,
                        "embedding": embedding,
                    },
                )
            ],
        )

    def semantic_search(
        self,
        query_embedding: list[float],
        repository_ids: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        query_filter = None
        if repository_ids:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="repository_id",
                        match=models.MatchAny(any=repository_ids),
                    )
                ]
            )
        results = self.client.query_points(
            collection_name=self.COLLECTION,
            query=query_embedding,
            query_filter=query_filter,
            limit=limit,
        )
        return [{"score": r.score, **r.payload} for r in results.points]

    def get_by_commit_hash(self, commit_hash: str) -> dict | None:
        point_id = commit_hash.replace("0x", "")[:32]
        try:
            points = self.client.retrieve(collection_name=self.COLLECTION, ids=[point_id])
            if points:
                return points[0].payload
        except Exception:
            pass
        return None

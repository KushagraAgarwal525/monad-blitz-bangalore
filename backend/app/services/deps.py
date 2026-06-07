from functools import lru_cache

from app.services.agent import AgentService
from app.services.commit_service_ext import CommitService
from app.services.fireworks_client import FireworksClient
from app.services.provenance_service import ProvenanceService
from app.services.qdrant_service import QdrantService


@lru_cache
def get_qdrant() -> QdrantService:
    return QdrantService()


@lru_cache
def get_fireworks() -> FireworksClient:
    return FireworksClient()


def get_commit_service() -> CommitService:
    return CommitService(get_qdrant())


def get_provenance_service() -> ProvenanceService:
    return ProvenanceService(get_commit_service())


def get_agent_service() -> AgentService:
    return AgentService(get_fireworks(), get_qdrant())

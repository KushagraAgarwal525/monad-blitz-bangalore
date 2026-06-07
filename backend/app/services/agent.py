import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    CommitProposal,
    ForkRelationship,
    MemoryCommit,
    MemoryRepository,
    MemoryUsageEvent,
    ProposalStatus,
    RepositoryDisplayMetadata,
    RoyaltyRule,
    Visibility,
)
from app.services.access_service import can_access_content
from app.services.commit_service_ext import CommitService
from app.services.fireworks_client import FireworksClient
from app.services.memory_score import MemoryScoreService
from app.services.provenance_service import ProvenanceService
from app.services.qdrant_service import QdrantService


class AgentService:
    SYSTEM = (
        "You are a research agent for Memoria. Answer using retrieved memory context when available. "
        "Always respond with a JSON object with exactly these fields:\n"
        '- "answer" (string): your reply to the user\n'
        '- "propose_memory" (boolean): true when the user asks to remember/store a fact or you identify new storable knowledge\n'
        '- "proposed_content" (string): the exact fact or knowledge to persist; required when propose_memory is true\n'
        '- "rationale" (string): why this should be stored; required when propose_memory is true\n\n'
        "When the user says remember, store, or save a fact, set propose_memory=true, "
        "put the fact verbatim in proposed_content, and explain in rationale."
    )

    def __init__(
        self,
        fireworks: FireworksClient,
        qdrant: QdrantService,
    ):
        self.fireworks = fireworks
        self.qdrant = qdrant

    async def _filter_accessible_repo_ids(
        self,
        db: AsyncSession,
        wallet: str,
        repository_ids: list[str] | None,
    ) -> list[str] | None:
        if not repository_ids:
            return None
        allowed: list[str] = []
        for rid in repository_ids:
            repo = await db.get(MemoryRepository, uuid.UUID(rid))
            if repo and await can_access_content(db, repo, wallet):
                allowed.append(rid)
        return allowed or None

    async def chat(
        self,
        db: AsyncSession,
        wallet: str,
        session_id: str,
        message: str,
        repository_ids: list[str] | None = None,
    ) -> dict:
        accessible_ids = await self._filter_accessible_repo_ids(db, wallet, repository_ids)
        embedding = self.fireworks.embed_text(message)
        results = self.qdrant.semantic_search(embedding, accessible_ids, limit=5)

        context = "\n".join(
            f"- {r.get('content_json', {}).get('text', '')[:200]}" for r in results
        )
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {message}"},
        ]
        raw = self.fireworks.chat_completion(messages, json_mode=True)
        try:
            parsed = json.loads(raw)
            answer = parsed.get("answer") or parsed.get("response") or raw
            propose_raw = parsed.get("propose_memory", False)
            if isinstance(propose_raw, bool):
                propose = propose_raw
                rationale = parsed.get("rationale", "")
            elif isinstance(propose_raw, str) and propose_raw.strip():
                # Older models sometimes put rationale in propose_memory instead of a boolean.
                propose = True
                rationale = propose_raw
            else:
                propose = False
                rationale = parsed.get("rationale", "")
            proposed_text = parsed.get("proposed_content") or parsed.get("proposed_text") or ""
            if propose and not proposed_text.strip():
                if isinstance(propose_raw, str):
                    proposed_text = propose_raw
                elif rationale:
                    proposed_text = rationale
        except json.JSONDecodeError:
            answer = raw
            propose = False
            proposed_text = ""
            rationale = ""

        proposal_id = None
        if propose and proposed_text:
            proposal = CommitProposal(
                id=uuid.uuid4(),
                session_id=session_id,
                wallet=wallet.lower(),
                proposed_content_json={"text": proposed_text, "format": "markdown"},
                source_attribution_json={"source": "agent", "session_id": session_id},
                agent_rationale=rationale or "Agent suggested persisting this knowledge.",
                status=ProposalStatus.PENDING,
            )
            db.add(proposal)
            await db.flush()
            proposal_id = str(proposal.id)

        if accessible_ids:
            for rid in accessible_ids[:1]:
                db.add(
                    MemoryUsageEvent(
                        repository_id=uuid.UUID(rid),
                        event_type="retrieve",
                        actor_wallet=wallet.lower(),
                    )
                )

        access_denied = bool(repository_ids and not accessible_ids)
        return {
            "answer": answer,
            "proposal_id": proposal_id,
            "retrieved": len(results),
            "access_denied": access_denied,
        }

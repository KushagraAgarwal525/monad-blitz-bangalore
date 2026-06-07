import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import CommitProposal, MemoryRepository, ProposalStatus
from app.services.deps import get_agent_service, get_commit_service, get_fireworks

router = APIRouter(tags=["agent"])


class ChatRequest(BaseModel):
    wallet: str
    session_id: str
    message: str
    repository_ids: list[str] | None = None


@router.post("/agent/chat")
async def agent_chat(body: ChatRequest, db: AsyncSession = Depends(get_db), agent=Depends(get_agent_service)):
    return await agent.chat(db, body.wallet, body.session_id, body.message, body.repository_ids)


@router.get("/proposals/pending")
async def pending_proposals(wallet: str, db: AsyncSession = Depends(get_db)):
    proposals = (
        await db.execute(
            select(CommitProposal).where(
                CommitProposal.wallet == wallet.lower(),
                CommitProposal.status == ProposalStatus.PENDING,
            )
        )
    ).scalars().all()
    return [
        {
            "id": str(p.id),
            "proposed_content_json": p.proposed_content_json,
            "agent_rationale": p.agent_rationale,
            "repository_id": str(p.repository_id) if p.repository_id else None,
        }
        for p in proposals
    ]


class ApproveProposal(BaseModel):
    repository_id: str
    wallet: str


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    body: ApproveProposal,
    db: AsyncSession = Depends(get_db),
    cs=Depends(get_commit_service),
    fw=Depends(get_fireworks),
):
    proposal = await db.get(CommitProposal, uuid.UUID(proposal_id))
    if not proposal or proposal.status != ProposalStatus.PENDING:
        raise HTTPException(404, "Proposal not found")
    repo = await db.get(MemoryRepository, uuid.UUID(body.repository_id))
    if not repo:
        raise HTTPException(404, "Repository not found")

    text = proposal.proposed_content_json.get("text", "")
    emb = fw.embed_text(text)
    commit = await cs.create_commit_from_approved(
        db,
        repo,
        proposal.proposed_content_json,
        proposal.source_attribution_json,
        emb,
        body.wallet.lower(),
    )
    proposal.status = ProposalStatus.APPROVED
    proposal.repository_id = repo.id

    return {
        "commit_hash": commit.commit_hash,
        "state_root": commit.state_root,
        "primary_parent_commit_hash": commit.primary_parent_commit_hash,
        "parent_count": commit.parent_count,
        "secondary_parents_canonical": commit.secondary_parents_canonical,
        "content_hash": commit.content_hash,
        "embedding_hash": commit.embedding_hash,
        "source_attribution_hash": commit.source_attribution_hash,
    }


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: str, db: AsyncSession = Depends(get_db)):
    proposal = await db.get(CommitProposal, uuid.UUID(proposal_id))
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    proposal.status = ProposalStatus.REJECTED
    return {"status": "rejected"}

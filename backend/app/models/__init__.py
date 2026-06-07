import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Visibility(str, enum.Enum):
    PRIVATE = "PRIVATE"
    LICENSED = "LICENSED"
    PUBLIC = "PUBLIC"


class ProposalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_address: Mapped[str] = mapped_column(String(42), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryRepository(Base):
    __tablename__ = "repositories"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    on_chain_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    owner_wallet: Mapped[str] = mapped_column(String(42), index=True)
    head_commit_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    parent_memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True)
    fork_point_commit_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    visibility: Mapped[Visibility] = mapped_column(Enum(Visibility), default=Visibility.PRIVATE)
    metadata_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    current_commit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    commits: Mapped[list["MemoryCommit"]] = relationship(back_populates="repository")
    display_metadata: Mapped["RepositoryDisplayMetadata | None"] = relationship(back_populates="repository", uselist=False)


class MemoryCommit(Base):
    __tablename__ = "memory_commits"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"), index=True)
    commit_hash: Mapped[str] = mapped_column(String(66), unique=True, index=True)
    primary_parent_commit_hash: Mapped[str] = mapped_column(String(66))
    parent_count: Mapped[int] = mapped_column(Integer, default=1)
    secondary_parent_commit_hashes: Mapped[list] = mapped_column(JSON, default=list)
    secondary_parents_canonical: Mapped[str] = mapped_column(String(66))
    content_hash: Mapped[str] = mapped_column(String(66))
    embedding_hash: Mapped[str] = mapped_column(String(66))
    source_attribution_hash: Mapped[str] = mapped_column(String(66))
    state_root: Mapped[str] = mapped_column(String(66))
    content_json: Mapped[dict] = mapped_column(JSON)
    source_attribution_json: Mapped[dict] = mapped_column(JSON)
    creator_wallet: Mapped[str] = mapped_column(String(42))
    timestamp: Mapped[int] = mapped_column(Integer)
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    commit_index: Mapped[int] = mapped_column(Integer)

    repository: Mapped["MemoryRepository"] = relationship(back_populates="commits")


class CommitProposal(Base):
    __tablename__ = "commit_proposals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True)
    session_id: Mapped[str] = mapped_column(String(64))
    wallet: Mapped[str] = mapped_column(String(42))
    proposed_content_json: Mapped[dict] = mapped_column(JSON)
    source_attribution_json: Mapped[dict] = mapped_column(JSON)
    agent_rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[ProposalStatus] = mapped_column(Enum(ProposalStatus), default=ProposalStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RepositoryDisplayMetadata(Base):
    __tablename__ = "repository_display_metadata"
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_photo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    display_tags: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    repository: Mapped["MemoryRepository"] = relationship(back_populates="display_metadata")


class License(Base):
    __tablename__ = "licenses"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"), index=True)
    licensee_wallet: Mapped[str] = mapped_column(String(42), index=True)
    license_type: Mapped[str] = mapped_column(String(32))
    payment_type: Mapped[str] = mapped_column(String(8), default="MEM")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    price_paid_mem: Mapped[float] = mapped_column(Float, default=0)
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)


class RoyaltyRule(Base):
    __tablename__ = "royalty_rules"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"))
    ancestor_repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"))
    percentage_bps: Mapped[int] = mapped_column(Integer)


class ForkRelationship(Base):
    __tablename__ = "forks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"))
    child_repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"))
    fork_point_commit_hash: Mapped[str] = mapped_column(String(66))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RevenueEvent(Base):
    __tablename__ = "revenue_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(16))
    amount_mem: Mapped[float] = mapped_column(Float)
    payer_wallet: Mapped[str | None] = mapped_column(String(42), nullable=True)
    recipient_wallet: Mapped[str | None] = mapped_column(String(42), nullable=True)
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryUsageEvent(Base):
    __tablename__ = "usage_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"))
    commit_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32))
    actor_wallet: Mapped[str | None] = mapped_column(String(42), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryScore(Base):
    __tablename__ = "memory_scores"
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    license_revenue: Mapped[float] = mapped_column(Float, default=0)
    royalty_revenue: Mapped[float] = mapped_column(Float, default=0)
    knowledge_revenue: Mapped[float] = mapped_column(Float, default=0)
    fork_count: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_volume: Mapped[int] = mapped_column(Integer, default=0)
    memory_age_days: Mapped[int] = mapped_column(Integer, default=0)
    breakdown_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_snapshot_tx: Mapped[str | None] = mapped_column(String(66), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentChatLog(Base):
    __tablename__ = "agent_chat_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(64))
    wallet: Mapped[str] = mapped_column(String(42))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
